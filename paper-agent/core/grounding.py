"""
grounding — 소스 읽기(dumb 추출) + 수치 검증 + 프롬프트 블록화.

논문에서 제일 중요: 본문 수치는 반드시 실제 데이터(results/summary.json 등)에서만.
  - read_source        : 파일/URL → 텍스트(캐시 스냅샷).
  - unverified_numbers : 본문 수치 중 자료에서 확인 안 되는 값 검출(결정적, LLM 무관).
  - ground_block       : grounding 텍스트를 프롬프트 블록 + 사용 원칙으로 포맷.
"""
from pathlib import Path
import hashlib
import importlib
import json
import re

from core.config import REPO_ROOT, MAX_FILE_CHARS

_CACHE_DIR = REPO_ROOT / "cache" / "paper_source"
_MAX_FILE_CHARS = MAX_FILE_CHARS


def ground_block(grounding_text: str) -> str:
    """참고 기반 자료(실측 데이터) 블록 + 사용 원칙. write/review/revise 공용."""
    if not grounding_text:
        return ""
    return (
        "\n[참고 기반 자료 — 실측 데이터/근거]\n"
        "아래 자료는 본문 작성의 사실 근거입니다.\n"
        "자료의 수치·용어·결과를 우선 반영하고, 자료와 충돌하는 내용은 쓰지 마세요.\n"
        "배경 설명·일반 지식·논증은 자유롭게 쓰되,\n"
        "자료에 없는 구체 수치·고유 결과·출처성 주장은 확정적으로 단정하지 마세요.\n\n"
        f"{grounding_text}\n"
    )


def _require(mod: str, pip: str):
    try:
        return importlib.import_module(mod)
    except ImportError:
        raise RuntimeError(f"[source] '{mod}' 모듈이 필요합니다 → pip install {pip}")


def _truncate(text: str) -> str:
    if len(text) > _MAX_FILE_CHARS:
        return text[:_MAX_FILE_CHARS] + "\n...(이하 생략)"
    return text


def _read_file(path: Path) -> str:
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"[source] 파일 없음: {path}")
    suffix = path.suffix.lower()

    if suffix in {".xlsx", ".xls"}:
        openpyxl = _require("openpyxl", "openpyxl")
        wb = openpyxl.load_workbook(path, data_only=True)
        lines = []
        for ws in wb.worksheets:
            lines.append(f"# sheet: {ws.title}")
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    lines.append(" | ".join(cells))
        return "\n".join(lines)
    if suffix == ".pdf":
        pypdf = _require("pypdf", "pypdf")
        reader = pypdf.PdfReader(str(path))
        return "\n".join((pg.extract_text() or "") for pg in reader.pages)
    if suffix == ".docx":
        docx = _require("docx", "python-docx")
        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    return path.read_text(encoding="utf-8")             # .md/.txt/.csv/.json/...


def _read_url(url: str) -> str:
    httpx = _require("httpx", "httpx")
    trafilatura = _require("trafilatura", "trafilatura")
    html = httpx.get(url, timeout=15.0, follow_redirects=True).text
    text = trafilatura.extract(html) or ""
    if not text:
        raise RuntimeError(f"[source] URL 본문 추출 실패: {url}")
    return text


def _cache_path(slug: str, source: str) -> Path:
    h = hashlib.sha1(source.encode("utf-8")).hexdigest()[:10]
    return _CACHE_DIR / f"{slug}-{h}.txt"


def read_source(source: str | None, slug: str, use_cache: bool = True) -> str:
    """`source`(파일경로|URL) → 텍스트. 없으면 빈 문자열."""
    if not source:
        return ""
    cache = _cache_path(slug, source)
    if use_cache and cache.exists():
        print(f"  [source] 캐시 사용: {cache.name}")
        return cache.read_text(encoding="utf-8")

    is_url = source.lower().startswith(("http://", "https://"))
    if not is_url:
        p = Path(source)
        if not p.is_absolute():
            p = REPO_ROOT / p
        if not p.exists():
            print(f"  [source] 파일/URL 아님 — grounding 없이 진행: {source[:60]}")
            return ""
    text = _truncate(_read_url(source) if is_url else _read_file(Path(source)))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    print(f"  [source] 해소: {'url' if is_url else 'file'}, {len(text)}자 → {cache.name}")
    return text


# -------- 결정적 수치 검증 (환각 차단, LLM 판단과 무관) --------
_SKIP_NUMS = {0.0, 100.0}
_NUM_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
_NUM_IN_STR = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _collect_payload_values(payload: str) -> set[float]:
    vals: set[float] = set()

    def add(x: float) -> None:
        vals.add(x)
        if 0 < abs(x) < 1:
            vals.add(x * 100)        # 0.032 → 3.2 (비율을 퍼센트로 인용 허용)

    def harvest(s: str) -> None:
        for m in _NUM_IN_STR.findall(s):
            try:
                add(float(m.replace(",", "")))
            except ValueError:
                pass

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        harvest(payload)
        return vals

    def walk(o) -> None:
        if isinstance(o, bool):
            return
        if isinstance(o, (int, float)):
            add(float(o))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            harvest(o)

    walk(data)
    return vals


def unverified_numbers(text: str, payload: str, rel_tol: float = 0.05) -> list[str]:
    """text의 '유의미한' 수치 중 근거 payload에서 확인할 수 없는 것들의 목록."""
    if not text or not payload:
        return []
    allowed = _collect_payload_values(payload)
    out: list[str] = []
    seen: set[str] = set()
    for tok in _NUM_TOKEN.findall(text):
        if tok in seen:
            continue
        seen.add(tok)
        pct = tok.endswith("%")
        core = (tok[:-1] if pct else tok).replace(",", "")
        try:
            val = float(core)
        except ValueError:
            continue
        if not ("." in core or abs(val) >= 1000 or pct):
            continue
        if val in _SKIP_NUMS and "." not in core:
            continue
        dec = len(core.split(".")[1]) if "." in core else 0
        cands = [val] + ([val / 100] if pct else [])
        ok = any(
            round(v, dec) == round(c, dec) or abs(c - v) <= abs(v) * rel_tol + 1e-9
            for c in cands for v in allowed
        )
        if not ok:
            out.append(tok)
    return out

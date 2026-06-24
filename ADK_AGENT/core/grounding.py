"""
grounding — 소스 읽기(dumb 추출) + 수치 검증 + 프롬프트 블록화.

grounding 은 전 단계를 가로지른다: design(생성)·write/review/revise(소비)·검증.
그 관련 기능을 한 곳에 모은다.
  - read_source        : `source`(파일/URL) 한 줄 → 텍스트(캐시 스냅샷). "읽기(dumb)"만.
  - unverified_numbers : 본문 수치 중 자료에서 확인 안 되는 값 검출(결정적).
  - ground_block       : grounding 텍스트를 프롬프트 블록 + 사용 원칙으로 포맷(write/review/revise 공용).
"해석·요약·목차화(smart)"는 Design 에이전트 몫. generator/grounding.py 를 복사·단순화(원본 무수정).
"""
from pathlib import Path
import hashlib
import importlib
import json
import re

from core.config import REPO_ROOT, MAX_FILE_CHARS

_CACHE_DIR = REPO_ROOT / "cache" / "adk_source"
_MAX_FILE_CHARS = MAX_FILE_CHARS                         # 토큰 예산 보호용 절단 한도


def ground_block(grounding_text: str) -> str:
    """참고 기반 자료 블록 + 사용 원칙(한 곳에서만 정의). write/review/revise 공용."""
    if not grounding_text:
        return ""
    return (
        "\n[참고 기반 자료]\n"
        "아래 자료는 본문 작성의 주요 참고 기반입니다.\n"
        "자료의 핵심 내용, 용어, 사례, 수치, 관점을 우선 반영하세요.\n"
        "자료와 충돌하는 내용은 쓰지 마세요.\n"
        "독자의 이해를 돕는 일반 지식, 배경 설명, 비유, 예시 등은 자유롭게 사용할 수 있습니다.\n"
        "단, 자료에 없는 구체 수치·고유 사실·출처성 주장은 확정적으로 단정하지 마세요.\n\n"
        f"{grounding_text}\n"
    )


def _require(mod: str, pip: str):
    """기능별 의존성을 실제 사용 시점에만 검사. 없으면 설치 안내."""
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
    return path.read_text(encoding="utf-8")             # .md/.txt/.csv/...


def _read_url(url: str) -> str:
    httpx = _require("httpx", "httpx")
    trafilatura = _require("trafilatura", "trafilatura")
    html = httpx.get(url, timeout=15.0, follow_redirects=True).text
    text = trafilatura.extract(html) or ""              # 본문만 추출 (HTML 쓰레기 제거)
    if not text:
        raise RuntimeError(f"[source] URL 본문 추출 실패: {url}")
    return text


def _cache_path(slug: str, source: str) -> Path:
    h = hashlib.sha1(source.encode("utf-8")).hexdigest()[:10]
    return _CACHE_DIR / f"{slug}-{h}.txt"


def read_source(source: str | None, slug: str, use_cache: bool = True) -> str:
    """`source`(파일경로|URL) → 텍스트. 없으면 빈 문자열(모델 지식으로 작성)."""
    if not source:
        return ""
    cache = _cache_path(slug, source)
    if use_cache and cache.exists():
        print(f"  [source] 캐시 사용: {cache.name}")
        return cache.read_text(encoding="utf-8")

    is_url = source.lower().startswith(("http://", "https://"))
    if not is_url:
        # source가 URL도 실제 파일도 아니면 '영감용 설명 텍스트'(예: 소설의 원작 참고)로 본다.
        # grounding 없이 진행 — 정체성·창작 브리프는 config(description 등)에 이미 있고,
        # 짧은 설명을 grounding 으로 걸면 수치 검증이 본문 숫자를 전부 미검증으로 오판한다.
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
_SKIP_NUMS = {0.0, 100.0}                          # 수사적 상수(0, 100%)는 검사 제외
_NUM_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?%?")    # 검사 대상 수치 토큰
_NUM_IN_STR = re.compile(r"-?\d[\d,]*(?:\.\d+)?")   # 문자열 안 숫자 수집용


def _collect_payload_values(payload: str) -> set[float]:
    """근거 payload에서 인용 가능한 실제 숫자 집합. JSON이면 파싱, 아니면 정규식."""
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
    """text의 '유의미한' 수치 중 근거 payload에서 확인할 수 없는 것들의 목록.

    유의미 = 소수점이 있거나, 1000 이상이거나, %가 붙은 수치(측정값 후보).
    매칭 = 같은 소수자리로 반올림 일치 또는 상대오차 rel_tol 이내(반올림·근사 허용).
    """
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
            continue                              # 구조적 소정수 무시
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

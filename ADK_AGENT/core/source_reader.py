"""
소스 reader (얇은 dumb 추출) + 결정적 수치 검증.

설계: "읽기(dumb)"만 코드에 남기고, "해석·요약·목차화(smart)"는 Design 에이전트로 올린다.
입력 JSON의 `source`(파일경로 또는 URL) 한 줄을 받아 텍스트로 해소 → state["source_text"].
kind는 문자열에서 추론(http*면 url, 아니면 파일). 결과는 cache/ 에 스냅샷(오프라인 재생성).

generator/grounding.py 의 reader/resolver/unverified_numbers 를 복사·단순화한 것(원본 무수정).
"""
from pathlib import Path
import hashlib
import importlib
import json
import re

_ROOT = Path(__file__).resolve().parent.parent.parent   # ai-books/ (core/ 한 단계 더 깊음)
_CACHE_DIR = _ROOT / "cache" / "adk_source"
_MAX_FILE_CHARS = 12000                                  # 토큰 예산 보호용 절단 한도


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
        path = _ROOT / path
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

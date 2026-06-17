"""
그라운딩(근거) 추상화 — 참고 기반 자료를 프롬프트용 텍스트로 해소.

spec의 선택 필드 `grounding`을 받아 `Grounding` 객체로 해소한다.
grounding이 없으면 None → 모델 지식으로 작성(책/소설 등).

지원 kind:
  - "file" : 로컬 파일(.md/.txt/.csv/.xlsx/.pdf/.docx)
  - "url"  : 웹 페이지 본문 추출(trafilatura)
  - "text" : spec에 인라인으로 박은 텍스트

해소 결과는 cache/grounding/<slug>-<spec해시>.json 에 스냅샷되어 재현/오프라인 생성이 가능하다.
의존성(openpyxl/pypdf/python-docx/trafilatura/httpx)은 실제 사용 시점에만 검사한다.
"""
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import importlib
import json
import re

_ROOT = Path(__file__).resolve().parent.parent
_CACHE_DIR = _ROOT / "cache" / "grounding"
_MAX_FILE_CHARS = 12000  # 토큰 예산 보호용 절단 한도


@dataclass
class Grounding:
    payload: str                         # 프롬프트에 주입할 텍스트
    provenance: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({"payload": self.payload, "provenance": self.provenance},
                          ensure_ascii=False, indent=2)

    @staticmethod
    def from_json(s: str) -> "Grounding":
        d = json.loads(s)
        return Grounding(payload=d["payload"], provenance=d.get("provenance", {}))


def _require(mod: str, pip: str):
    """기능별 의존성을 실제 사용 시점에만 검사. 없으면 설치 안내."""
    try:
        return importlib.import_module(mod)
    except ImportError:
        raise RuntimeError(f"[grounding] '{mod}' 모듈이 필요합니다 → pip install {pip}")


def _truncate(text: str) -> tuple[str, bool]:
    if len(text) > _MAX_FILE_CHARS:
        return text[:_MAX_FILE_CHARS] + "\n...(이하 생략)", True
    return text, False


# -------- 결정적 수치 검증 (환각 차단, LLM 판단과 무관) --------
# 근거(payload)에 실재하지 않는 수치가 텍스트에 있으면 잡아낸다.
# 구조적 소정수(단계 번호 등)는 무시하고, 측정값으로 보이는 수치만 검사한다.
_SKIP_NUMS = {0.0, 100.0}                          # 수사적 상수(0, 100%)는 검사 제외
_NUM_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?%?")    # 검사 대상 수치 토큰
_NUM_IN_STR = re.compile(r"-?\d[\d,]*(?:\.\d+)?")   # 문자열 안 숫자 수집용


def _collect_payload_values(payload: str) -> set[float]:
    """근거 payload에서 인용 가능한 실제 숫자 집합. JSON이면 파싱, 아니면 정규식."""
    vals: set[float] = set()

    def add(x: float) -> None:
        vals.add(x)
        if 0 < abs(x) < 1:
            vals.add(x * 100)        # 0.032 → 3.2 (비율을 퍼센트로 인용하는 것 허용)

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


# -------- kind별 resolver --------
def _resolve_file(spec: dict) -> Grounding:
    path = Path(spec["path"])
    if not path.is_absolute():
        path = _ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"[grounding] 파일 없음: {path}")
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
        text = "\n".join(lines)
    elif suffix == ".pdf":
        pypdf = _require("pypdf", "pypdf")
        reader = pypdf.PdfReader(str(path))
        text = "\n".join((pg.extract_text() or "") for pg in reader.pages)
    elif suffix == ".docx":
        docx = _require("docx", "python-docx")
        doc = docx.Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:  # .md/.txt/.csv/...
        text = path.read_text(encoding="utf-8")

    text, truncated = _truncate(text)
    return Grounding(payload=text,
                     provenance={"source": "file", "path": str(path),
                                 "format": suffix.lstrip("."), "truncated": truncated})


def _resolve_url(spec: dict) -> Grounding:
    httpx = _require("httpx", "httpx")
    trafilatura = _require("trafilatura", "trafilatura")
    url = spec["url"]
    html = httpx.get(url, timeout=spec.get("timeout", 15.0), follow_redirects=True).text
    text = trafilatura.extract(html) or ""        # 본문만 추출 (HTML 쓰레기 제거)
    if not text:
        raise RuntimeError(f"[grounding] URL 본문 추출 실패: {url}")
    text, truncated = _truncate(text)
    return Grounding(payload=text, provenance={"source": "url", "url": url, "truncated": truncated})


def _resolve_text(spec: dict) -> Grounding:
    text, truncated = _truncate(spec.get("text", ""))
    return Grounding(payload=text, provenance={"source": "text", "truncated": truncated})


RESOLVERS = {
    "file": _resolve_file,
    "url": _resolve_url,
    "text": _resolve_text,
}


def _cache_path(slug: str, spec: dict) -> Path:
    """slug + spec 해시. 같은 slug라도 spec이 바뀌면 캐시를 새로 만든다."""
    raw = json.dumps(spec, ensure_ascii=False, sort_keys=True)
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return _CACHE_DIR / f"{slug}-{h}.json"


def resolve_grounding(spec_grounding: dict | None, slug: str,
                      use_cache: bool = True) -> Grounding | None:
    """spec.grounding → Grounding. 없으면 None. 같은 spec 캐시가 있으면 재사용."""
    if not spec_grounding:
        return None
    kind = spec_grounding.get("kind")
    if kind not in RESOLVERS:
        raise ValueError(f"알 수 없는 grounding kind: {kind!r} (지원: {list(RESOLVERS)})")

    cache = _cache_path(slug, spec_grounding)
    if use_cache and cache.exists():
        print(f"  [grounding] 캐시 사용: {cache.name}")
        return Grounding.from_json(cache.read_text(encoding="utf-8"))

    g = RESOLVERS[kind](spec_grounding)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(g.to_json(), encoding="utf-8")
    print(f"  [grounding] 해소: kind={kind}, payload {len(g.payload)}자 → {cache.name}")
    return g

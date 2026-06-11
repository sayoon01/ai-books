"""
그라운딩(근거) 추상화 — 선택·다형·캐시.

spec의 선택 필드 `grounding`을 받아, 프롬프트에 주입할 `Grounding` 객체로 해소한다.
grounding이 없으면 None → 모델 지식으로 작성(책/소설 등).

지원 kind:
  - "mold_api" : :33001 API + 엑셀 사전 → DataDigest (구조화 통계)
  - "file"     : 로컬 파일(.md/.txt/.csv/.xlsx) 내용/요약
  - "url"      : 평문 HTTP fetch (텍스트/JSON)
  - "text"     : spec에 인라인으로 박은 텍스트

해소 결과는 cache/grounding/<slug>.json 에 스냅샷되어 재현/오프라인 생성이 가능하다.
"""
from dataclasses import dataclass, field
from pathlib import Path
import json

_ROOT = Path(__file__).resolve().parent.parent
_CACHE_DIR = _ROOT / "cache" / "grounding"
_MAX_FILE_CHARS = 12000  # 토큰 예산 보호용 절단 한도


@dataclass
class Grounding:
    payload: str                          # 프롬프트에 주입할 텍스트
    ref_keys: set[str] = field(default_factory=set)  # Planner data_refs 검증용(없으면 빈 set)
    provenance: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({"payload": self.payload, "ref_keys": sorted(self.ref_keys),
                           "provenance": self.provenance}, ensure_ascii=False, indent=2)

    @staticmethod
    def from_json(s: str) -> "Grounding":
        d = json.loads(s)
        return Grounding(payload=d["payload"], ref_keys=set(d.get("ref_keys", [])),
                         provenance=d.get("provenance", {}))


# -------- 범용 키 추출 (도메인 무관) --------
def flatten_keys(obj, prefix: str = "") -> set[str]:
    """구조화 데이터(dict/list)를 재귀로 훑어 점(.) 경로 키 집합을 만든다.
    Planner.data_refs 교차검증용. 도메인별로 키를 손으로 적지 않는다."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            full = f"{prefix}.{k}" if prefix else k
            keys.add(full)
            keys |= flatten_keys(v, full)
    elif isinstance(obj, list):
        for item in obj:
            keys |= flatten_keys(item, prefix)
    return keys


# -------- kind별 resolver --------
def _resolve_mold_api(spec: dict) -> Grounding:
    from digest.build import load_or_build, DEFAULT_EXCEL, DEFAULT_API
    digest = load_or_build(
        cache_path=str(_CACHE_DIR / "_mold_digest.json"),
        excel_path=spec.get("excel", DEFAULT_EXCEL),
        api_base=spec.get("api", DEFAULT_API),
        force=spec.get("force", False),
    )
    return Grounding(
        payload=digest.model_dump_json(indent=2),
        ref_keys=flatten_keys(digest.model_dump()),   # 데이터에서 자동 추출
        provenance=digest.provenance.model_dump(),
    )


def _resolve_file(spec: dict) -> Grounding:
    path = Path(spec["path"])
    if not path.is_absolute():
        path = _ROOT / path
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True)
        lines = []
        for ws in wb.worksheets:
            lines.append(f"# sheet: {ws.title}")
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    lines.append(" | ".join(cells))
        text = "\n".join(lines)
    else:  # .md/.txt/.csv/...
        text = path.read_text(encoding="utf-8")
    truncated = len(text) > _MAX_FILE_CHARS
    if truncated:
        text = text[:_MAX_FILE_CHARS] + "\n...(이하 생략)"
    return Grounding(payload=text,
                     provenance={"source": "file", "path": str(path), "truncated": truncated})


def _resolve_url(spec: dict) -> Grounding:
    import httpx
    url = spec["url"]
    r = httpx.get(url, timeout=spec.get("timeout", 15.0))  # 평문 HTTP 유지
    r.raise_for_status()
    text = r.text
    if len(text) > _MAX_FILE_CHARS:
        text = text[:_MAX_FILE_CHARS] + "\n...(이하 생략)"
    return Grounding(payload=text, provenance={"source": "url", "url": url})


def _resolve_text(spec: dict) -> Grounding:
    return Grounding(payload=spec.get("text", ""), provenance={"source": "text"})


RESOLVERS = {
    "mold_api": _resolve_mold_api,
    "file": _resolve_file,
    "url": _resolve_url,
    "text": _resolve_text,
}


def resolve_grounding(spec_grounding: dict | None, slug: str,
                      use_cache: bool = True) -> Grounding | None:
    """spec.grounding → Grounding. 없으면 None. 캐시가 있으면 재사용."""
    if not spec_grounding:
        return None
    kind = spec_grounding.get("kind")
    if kind not in RESOLVERS:
        raise ValueError(f"알 수 없는 grounding kind: {kind!r} (지원: {list(RESOLVERS)})")

    cache = _CACHE_DIR / f"{slug}.json"
    if use_cache and cache.exists():
        print(f"  [grounding] 캐시 사용: {cache}")
        return Grounding.from_json(cache.read_text(encoding="utf-8"))

    g = RESOLVERS[kind](spec_grounding)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(g.to_json(), encoding="utf-8")
    print(f"  [grounding] 해소: kind={kind}, payload {len(g.payload)}자, "
          f"ref_keys {len(g.ref_keys)}개 → {cache}")
    return g

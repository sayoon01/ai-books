"""
소스(API+엑셀)를 합쳐 DataDigest를 만들고 스냅샷 캐시한다.

- API가 살아있으면 실측 숫자 + 엑셀 사전 = 옵션 C(권장).
- API가 죽으면 엑셀 사전만으로 폴백(옵션 A). 이 경우 통계는 비고 provenance.source="excel".
- 캐시(cache/grounding/)가 있으면 서버 없이 재현/오프라인 생성 가능.

스냅샷 만들기:
  python -m digest.build               # generator/ 에서 실행
  python -m digest.build --force       # 캐시 무시하고 다시 받기
"""
from datetime import datetime, timezone
from pathlib import Path

from schemas import (
    DataDigest, Provenance, StatBlock, MoldModelStat, Corr, ModelMeta,
)
from digest.api_source import ApiSource
from digest.excel_source import ExcelSource

# 경로는 CWD와 무관하게 프로젝트 루트 기준으로 고정 (generator/digest/build.py → 루트)
_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CACHE = str(_ROOT / "cache" / "grounding" / "_mold_digest.json")
DEFAULT_EXCEL = str(_ROOT / "data" / "241118 금형 필드 설명_수정.xlsx")
DEFAULT_API = "http://keti-ev1.iptime.org:33001"


def _molds(summary: dict, top: int = 8) -> list[MoldModelStat]:
    out = []
    for mid, m in (summary.get("mold_models") or {}).items():
        tot = m.get("total_cycles", 0) or 0
        out.append(MoldModelStat(
            model=mid, n_cycles=tot,
            anomaly_rate=(m.get("anomaly_count", 0) / tot) if tot else 0.0,
            mean_ct_sec=m.get("ci_mean_sec", 0.0) or 0.0,
        ))
    out.sort(key=lambda x: x.n_cycles, reverse=True)
    return out[:top]


def _proc(d) -> dict[str, StatBlock]:
    """proc-stats: {proc: {mean,p1,p25,p75,p99,n}} 형태를 가정. 키 없으면 건너뜀."""
    if not isinstance(d, dict):
        return {}
    out = {}
    need = ("mean", "p1", "p25", "p75", "p99", "n")
    for k, v in d.items():
        if isinstance(v, dict) and all(x in v for x in need):
            out[k] = StatBlock(**{x: v[x] for x in need})
    return out


def _corr(d, thresh: float = 0.8, top: int = 40) -> list[Corr]:
    """correlation: {features:[...], matrix:[[...]]}. 상삼각에서 |r|>thresh만 추출."""
    if not isinstance(d, dict):
        return []
    feats, mat = d.get("features"), d.get("matrix")
    if not (isinstance(feats, list) and isinstance(mat, list)):
        return []
    out = []
    for i in range(len(feats)):
        for j in range(i + 1, len(feats)):
            try:
                r = float(mat[i][j])
            except (IndexError, TypeError, ValueError):
                continue
            if abs(r) > thresh:
                out.append(Corr(a=str(feats[i]), b=str(feats[j]), r=round(r, 3)))
    out.sort(key=lambda c: abs(c.r), reverse=True)
    return out[:top]


def _n_clusters(d) -> int:
    """cluster-stats: 평면 dict 123개. 중심값은 토큰 예산상 미주입, 개수만."""
    return len(d) if isinstance(d, list) else 0


def _models(d) -> list[ModelMeta]:
    """model-meta: {task: {model_name, n_features, n_classes, ...}} 딕셔너리."""
    if not isinstance(d, dict):
        return []
    out = []
    for task, m in d.items():
        if not isinstance(m, dict):
            continue
        n_classes = m.get("n_classes")
        out.append(ModelMeta(
            name=str(m.get("model_name", "?")),
            task=str(task),
            n_features=int(m.get("n_features", 0) or 0),
            notes=(f"n_classes={n_classes}" if n_classes else ""),
        ))
    return out


def _round(v, nd: int = 2):
    return round(float(v), nd) if isinstance(v, (int, float)) else v


def _sensor_stats(d) -> dict:
    """sensor-dist: {t:{T1:{mean,p1,p99,...}}, p:{P1:{...}}} → {T1:{mean,p1,p99}}."""
    if not isinstance(d, dict):
        return {}
    out = {}
    for group in ("t", "p"):
        for name, s in (d.get(group) or {}).items():
            if isinstance(s, dict) and "mean" in s:
                out[name] = {k: _round(s[k]) for k in ("mean", "p1", "p99") if k in s}
    return out


def _dist_summary(d, keys) -> dict:
    """ci-hist/wait-dist에서 스칼라 요약만 추출(히스토그램 edges/counts 제외)."""
    if not isinstance(d, dict):
        return {}
    out = {}
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)):
            out[k] = int(v) if k == "n" else _round(v)
    return out


def _anomaly_categories(d) -> dict:
    return (d.get("category_dist") if isinstance(d, dict) else {}) or {}


def build_digest(api: ApiSource | None, excel: ExcelSource | None, fetched_at: str) -> DataDigest:
    data = api.fetch_all() if api else {}
    summary = data.get("summary") or {}
    has_api = bool(summary)

    if has_api and excel:
        src = "composite(api+excel)"
    elif has_api:
        src = "api"
    else:
        src = "excel"  # API 폴백

    tot = summary.get("total_cycles", 0) or 0
    return DataDigest(
        provenance=Provenance(source=src, fetched_at=fetched_at,
                              api_base=api.base if api else None),
        n_cycles=tot,
        period=str(summary.get("updated_at", "")),
        cycle_type_dist=summary.get("cycle_type_dist", {}) or {},
        anomaly_rate=(summary.get("anomaly_total", 0) / tot) if tot else 0.0,
        mean_ct_sec=summary.get("ci_overall_mean", 0.0) or 0.0,
        mold_models=_molds(summary),
        process_time=_proc(data.get("proc-stats")),
        top_correlations=_corr(data.get("correlation")),
        n_clusters=_n_clusters(data.get("cluster-stats")),
        models_in_use=_models(data.get("model-meta")),
        field_dict=excel.field_dict() if excel else {},
        sensor_stats=_sensor_stats(data.get("sensor-dist")),
        cycle_interval=_dist_summary(data.get("ci-hist"), ["mean", "p25", "p50", "p75", "n"]),
        wait=_dist_summary(data.get("wait-dist"), ["mean", "p50", "p75", "p95", "n"]),
        anomaly_categories=_anomaly_categories(data.get("mismatch-stats")),
    )


def load_or_build(cache_path: str = DEFAULT_CACHE, excel_path: str = DEFAULT_EXCEL,
                  api_base: str = DEFAULT_API, force: bool = False) -> DataDigest:
    cache = Path(cache_path)
    if cache.exists() and not force:
        return DataDigest.model_validate_json(cache.read_text(encoding="utf-8"))

    api = ApiSource(api_base)
    excel = ExcelSource(excel_path) if Path(excel_path).exists() else None
    fetched_at = datetime.now(timezone.utc).isoformat()
    digest = build_digest(api, excel, fetched_at)

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(digest.model_dump_json(indent=2), encoding="utf-8")
    print(f"[digest] 저장: {cache}  (source={digest.provenance.source}, "
          f"n_cycles={digest.n_cycles}, fields={len(digest.field_dict)})")
    if digest.provenance.source == "excel":
        print("  [경고] API 미수신 → 엑셀 사전만 포함. API 복구 후 --force로 재생성 권장.")
    return digest


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="digest 스냅샷 생성")
    p.add_argument("--force", action="store_true")
    p.add_argument("--cache", default=DEFAULT_CACHE)
    p.add_argument("--excel", default=DEFAULT_EXCEL)
    p.add_argument("--api", default=DEFAULT_API)
    a = p.parse_args()
    load_or_build(a.cache, a.excel, a.api, force=a.force)

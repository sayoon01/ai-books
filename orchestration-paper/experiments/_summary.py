"""실험 결과 집계 (run_experiment / run_judge 공용)."""
from __future__ import annotations

import statistics


def agg(rows: list[dict], key: str):
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    if not vals:
        return None
    return {"mean": round(statistics.mean(vals), 2),
            "std": round(statistics.pstdev(vals), 2) if len(vals) > 1 else 0.0,  # std = 일관성
            "n": len(vals)}


def summarize(rows: list[dict]) -> dict:
    """구조별 지표 평균/표준편차(=일관성). error 행은 자동 제외(수치 없음)."""
    out: dict = {}
    for orch in sorted({r["orchestrator"] for r in rows}):
        sub = [r for r in rows if r["orchestrator"] == orch]
        ok = [r for r in sub if not r.get("error")]
        out[orch] = {
            "runs": len(sub),
            "errors": sum(1 for r in sub if r.get("error")),
            "elapsed_sec": agg(ok, "elapsed_sec"),
            "tokens": agg(ok, "tokens"),
            "best_score": agg(ok, "best_score"),
            "judge_score": agg(ok, "judge_score"),
            "chars": agg(ok, "chars"),
            "retry_count": agg(ok, "retry_count"),
        }
    return out

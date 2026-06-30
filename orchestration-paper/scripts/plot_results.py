"""results/<slug>/runs.jsonl → 논문용 막대그래프(figures/result_bar.pdf).

구조별 평균과 표준편차(=일관성, 에러바)를 함께 그린다.
라벨은 폰트 문제를 피해 영문으로 둔다(논문 그림용).

사용:
    python scripts/plot_results.py --runs results/<slug>/runs.jsonl
    python scripts/plot_results.py --task structured   # results/*structured*/ 자동 탐색은 안 함; 경로 권장
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
ORDER = ["code", "llm", "hybrid"]
LABELS = {"code": "Code", "llm": "LLM", "hybrid": "Hybrid"}


def load(runs_path: Path) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = defaultdict(list)
    for line in runs_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            by[r["orchestrator"]].append(r)
    return by


def _ms(rows: list[dict], key: str) -> tuple[float, float]:
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    if not vals:
        return 0.0, 0.0
    return statistics.mean(vals), (statistics.pstdev(vals) if len(vals) > 1 else 0.0)


def quality_key(by: dict) -> str:
    # judge_score 가 있으면 그것(별도 모델), 없으면 reviewer best_score.
    for rows in by.values():
        if any("judge_score" in r for r in rows):
            return "judge_score"
    return "best_score"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, help="runs.jsonl 경로")
    ap.add_argument("--out", default=str(ROOT / "figures" / "result_bar.pdf"))
    args = ap.parse_args()

    by = load(Path(args.runs))
    orchs = [o for o in ORDER if o in by] + [o for o in by if o not in ORDER]
    qkey = quality_key(by)

    panels = [("elapsed_sec", "Execution Time (s)"),
              (qkey, "Quality" + (" (judge)" if qkey == "judge_score" else " (reviewer)")),
              ("tokens", "Token Usage")]

    fig, axes = plt.subplots(1, 3, figsize=(10, 3.4))
    x = list(range(len(orchs)))
    for ax, (key, title) in zip(axes, panels):
        means = [_ms(by[o], key)[0] for o in orchs]
        stds = [_ms(by[o], key)[1] for o in orchs]
        ax.bar(x, means, yerr=stds, capsize=4,
               color=["#4C72B0", "#DD8452", "#55A868"][:len(orchs)])
        ax.set_xticks(x)
        ax.set_xticklabels([LABELS.get(o, o) for o in orchs])
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("Orchestration Comparison (mean ± std)", y=1.02)
    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), dpi=150, bbox_inches="tight")
    print(f"저장: {out} (+ .png)")


if __name__ == "__main__":
    main()

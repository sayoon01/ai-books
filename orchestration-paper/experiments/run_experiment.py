"""오케스트레이션 비교 실험 드라이버.

3구조(code/llm/hybrid) × 작업 × 반복 × 챕터 를 실행하고 지표를 모은다.
설계(design.json)는 작업당 1회 생성·캐시되어 세 구조가 동일 입력을 공유한다
(변인 통제). 실행에는 ollama 서버(gemma4:31b)가 떠 있어야 한다.

사용 예:
    # 스모크: code 구조로 1챕터 1회만
    python -m experiments.run_experiment --orch code --limit 1 --repeat 1

    # 본 실험: 세 구조, 첫 2챕터, 각 5회
    python -m experiments.run_experiment --orch all --limit 2 --repeat 5 \
        --task datasets/mold-machine-report.json

결과: results/<slug>/runs.jsonl (원시) + summary.json (집계)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

# orchestrators import 시 _bootstrap 가 testbed 를 sys.path 에 추가한다.
from orchestrators import REGISTRY, Result

from agent.design import run_or_load_design          # testbed
from core.grounding import read_source               # testbed
from core.config import QUALITY_GATE, TARGET_SCORE, MIN_CHARS  # testbed

ROOT = Path(__file__).resolve().parent.parent
_SKIP_KEYS = {"chapters", "source", "visuals"}


def _slug(title: str) -> str:
    import re
    s = re.sub(r"[^\w\s-]", "", title.lower().strip())
    return re.sub(r"[\s_]+", "-", s)


def _config(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in _SKIP_KEYS}


def build_base_state(doc: dict, out_dir: Path) -> tuple[dict, list[dict]]:
    """design 을 생성/로드하고 (base_state, chapters) 를 반환한다."""
    config = _config(doc)
    slug = _slug(doc["title"])
    source_text = read_source(doc.get("source"), slug)
    design_config = {**config, **({"chapters": doc["chapters"]} if doc.get("chapters") else {})}
    design = run_or_load_design(design_config, source_text, out_dir, force=False)

    base_state = {
        "config": config,
        "write_brief": design["write_brief"],
        "grounding": design["grounding_digest"],
        "min_chars": MIN_CHARS,
        "quality_gate": QUALITY_GATE,
        "target_score": TARGET_SCORE,
        "prev_summaries": [],
    }
    return base_state, design["chapters"]


def _agg(rows: list[dict], key: str):
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    if not vals:
        return None
    return {"mean": round(statistics.mean(vals), 2),
            "std": round(statistics.pstdev(vals), 2) if len(vals) > 1 else 0.0,  # std = 일관성
            "n": len(vals)}


def _summarize(rows: list[dict]) -> dict:
    """구조별 지표 평균/표준편차(=일관성)."""
    out: dict = {}
    for orch in sorted({r["orchestrator"] for r in rows}):
        sub = [r for r in rows if r["orchestrator"] == orch]
        out[orch] = {
            "runs": len(sub),
            "elapsed_sec": _agg(sub, "elapsed_sec"),
            "tokens": _agg(sub, "tokens"),
            "best_score": _agg(sub, "best_score"),
            "judge_score": _agg(sub, "judge_score"),
            "chars": _agg(sub, "chars"),
            "retry_count": _agg(sub, "retry_count"),
        }
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="datasets/structured.json",
                    help="입력 toc json (structured|creative|mixed)")
    ap.add_argument("--orch", default="code",
                    help="code|llm|hybrid|all (쉼표 구분 가능)")
    ap.add_argument("--repeat", type=int, default=1, help="반복 횟수(일관성용)")
    ap.add_argument("--limit", type=int, default=1, help="앞에서부터 챕터 N개")
    ap.add_argument("--out", default=None, help="결과 폴더(기본 results/<slug>)")
    ap.add_argument("--judge", action="store_true",
                    help="별도 모델 LLM-as-Judge 로 품질 채점(권장)")
    args = ap.parse_args()

    doc = json.loads((ROOT / args.task).read_text(encoding="utf-8"))
    slug = _slug(doc["title"])
    out_dir = Path(args.out) if args.out else ROOT / "results" / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    which = list(REGISTRY) if args.orch == "all" else [s.strip() for s in args.orch.split(",")]
    for name in which:
        if name not in REGISTRY:
            raise SystemExit(f"알 수 없는 구조: {name} (가능: {list(REGISTRY)} 또는 all)")

    print(f"[실험] task={slug} | 구조={which} | 챕터={args.limit} | 반복={args.repeat}")
    base_state, chapters = build_base_state(doc, out_dir)
    chapters = chapters[:args.limit]

    runs_path = out_dir / "runs.jsonl"
    rows: list[dict] = []
    t_all = time.perf_counter()

    with runs_path.open("a", encoding="utf-8") as fp:
        for name in which:
            orch = REGISTRY[name]()
            for ch in chapters:
                num = ch.get("number", "?")
                for rep in range(args.repeat):
                    print(f"  - {name} | 챕터 {num} | 반복 {rep+1}/{args.repeat} ...", flush=True)
                    res: Result = await orch.run(ch, base_state)
                    row = {
                        "orchestrator": res.orchestrator,
                        "chapter": num, "repeat": rep,
                        "elapsed_sec": res.elapsed_sec,
                        "tokens": res.tokens,
                        "token_detail": res.token_detail,
                        "best_score": res.best_score,
                        "chars": res.chars,
                        "write_count": res.write_count,
                        "pass_count": res.pass_count,
                        "retry_count": res.retry_count,
                    }
                    if args.judge:
                        from experiments.judge import judge
                        jr = judge(res.draft, ch, base_state["config"])
                        row["judge_score"] = jr["score"]
                        row["judge_detail"] = jr
                    rows.append(row)
                    fp.write(json.dumps(row, ensure_ascii=False) + "\n")
                    fp.flush()
                    print(f"    → {res.elapsed_sec}s, score={res.best_score}, "
                          f"tokens={res.tokens}, chars={res.chars}")

    summary = {"task": slug, "chapters": [c.get("number") for c in chapters],
               "repeat": args.repeat, "by_orchestrator": _summarize(rows)}
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[완료] {time.perf_counter()-t_all:.0f}s | "
          f"runs → {runs_path} | summary → {out_dir/'summary.json'}")
    print(json.dumps(summary["by_orchestrator"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

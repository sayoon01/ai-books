"""오케스트레이션 비교 실험 드라이버.

3구조(code/llm/hybrid) × 작업 × 반복 × 챕터 를 실행하고 지표를 모은다.
설계(design.json)는 작업당 1회 생성·캐시되어 세 구조가 동일 입력을 공유한다
(변인 통제). 실행에는 ollama 서버(gemma4:31b)가 떠 있어야 한다.

생성(gemma4:31b)을 모두 끝낸 뒤 채점(gemma3:27b)을 별도 패스로 돌린다.
이렇게 두 단계로 나눠 매 런마다 모델을 번갈아 로드하는 스래싱을 없앤다
(ollama 안정성·속도 향상). 런 단위 재시도/계속으로 일시적 연결 끊김에도
실험 전체가 죽지 않는다.

사용 예:
    # 스모크: code 구조로 1챕터 1회만
    python -m experiments.run_experiment --orch code --limit 1 --repeat 1

    # 본 실험: 세 구조, 1챕터, 각 20회 + 채점
    python -m experiments.run_experiment --orch all --limit 1 --repeat 20 \
        --judge --task datasets/structured.json

결과: results/<slug>/runs.jsonl (원시) + summary.json (집계) + drafts/ (산출물)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

# orchestrators import 시 _bootstrap 가 testbed 를 sys.path 에 추가한다.
from orchestrators import REGISTRY, Result
from experiments._summary import summarize

from agent.design import run_or_load_design          # testbed
from core.grounding import read_source               # testbed
from core.config import QUALITY_GATE, TARGET_SCORE, MIN_CHARS  # testbed

ROOT = Path(__file__).resolve().parent.parent
_SKIP_KEYS = {"chapters", "source", "visuals"}
RUN_RETRIES = 3          # 런 1개당 일시적 오류 재시도 횟수
RETRY_SLEEP = 20         # 재시도 전 대기(초) — ollama 회복 시간


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


async def _run_with_retry(orch, ch, base_state, label: str):
    """런 1개를 재시도 포함 실행. 끝까지 실패하면 (None, error_str)."""
    last = None
    for attempt in range(1, RUN_RETRIES + 1):
        try:
            return await orch.run(ch, base_state), None
        except Exception as e:                       # 일시적 ollama 끊김 등
            last = f"{type(e).__name__}: {e}"
            print(f"    [재시도 {attempt}/{RUN_RETRIES}] {label} 실패: {last[:120]}", flush=True)
            if attempt < RUN_RETRIES:
                await asyncio.sleep(RETRY_SLEEP)
    return None, last


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

    drafts_dir = out_dir / "drafts"
    drafts_dir.mkdir(exist_ok=True)
    # 채점 패스(run_judge)가 쓸 config 저장
    (out_dir / "meta.json").write_text(
        json.dumps({"task": slug, "config": base_state["config"]},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    runs_path = out_dir / "runs.jsonl"
    rows: list[dict] = []
    t_all = time.perf_counter()

    # ---- 1단계: 생성 패스 (gemma4:31b만 사용 — 모델 스왑 없음) ----
    with runs_path.open("a", encoding="utf-8") as fp:
        for name in which:
            orch = REGISTRY[name]()
            for ch in chapters:
                num = ch.get("number", "?")
                for rep in range(args.repeat):
                    label = f"{name} ch{num} rep{rep+1}/{args.repeat}"
                    print(f"  - {label} ...", flush=True)
                    res, err = await _run_with_retry(orch, ch, base_state, label)
                    if err:                              # 끝까지 실패 → 기록하고 계속
                        row = {"orchestrator": name, "chapter": num, "repeat": rep,
                               "error": err}
                        rows.append(row)
                        fp.write(json.dumps(row, ensure_ascii=False) + "\n"); fp.flush()
                        print(f"    ✗ 실패(건너뜀): {err[:100]}", flush=True)
                        continue
                    res: Result
                    draft_file = f"drafts/{name}__ch{num}__rep{rep}.md"
                    (out_dir / draft_file).write_text(res.draft, encoding="utf-8")
                    row = {
                        "orchestrator": res.orchestrator,
                        "chapter": num, "repeat": rep,
                        "chapter_obj": {k: ch.get(k) for k in ("number", "title", "description")},
                        "draft_file": draft_file,
                        "elapsed_sec": res.elapsed_sec,
                        "tokens": res.tokens,
                        "token_detail": res.token_detail,
                        "best_score": res.best_score,
                        "chars": res.chars,
                        "write_count": res.write_count,
                        "pass_count": res.pass_count,
                        "retry_count": res.retry_count,
                    }
                    rows.append(row)
                    fp.write(json.dumps(row, ensure_ascii=False) + "\n"); fp.flush()
                    print(f"    → {res.elapsed_sec}s, score={res.best_score}, "
                          f"tokens={res.tokens}, chars={res.chars}")

    summary = {"task": slug, "chapters": [c.get("number") for c in chapters],
               "repeat": args.repeat, "by_orchestrator": summarize(rows)}
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[생성 완료] {time.perf_counter()-t_all:.0f}s | runs → {runs_path}")

    # ---- 2단계: 채점 패스 (gemma3:27b만 로드 — 스왑 1회) ----
    if args.judge:
        print("\n[채점 패스 시작] 생성 끝 → 별도 모델로 채점")
        from experiments.run_judge import judge_pass
        rows = judge_pass(out_dir)

    print(f"\n[완료] summary → {out_dir/'summary.json'}")
    print(json.dumps(summarize(rows), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

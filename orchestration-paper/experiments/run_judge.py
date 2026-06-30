"""채점 패스 — 생성과 분리된 LLM-as-Judge.

생성(gemma4:31b)을 모두 끝낸 뒤 별도로 실행한다. 이렇게 하면 매 런마다
생성↔채점 모델을 번갈아 로드하는 스래싱이 사라져 ollama가 안정적이고
빠르다(모델 스왑 1회). 재실행 가능: 이미 채점된 행은 건너뛴다.

사용:
    python -m experiments.run_judge --out results/<slug>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.judge import judge, JUDGE_MODEL
from experiments._summary import summarize

ROOT = Path(__file__).resolve().parent.parent


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


def judge_pass(out_dir: Path, model: str = JUDGE_MODEL, samples: int | None = None) -> list[dict]:
    """out_dir/runs.jsonl 의 각 행을 채점해 judge_score 를 채운다(in-place 갱신)."""
    runs_path = out_dir / "runs.jsonl"
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    config = meta["config"]
    rows = _read_jsonl(runs_path)

    todo = [r for r in rows if not r.get("error") and "judge_score" not in r]
    print(f"[judge] 대상 {len(todo)}/{len(rows)}행 | 모델 {model}")
    for i, r in enumerate(todo, 1):
        draft = (out_dir / r["draft_file"]).read_text(encoding="utf-8") if r.get("draft_file") else ""
        chapter = r.get("chapter_obj") or {"number": r.get("chapter")}
        kw = {"model": model} if model else {}
        if samples:
            kw["samples"] = samples
        jr = judge(draft, chapter, config, **kw)
        r["judge_score"] = jr["score"]
        r["judge_detail"] = jr
        _write_jsonl(runs_path, rows)            # 매 행 후 저장(크래시 안전)
        print(f"  {i}/{len(todo)} {r['orchestrator']} ch{r.get('chapter')} rep{r.get('repeat')}"
              f" → judge {jr['score']}")

    # summary 갱신
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8")) \
        if (out_dir / "summary.json").exists() else {}
    summary["by_orchestrator"] = summarize(rows)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="결과 폴더 (results/<slug>)")
    ap.add_argument("--model", default=JUDGE_MODEL, help="채점 모델(기본 gemma3:27b)")
    ap.add_argument("--samples", type=int, default=None, help="행당 채점 반복(기본 환경값)")
    args = ap.parse_args()
    out_dir = Path(args.out) if Path(args.out).is_absolute() else ROOT / args.out
    rows = judge_pass(out_dir, model=args.model, samples=args.samples)
    print(f"[완료] {out_dir/'summary.json'}")
    print(json.dumps(summarize(rows), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

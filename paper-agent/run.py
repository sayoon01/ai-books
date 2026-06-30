"""
CLI 진입점 — 입력 spec 으로 논문 한 편을 설계→집필→검수→수정→조립.

사용:
    python run.py --input inputs/orchestration.json
    python run.py --input inputs/orchestration.json --force        # plan 재생성
    python run.py --input inputs/orchestration.json --limit 2       # 앞 2섹션만(스모크)
    python run.py --input inputs/orchestration.json --plan-only     # 설계만

출력: output/<slug>/ {plan.json, sections/*.tex, tables/, figures/, main.tex, logs/run.json}
빌드: cd output/<slug> && pdflatex main && pdflatex main
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import OUTPUT_ROOT
from core.grounding import read_source
from agents.plan import run_or_load_plan
from orchestrator import run_paper
from assemble import assemble


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="입력 spec json (slug/topic/venue/source)")
    ap.add_argument("--force", action="store_true", help="plan.json 무시하고 재설계")
    ap.add_argument("--limit", type=int, default=0, help="앞 N개 섹션만(0=전체)")
    ap.add_argument("--plan-only", action="store_true", help="설계(plan.json)만 생성")
    args = ap.parse_args()

    spec = json.loads(Path(args.input).read_text(encoding="utf-8"))
    out = OUTPUT_ROOT / spec["slug"]

    if args.plan_only:
        src = read_source(spec.get("source"), spec["slug"])
        plan = run_or_load_plan(spec["topic"], src, out,
                                venue=spec.get("venue", ""), force=args.force)
        print(f"\nplan.json → {out/'plan.json'}")
        print("제목:", plan["title"])
        print("섹션:", [s["id"] for s in plan["sections"]])
        return

    result = run_paper(spec, force=args.force, limit=args.limit)
    tex = assemble(result)
    print(f"\nmain.tex → {tex}")
    print(f"빌드: cd {result['out']} && pdflatex main && pdflatex main")


if __name__ == "__main__":
    main()

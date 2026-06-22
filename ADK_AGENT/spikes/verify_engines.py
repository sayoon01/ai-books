"""
검증 — 같은 챕터를 graph 엔진과 agent 엔진으로 각각 돌려 산출 state 키를 비교.
(graph 회귀 무손상 + agent 엔진 동작 + 같은 스키마 동시 확인)

실행: .venv/bin/python spikes/verify_engines.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.adk.runners import InMemoryRunner
from google.genai import types

from pipeline import _config, _build_chapter_runtime
from core.config import MIN_CHARS, QUALITY_GATE, TARGET_SCORE
from core.grounding import read_source
from agent.design import run_or_load_design

DOC = Path("toc/mold-dx-auto.json")
OUT = Path("output/금형-사출-센서-데이터-자동-해석-가이드")
_GO = types.Content(role="user", parts=[types.Part(text="go")])


async def run_one(engine: str, base: dict, ch: dict) -> dict:
    runner = InMemoryRunner(agent=_build_chapter_runtime(engine), app_name="adk_book")
    sess = await runner.session_service.create_session(
        app_name="adk_book", user_id="u",
        state={**base, "chapter": ch, "prev_summaries": [],
               "last_score": -1, "best_score": -1, "write_count": 0,
               "pass_count": 0, "history": []})
    async for _ in runner.run_async(user_id="u", session_id=sess.id, new_message=_GO):
        pass
    st = (await runner.session_service.get_session(
        app_name="adk_book", user_id="u", session_id=sess.id)).state
    final = st.get("best_draft") or st.get("draft", "")
    stages = [h.get("stage") for h in st.get("history", [])]
    return {"engine": engine, "final_chars": len(final),
            "best_score": st.get("best_score"), "pass_count": st.get("pass_count"),
            "write_count": st.get("write_count"), "flagged": st.get("flagged", False),
            "has_review": bool(st.get("review") or st.get("best_review")),
            "history_stages": stages}


async def main():
    doc = json.loads(DOC.read_text(encoding="utf-8"))
    config = _config(doc)
    design = run_or_load_design({**config}, read_source(doc.get("source"), "verify"), OUT)
    ch = design["chapters"][0]
    base = {"config": config, "write_brief": design["write_brief"],
            "grounding": design.get("grounding_digest", ""),
            "min_chars": MIN_CHARS, "quality_gate": QUALITY_GATE, "target_score": TARGET_SCORE}
    print(f"대상 챕터: {ch['title']}\n")

    for engine in ("graph", "agent"):
        print(f"--- {engine} 엔진 실행 ---")
        r = await run_one(engine, base, ch)
        print(json.dumps(r, ensure_ascii=False), "\n")

    print("판정 기준: 두 엔진 모두 final_chars≥%d, has_review=True, history에 write/review/gate 존재" % MIN_CHARS)


if __name__ == "__main__":
    asyncio.run(main())

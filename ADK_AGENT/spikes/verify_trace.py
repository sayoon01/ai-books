"""트레이싱 검증 — 캐시된 design 으로 1챕터만 그래프 실행 → Phoenix/Langfuse 전송 확인용.
실행: .venv/bin/python spikes/verify_trace.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # 프로젝트 루트

from google.adk.runners import InMemoryRunner

from pipeline import _config, _GO
from agent.graph import build_chapter_graph
from core.config import MIN_CHARS, QUALITY_GATE, TARGET_SCORE
from core.tracing import setup_tracing, flush_tracing

DOC = Path("toc/mold-dx-auto.json")
DESIGN = Path("output/금형-사출-센서-데이터-자동-해석-가이드/design.json")


async def main():
    on = setup_tracing(run_name="verify-trace")
    print("tracing_on:", on)

    doc = json.loads(DOC.read_text(encoding="utf-8"))
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    config = _config(doc)
    ch = design["chapters"][0]
    print("대상 챕터:", ch["title"])

    from google.adk.plugins.auto_tracing_plugin import AutoTracingPlugin
    plugins = [AutoTracingPlugin(extra_scope_prefixes=("agent.", "core.", "pipeline"))] if on else []
    runner = InMemoryRunner(agent=build_chapter_graph(), app_name="adk_book", plugins=plugins)

    base = {"config": config, "write_brief": design["write_brief"],
            "grounding": design.get("grounding_digest", ""),
            "min_chars": MIN_CHARS, "quality_gate": QUALITY_GATE, "target_score": TARGET_SCORE}
    sess = await runner.session_service.create_session(
        app_name="adk_book", user_id="u",
        state={**base, "chapter": ch, "prev_summaries": [],
               "last_score": -1, "best_score": -1, "write_count": 0,
               "pass_count": 0, "history": []})

    from google.adk.telemetry import tracer
    with tracer.start_as_current_span(f"chapter-{ch.get('number',1)}: {ch['title']}"):
        async for _ in runner.run_async(user_id="u", session_id=sess.id, new_message=_GO):
            pass

    flush_tracing()
    print("=== 1챕터 실행 + flush 완료 ===")


if __name__ == "__main__":
    asyncio.run(main())

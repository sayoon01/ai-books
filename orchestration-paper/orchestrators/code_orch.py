"""Code Orchestration — 흐름이 코드에 고정된 구조.

벤더링된 testbed의 Workflow 그래프(agent/graph.py)를 그대로 사용한다.
다음 단계 전이를 코드(엣지·게이트)가 결정한다. 이 어댑터는 그래프를
1챕터 실행하고 지표를 뽑아 Result로 반환하는 얇은 래퍼다.
"""
from __future__ import annotations

import time

from . import _bootstrap  # noqa: F401  (testbed를 sys.path에 추가)

from google.adk.runners import InMemoryRunner

from agent.graph import build_chapter_graph  # testbed
from core.usage import METER                 # testbed: 직접 ollama 호출 토큰
from .base import Orchestrator, Result, initial_state
from ._adk import _GO, event_tokens


class CodeOrchestrator(Orchestrator):
    name = "code"

    def __init__(self) -> None:
        self._root = build_chapter_graph()

    async def run(self, chapter, base_state) -> Result:
        runner = InMemoryRunner(agent=self._root, app_name="exp_code")
        sess = await runner.session_service.create_session(
            app_name="exp_code", user_id="u",
            state=initial_state(base_state, chapter,
                                base_state.get("prev_summaries")),
        )

        METER.reset()                          # 직접 ollama 호출(review 등) 토큰 측정 시작
        ev_prompt = ev_completion = 0
        t0 = time.perf_counter()
        async for ev in runner.run_async(user_id="u", session_id=sess.id, new_message=_GO):
            p, c = event_tokens(ev)            # LlmAgent(write/revise) 토큰
            ev_prompt += p
            ev_completion += c
        elapsed = time.perf_counter() - t0
        direct = METER.snapshot()

        st = (await runner.session_service.get_session(
            app_name="exp_code", user_id="u", session_id=sess.id)).state

        prompt_tok = direct.prompt + ev_prompt
        completion_tok = direct.completion + ev_completion
        final = st.get("best_draft") or st.get("draft", "") or ""
        return Result(
            orchestrator=self.name,
            draft=final,
            elapsed_sec=round(elapsed, 2),
            write_count=st.get("write_count") or 0,
            pass_count=st.get("pass_count") or 0,
            best_score=st.get("best_score"),
            tokens=prompt_tok + completion_tok,
            token_detail={
                "prompt": prompt_tok, "completion": completion_tok,
                "direct": direct.total, "event": ev_prompt + ev_completion,
                "direct_calls": direct.calls,
            },
            chars=len(final),
            history=st.get("history", []),
        )

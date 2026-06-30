"""오케스트레이터 공용 ADK 헬퍼.

- _GO            : ADK 러너 트리거 메시지
- event_tokens() : 이벤트에서 (prompt, completion) 토큰 추출
- run_single_agent() : LlmAgent 하나를 1회 실행하고 output(draft)+토큰 반환
"""
from __future__ import annotations

from . import _bootstrap  # noqa: F401  (testbed를 sys.path에 추가)

from google.genai import types
from google.adk.runners import InMemoryRunner

_GO = types.Content(role="user", parts=[types.Part(text="go")])


def event_tokens(ev) -> tuple[int, int]:
    """ADK 이벤트에서 (prompt, completion) 토큰. 없으면 (0,0).

    부분(partial) 스트리밍 이벤트는 누적 중복을 피해 제외한다.
    """
    if getattr(ev, "partial", False):
        return 0, 0
    um = getattr(ev, "usage_metadata", None)
    if um is None:
        return 0, 0
    return (getattr(um, "prompt_token_count", 0) or 0,
            getattr(um, "candidates_token_count", 0) or 0)


async def run_single_agent(agent, state: dict, app_name: str = "exp") -> tuple[str, int, int]:
    """LlmAgent(write/revise 등) 하나를 주어진 state로 1회 실행한다.

    반환: (output_key="draft" 결과, prompt_tokens, completion_tokens)
    각 호출마다 새 세션을 state 스냅샷으로 시드한다(흐름 제어는 호출부가 담당).
    """
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    sess = await runner.session_service.create_session(
        app_name=app_name, user_id="u", state=dict(state))
    ev_p = ev_c = 0
    async for ev in runner.run_async(user_id="u", session_id=sess.id, new_message=_GO):
        p, c = event_tokens(ev)
        ev_p += p
        ev_c += c
    st = (await runner.session_service.get_session(
        app_name=app_name, user_id="u", session_id=sess.id)).state
    return st.get("draft", "") or "", ev_p, ev_c

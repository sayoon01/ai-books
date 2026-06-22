"""
스파이크 — gemma LlmAgent 가 classic SequentialAgent / LoopAgent 의 sub_agent 로
output_key 로 state 를 채우고, 루프에서 재실행 시 덮어쓰는지 검증. (짧은 LLM 호출)

실행: .venv/bin/python spikes/spike_llmagent_compose.py
"""
import asyncio
import sys
from pathlib import Path
from typing import AsyncGenerator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.adk.agents import LlmAgent, SequentialAgent, LoopAgent, BaseAgent
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.runners import InMemoryRunner
from google.genai import types

from core.llm import make_gemma

_GO = types.Content(role="user", parts=[types.Part(text="go")])


def writer(name="w"):
    return LlmAgent(name=name, model=make_gemma(0.8),
                    instruction="한국어로 인사말 한 문장만 출력해라. 설명 없이.",
                    output_key="draft")


class CountGate(BaseAgent):
    """루프 강제 2회: 2회 미만이면 통과, 도달하면 escalate. (재실행 덮어쓰기 확인용)"""
    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        n = ctx.session.state.get("n", 0) + 1
        yield Event(invocation_id=ctx.invocation_id, author=self.name,
                    actions=EventActions(escalate=(n >= 2), state_delta={"n": n}))


async def get_state(runner, sess):
    return (await runner.session_service.get_session(
        app_name="spike", user_id="u", session_id=sess.id)).state


async def main():
    # 1) SequentialAgent 안에서 LlmAgent.output_key 가 state 를 채우나
    flow = SequentialAgent(name="s", sub_agents=[writer()])
    runner = InMemoryRunner(agent=flow, app_name="spike")
    sess = await runner.session_service.create_session(app_name="spike", user_id="u", state={})
    async for _ in runner.run_async(user_id="u", session_id=sess.id, new_message=_GO):
        pass
    d1 = (await get_state(runner, sess)).get("draft", "")
    ok1 = bool(d1.strip())
    print(f"[1] Sequential→draft 채움: {'PASS' if ok1 else 'FAIL'}  (len={len(d1)}) {d1[:40]!r}")

    # 2) LoopAgent 에서 writer 가 2회 재실행되며 draft 를 덮어쓰나(에러 없이)
    loop = LoopAgent(name="L", sub_agents=[writer("w2"), CountGate(name="g")], max_iterations=5)
    runner2 = InMemoryRunner(agent=loop, app_name="spike")
    sess2 = await runner2.session_service.create_session(app_name="spike", user_id="u", state={})
    async for _ in runner2.run_async(user_id="u", session_id=sess2.id, new_message=_GO):
        pass
    st2 = await get_state(runner2, sess2)
    d2, n2 = st2.get("draft", ""), st2.get("n")
    ok2 = bool(d2.strip()) and n2 == 2
    print(f"[2] Loop 재실행 덮어쓰기: {'PASS' if ok2 else 'FAIL'}  (n={n2}, len={len(d2)})")

    print("\n전체:", "✅ ALL PASS" if (ok1 and ok2) else "❌ 일부 실패")


if __name__ == "__main__":
    asyncio.run(main())

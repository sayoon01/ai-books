"""
스파이크 — LoopAgent + escalate(커스텀 gate) 메커니즘 검증. LLM 없이 빠르게.

검증 목표(§A 멀티에이전트 채택안의 핵심 미지수):
  1) 커스텀 BaseAgent 가 EventActions(escalate=True) 를 내면 LoopAgent 가 즉시 종료하는가
  2) escalate 안 나면 max_iterations 에서 안전 종료하는가
  3) 자식 간 state 공유(한 자식이 쓴 값을 다음 자식이 읽음)가 되는가
  4) SequentialAgent[..., LoopAgent[...]] 합성이 도는가

실행: .venv/bin/python spikes/spike_loop_escalate.py
"""
import asyncio
import sys
from pathlib import Path
from typing import AsyncGenerator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.adk.agents import BaseAgent, LoopAgent, SequentialAgent
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.runners import InMemoryRunner
from google.genai import types

GATE = 80
_GO = types.Content(role="user", parts=[types.Part(text="go")])


class ScoreStep(BaseAgent):
    """검수가 수정 후 점수를 올리는 걸 흉내 — 매 반복 score += inc."""
    inc: int = 40

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        score = ctx.session.state.get("score", 0) + self.inc
        loops = ctx.session.state.get("loops", 0) + 1
        ctx.session.state["score"] = score              # 즉시 가시화(같은 반복의 gate가 읽음)
        # state_delta 로 내야 최종 세션에 영속된다(직접 대입은 영속 안 됨 — 스파이크로 확인).
        yield Event(invocation_id=ctx.invocation_id, author=self.name,
                    actions=EventActions(state_delta={"score": score, "loops": loops}))


class Gate(BaseAgent):
    """score >= GATE 이면 escalate(루프 종료). 아니면 통과(계속)."""
    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        passed = ctx.session.state.get("score", 0) >= GATE
        yield Event(invocation_id=ctx.invocation_id, author=self.name,
                    actions=EventActions(escalate=passed, state_delta={"passed": passed}))


async def run_case(label: str, inc: int, max_iter: int) -> dict:
    loop = LoopAgent(name="refine",
                     sub_agents=[ScoreStep(name="step", inc=inc), Gate(name="gate")],
                     max_iterations=max_iter)
    flow = SequentialAgent(name="chapter", sub_agents=[loop])   # 합성 검증
    runner = InMemoryRunner(agent=flow, app_name="spike")
    sess = await runner.session_service.create_session(
        app_name="spike", user_id="u", state={"score": 0})
    async for _ in runner.run_async(user_id="u", session_id=sess.id, new_message=_GO):
        pass
    st = (await runner.session_service.get_session(
        app_name="spike", user_id="u", session_id=sess.id)).state
    r = {"loops": st.get("loops"), "score": st.get("score"), "passed": st.get("passed", False)}
    print(f"[{label}] inc={inc} max_iter={max_iter} → {r}")
    return r


async def main():
    print("=== 케이스 1: 도달 가능(inc=40) — 2회째 80점에서 escalate 종료 기대 ===")
    c1 = await run_case("reachable", inc=40, max_iter=10)
    print("=== 케이스 2: 도달 불가(inc=5) — max_iter=3 에서 안전 종료 기대 ===")
    c2 = await run_case("unreachable", inc=5, max_iter=3)

    print("\n=== 판정 ===")
    ok1 = c1["loops"] == 2 and c1["passed"] is True            # escalate 조기 종료
    ok2 = c2["loops"] == 3 and c2["passed"] is False           # max_iter 안전 종료
    ok3 = c1["score"] == 80 and c2["score"] == 15              # state 공유(누적)
    print(f"  1) escalate 조기 종료(2회): {'PASS' if ok1 else 'FAIL'}  {c1}")
    print(f"  2) max_iter 안전 종료(3회): {'PASS' if ok2 else 'FAIL'}  {c2}")
    print(f"  3) state 공유 누적:          {'PASS' if ok3 else 'FAIL'}")
    print("\n전체:", "✅ ALL PASS" if (ok1 and ok2 and ok3) else "❌ 일부 실패")


if __name__ == "__main__":
    asyncio.run(main())

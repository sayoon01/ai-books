"""
S2: LoopAgent 의 escalate 동작 검증 (LLM 없이, BaseAgent 만으로).

확인 목표(설계 refine_loop 의 핵심 가정):
  LoopAgent[ A -> Gate(escalate) -> B ] 에서
  - Gate 가 escalate=True 를 내면:
      (1) 같은 iteration 의 뒤 agent B 가 스킵되는가?
      (2) 루프가 즉시 종료되는가?
  - escalate=False 면 A->Gate->B 가 끝까지 돌고 다음 iteration 으로 가는가?

기대(설계 전제): iter1 에서 A, Gate 만 실행되고 B 는 안 보여야 escalate-skip 가정이 맞음.
실행: .venv/bin/python spikes/s2_escalate.py
"""
import asyncio

from google.adk.agents import LoopAgent, BaseAgent
from google.adk.events import Event, EventActions
from google.adk.runners import InMemoryRunner
from google.genai import types

TRACE = []


class Marker(BaseAgent):
    """실행되면 자기 이름을 TRACE 에 남기는 더미 agent."""
    async def _run_async_impl(self, ctx):
        TRACE.append(self.name)
        yield Event(author=self.name)


class Gate(BaseAgent):
    """첫 호출에서 바로 escalate=True 를 낸다 (= '깨끗' 케이스 모사)."""
    async def _run_async_impl(self, ctx):
        TRACE.append("gate(escalate=True)")
        yield Event(author=self.name, actions=EventActions(escalate=True))


loop = LoopAgent(
    name="refine",
    max_iterations=3,
    sub_agents=[Marker(name="A_review"), Gate(name="gate"), Marker(name="B_revise")],
)


async def main():
    runner = InMemoryRunner(agent=loop, app_name="s2")
    sess = await runner.session_service.create_session(app_name="s2", user_id="u")
    msg = types.Content(role="user", parts=[types.Part(text="go")])
    async for _ in runner.run_async(user_id="u", session_id=sess.id, new_message=msg):
        pass

    print("실행 순서:", TRACE)
    skipped_B = "B_revise" not in TRACE
    one_iter = TRACE.count("A_review") == 1
    print(f"  뒤 agent(B_revise) 스킵됐나? {skipped_B}")
    print(f"  루프 1회만 돌았나(A_review 1번)? {one_iter}")
    print("RESULT:", "PASS (escalate가 뒤 agent 스킵 + 루프 종료)"
          if skipped_B and one_iter else "FAIL (설계 가정과 다름)")


if __name__ == "__main__":
    asyncio.run(main())

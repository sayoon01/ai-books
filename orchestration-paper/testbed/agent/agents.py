"""
멀티 에이전트 엔진(§A) — 챕터 파이프라인을 ADK 표준 SequentialAgent/LoopAgent 로 구성.

그래프 엔진(agent/graph.py)과 동일한 흐름·품질 게이트·keep-best 를 '코드 오케스트레이션'으로
다시 표현한다. 결정 로직은 write.py/review.py 의 순수 함수(length_decision/do_review/gate_decision)를
**공유**(단일 출처). writer/reviser 는 그래프와 같은 LlmAgent(build_write_node/build_revise_node).

구조(챕터 1개):
    SequentialAgent[
        LoopAgent("draft",  [writer, length_gate],            max=WRITE_MAX)     # 길이 충족까지 재작성
        LoopAgent("refine", [reviewer, gate, reviser],         max=PASS_MAX+2)    # 통과/수용까지 수정
    ]
escalate 규칙(스파이크 검증):
  - length_gate: 길이 ok 면 escalate → draft 루프 종료(부모 Sequential 은 안 멈춤, refine 으로 진행).
  - gate: 게이트 stop(완료/수용)이면 escalate → refine 루프 종료(reviser 건너뜀).
  - ⚠️ 커스텀 에이전트의 state 변경은 EventActions(state_delta=...) 로만 영속(직접 대입은 휘발).
"""
from typing import AsyncGenerator

from google.adk.agents import BaseAgent, SequentialAgent, LoopAgent
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions

from core.config import WRITE_MAX, PASS_MAX
from agent.write import build_write_node, length_decision
from agent.review import do_review, gate_decision
from agent.revise import build_revise_node


def _history(ctx, **entry) -> list:
    """현재 history 에 항목 하나 추가한 새 리스트(state_delta 로 내보낼 용)."""
    return ctx.session.state.get("history", []) + [entry]


class LengthGate(BaseAgent):
    """길이 가드 — len≥MIN(또는 상한 소진)이면 escalate. (그래프 length_guard 대응)"""

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        s = ctx.session.state
        route, updates, chars = length_decision(s)
        if route == "rewrite":
            print(f"    [가드] 본문 {chars}자 < {s['min_chars']} → 재작성({updates['write_count']}/{WRITE_MAX})")
        elif updates.get("flagged"):
            print(f"    [가드] 끝까지 {chars}자 — flagged 후 진행")
        delta = {**updates, "history": _history(
            ctx, stage="write", attempt=updates["write_count"], chars=chars,
            route=route, draft=s.get("draft", ""))}
        yield Event(invocation_id=ctx.invocation_id, author=self.name,
                    actions=EventActions(escalate=(route == "ok"), state_delta=delta))


class Reviewer(BaseAgent):
    """구조화 검수 + keep-best. (그래프 review_fn 대응) escalate 안 함 — 판정은 Gate."""

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        s = ctx.session.state
        updates, err = do_review(s)
        if err:
            print(f"    [검수 미수렴] {err} — flagged 후 종료")
            hist = _history(ctx, stage="review", error=err, reviewed_draft=s.get("draft", ""))
        else:
            r = updates["review"]
            print(f"    [검수] score {r['score']} · issues {len(r['issues'])} · "
                  f"needs_revision {r['needs_revision']} · best {updates.get('best_score', s.get('best_score'))}")
            hist = _history(ctx, stage="review", reviewed_draft=s.get("draft", ""), review=r)
        yield Event(invocation_id=ctx.invocation_id, author=self.name,
                    actions=EventActions(state_delta={**updates, "history": hist}))


class Gate(BaseAgent):
    """게이트 판정 — stop(완료/수용)이면 escalate, 아니면 통과(→reviser). (그래프 gate_fn 대응)"""

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        s = ctx.session.state
        stop, info, updates = gate_decision(s)
        if stop:
            print(f"    [게이트] 종료 — {info['kind']} (score {info['score']}, 위반 {info['violations']})")
        else:
            print(f"    [게이트] 재수정({info['kind']}) 위반 {info['violations']} · 약한축 {list(info['weak'])}")
        delta = {**updates, "history": _history(
            ctx, stage="gate", route=("done" if stop else "revise"), decision=info["kind"],
            score=info["score"], pass_count=updates.get("pass_count"),
            violations=info["violations"], weak_axes=info["weak"], unverified=info["unverified"])}
        yield Event(invocation_id=ctx.invocation_id, author=self.name,
                    actions=EventActions(escalate=stop, state_delta=delta))


def build_chapter_agent() -> SequentialAgent:
    """챕터 1개 처리 합성 에이전트. graph 엔진의 build_chapter_graph() 와 같은 흐름/상태 키 산출."""
    draft_loop = LoopAgent(
        name="draft",
        sub_agents=[build_write_node(), LengthGate(name="length_gate")],
        max_iterations=WRITE_MAX)
    refine_loop = LoopAgent(
        name="refine",
        sub_agents=[Reviewer(name="review"), Gate(name="gate"), build_revise_node()],
        max_iterations=PASS_MAX + 2)        # gate(pass_count>PASS_MAX)가 1차 종료, max 는 안전 backstop
    return SequentialAgent(name="chapter", sub_agents=[draft_loop, refine_loop])

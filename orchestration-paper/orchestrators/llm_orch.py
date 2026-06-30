"""LLM Orchestration — 다음 동작을 LLM이 결정하는 구조.

핵심 원칙(변인 통제): 실제 '작업'(작성/검토/수정)은 Code 구조와 **완전히
동일한** 구현을 재사용한다.
  - write  : testbed build_write_node() (동일 LlmAgent·프롬프트·온도)
  - review : testbed do_review() (동일 검수 함수)
  - revise : testbed build_revise_node() (동일 LlmAgent·프롬프트·온도)
오직 '다음에 무엇을 할지'만 코드(고정 엣지) 대신 **라우터 LLM**이 정한다.

라우터 LLM 호출의 토큰도 합산된다(LLM 구조의 비용·지연 특성을 반영).
무한 루프 방지를 위한 안전 상한(MAX_STEPS)만 코드로 둔다.
"""
from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel

from . import _bootstrap  # noqa: F401
from core.usage import METER                       # testbed
from core.llm import call_structured               # testbed: 라우터 LLM 호출
from agent.write import build_write_node, length_decision  # testbed
from agent.revise import build_revise_node         # testbed
from agent.review import do_review                  # testbed
from .base import Orchestrator, Result, initial_state
from ._adk import run_single_agent

# 안전 상한 — 라우터가 종료를 못 정해도 멈춘다(흐름 제어가 아니라 안전장치).
MAX_STEPS = 12


class RouteDecision(BaseModel):
    """라우터 LLM의 출력 스키마."""
    action: Literal["write", "review", "revise", "finish"]
    reason: str


ROUTER_SYSTEM = """
당신은 문서 생성 멀티 에이전트의 오케스트레이터입니다. 사용할 수 있는 에이전트는
- write  : 초안을 새로 작성(아직 초안이 없을 때 필수)
- review : 현재 초안을 검수해 점수와 문제점을 산출
- revise : 검수 결과를 반영해 초안을 수정
- finish : 충분히 좋으면 종료
목표는 '최소한의 호출로 충분히 좋은 챕터'를 완성하는 것입니다. 현재 상태를 보고
다음에 호출할 단 하나의 에이전트를 고르세요. 초안이 없으면 write, 검수가 없으면 review,
문제가 남아 있으면 revise, 품질이 목표에 도달했으면 finish 를 선택하세요.
출력은 제공된 JSON 스키마(action, reason)를 정확히 따르세요.
"""


def _router_user(state: dict) -> str:
    review = state.get("review") or {}
    has_draft = bool(state.get("draft"))
    return f"""
[현재 상태]
- 초안 있음: {has_draft} (글자수 {len(state.get('draft','') or '')})
- 최근 검수 점수: {review.get('score', '없음')}
- 검수 needs_revision: {review.get('needs_revision', '없음')}
- 검수 이슈 수: {len(review.get('issues', []))}
- 작성 횟수: {state.get('write_count', 0)} / 검수 횟수: {state.get('pass_count', 0)}
- 목표 점수: {state.get('target_score')} / 품질 게이트: {state.get('quality_gate')}
다음에 호출할 에이전트를 고르세요.
"""


class LlmOrchestrator(Orchestrator):
    name = "llm"

    def __init__(self) -> None:
        self._writer = build_write_node()
        self._reviser = build_revise_node()

    async def run(self, chapter, base_state) -> Result:
        state = initial_state(base_state, chapter, base_state.get("prev_summaries"))

        METER.reset()                              # 직접 호출(라우터+review) 토큰
        ev_prompt = ev_completion = 0
        trace: list[dict] = []
        t0 = time.perf_counter()

        for step in range(MAX_STEPS):
            decision = call_structured(
                ROUTER_SYSTEM, _router_user(state), RouteDecision, temperature=0.0)
            action = decision.action

            # 불가능한 선택 보정(최소한의 안전 보정 — 흐름 결정 자체는 LLM)
            if action in ("review", "revise", "finish") and not state.get("draft"):
                action = "write"
            if action == "revise" and not state.get("review"):
                action = "review"

            if action == "finish":
                trace.append({"step": step, "action": "finish", "reason": decision.reason})
                break

            if action == "write":
                draft, p, c = await run_single_agent(self._writer, state, "exp_llm")
                ev_prompt += p
                ev_completion += c
                state["draft"] = draft
                _, updates, chars = length_decision(state)   # write_count·flagged 갱신(지표용)
                state.update(updates)
                trace.append({"step": step, "action": "write", "chars": chars})

            elif action == "review":
                updates, err = do_review(state)
                state.update(updates)
                state["pass_count"] = state.get("pass_count", 0) + 1
                trace.append({"step": step, "action": "review",
                              "score": (updates.get("review") or {}).get("score"),
                              "error": err})

            elif action == "revise":
                draft, p, c = await run_single_agent(self._reviser, state, "exp_llm")
                ev_prompt += p
                ev_completion += c
                state["draft"] = draft
                trace.append({"step": step, "action": "revise"})

        elapsed = time.perf_counter() - t0
        direct = METER.snapshot()

        prompt_tok = direct.prompt + ev_prompt
        completion_tok = direct.completion + ev_completion
        final = state.get("best_draft") or state.get("draft", "") or ""
        return Result(
            orchestrator=self.name,
            draft=final,
            elapsed_sec=round(elapsed, 2),
            write_count=state.get("write_count") or 0,
            pass_count=state.get("pass_count") or 0,
            best_score=state.get("best_score"),
            tokens=prompt_tok + completion_tok,
            token_detail={
                "prompt": prompt_tok, "completion": completion_tok,
                "direct": direct.total, "event": ev_prompt + ev_completion,
                "direct_calls": direct.calls,   # 라우터+검수 호출 수
            },
            chars=len(final),
            history=trace,
        )

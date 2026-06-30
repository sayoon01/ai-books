"""Hybrid Orchestration — 큰 흐름=코드, 세부 판단=LLM.

골격(write -> 길이게이트 -> review 루프)은 Code 구조와 동일하게 코드로
고정한다. 단 하나, '재수정할지 종료할지'를 정하는 **게이트 판단**만
코드의 gate_decision() 대신 **LLM**이 내린다. 이렇게 의사결정 지점 하나만
LLM으로 옮겨 Code와 LLM의 중간 특성을 본다.

변인 통제: write/review/revise 실제 작업과 길이 게이트는 Code와 동일한
구현을 재사용한다(testbed). 달라지는 건 게이트 판단 주체뿐이다.
"""
from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel

from . import _bootstrap  # noqa: F401
from core.usage import METER                              # testbed
from core.llm import call_structured                      # testbed
from core.config import WRITE_MAX, PASS_MAX               # testbed
from agent.write import build_write_node, length_decision  # testbed
from agent.revise import build_revise_node                # testbed
from agent.review import do_review                         # testbed
from .base import Orchestrator, Result, initial_state
from ._adk import run_single_agent


class GateDecision(BaseModel):
    decision: Literal["finish", "revise"]
    reason: str


GATE_SYSTEM = """
당신은 원고 품질 게이트입니다. 검수 결과를 보고 이 초안을 그대로 종료(finish)할지,
한 번 더 수정(revise)할지 단 하나만 결정하세요. 오류·위반이 남아 있거나 품질이 목표
점수에 못 미치면 revise, 충분히 좋으면 finish 를 고르세요. 끝없이 수정하지 말고,
점수가 더 오르지 않을 것 같으면 finish 하세요. 출력은 JSON 스키마(decision, reason)를
정확히 따르세요.
"""


def _gate_user(state: dict) -> str:
    review = state.get("review") or {}
    issues = review.get("issues", [])
    return f"""
[검수 결과]
- 종합 점수: {review.get('score')}
- needs_revision: {review.get('needs_revision')}
- 이슈 수: {len(issues)} (유형: {[i.get('type') for i in issues][:8]})
- 목표 점수: {state.get('target_score')} / 품질 게이트: {state.get('quality_gate')}
- 현재까지 검수 횟수: {state.get('pass_count', 0)} (상한 {PASS_MAX})
이 초안을 finish 할지 revise 할지 결정하세요.
"""


class HybridOrchestrator(Orchestrator):
    name = "hybrid"

    def __init__(self) -> None:
        self._writer = build_write_node()
        self._reviser = build_revise_node()

    async def run(self, chapter, base_state) -> Result:
        state = initial_state(base_state, chapter, base_state.get("prev_summaries"))

        METER.reset()
        ev_prompt = ev_completion = 0
        trace: list[dict] = []
        t0 = time.perf_counter()

        # --- 1) write + 코드 길이 게이트(짧으면 재작성, 상한 WRITE_MAX) ---
        while True:
            draft, p, c = await run_single_agent(self._writer, state, "exp_hybrid")
            ev_prompt += p
            ev_completion += c
            state["draft"] = draft
            route, updates, chars = length_decision(state)   # 코드 판단
            state.update(updates)
            trace.append({"stage": "write", "attempt": state["write_count"],
                          "chars": chars, "route": route})
            if route == "ok":
                break

        # --- 2) review 루프: 코드가 돌리고, 종료/재수정 판단만 LLM ---
        for _ in range(PASS_MAX + 2):
            updates, err = do_review(state)                  # 코드(동일 검수)
            state.update(updates)
            state["pass_count"] = state.get("pass_count", 0) + 1
            review = updates.get("review") or {}
            trace.append({"stage": "review", "score": review.get("score"), "error": err})
            if err:
                break

            gate = call_structured(                          # ★ LLM 게이트 판단
                GATE_SYSTEM, _gate_user(state), GateDecision, temperature=0.0)
            trace.append({"stage": "gate", "decision": gate.decision, "reason": gate.reason})
            if gate.decision == "finish":
                break

            draft, p, c = await run_single_agent(self._reviser, state, "exp_hybrid")
            ev_prompt += p
            ev_completion += c
            state["draft"] = draft
            trace.append({"stage": "revise"})

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
                "direct_calls": direct.calls,   # 검수+게이트 LLM 호출 수
            },
            chars=len(final),
            history=trace,
        )

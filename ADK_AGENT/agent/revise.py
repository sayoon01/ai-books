"""
revise 단계 — 검수 결과를 반영해 초안을 수정(LlmAgent).

REVISE_SYSTEM(정적) + 참고/챕터 + 검수결과(review JSON) + 원문(draft)을 instruction으로
조립해 수정본을 만든다. output_key="draft" 로 기존 초안을 덮어쓴 뒤 review 로 되돌아간다.
"""
import json

from google.adk.agents import LlmAgent

from core.llm import make_gemma
from agent.prompts import REVISE_SYSTEM, ground_block, chapter_block, block


def revise_instruction(ctx) -> str:
    s = ctx.state
    return "\n".join(filter(None, [
        REVISE_SYSTEM,
        ground_block(s.get("grounding", "")),
        chapter_block(s["chapter"]),
        block("검수 결과", json.dumps(s["review"], ensure_ascii=False, indent=2)),
        block("원문", s.get("draft", "")),
    ]))


def build_revise_node() -> LlmAgent:
    return LlmAgent(name="revise", model=make_gemma(0.5),
                    instruction=revise_instruction, output_key="draft")

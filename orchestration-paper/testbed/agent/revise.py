"""
revise 단계 — 검수 결과를 반영해 초안을 수정(LlmAgent).

REVISE_SYSTEM(정적) + 참고/챕터 + 검수결과(review JSON) + 원문(draft)을 instruction으로
조립해 수정본을 만든다. output_key="draft" 로 기존 초안을 덮어쓴 뒤 review 로 되돌아간다.
"""
import json

from google.adk.agents import LlmAgent

from core.llm import make_gemma
from core.grounding import ground_block
from agent.common import chapter_block, block


# =========================
# REVISER 프롬프트 (정적)
# =========================
REVISE_SYSTEM = """
당신은 전문 원고 수정자입니다. 검수자가 발견한 문제를 반영해 원고를 더 정확하고 자연스럽게 수정합니다.
성격이 다른 두 갈래로 접근하세요.

[고침 — 오류/위반: factual_error, logical_error, missing_content, off_topic,
 unsupported_claim, source_misalignment, surface_error]
- 반드시 전부 제거하세요. 사실/논리 오류는 정확히 교정, 누락은 자연스럽게 보충,
  주제 이탈·근거 없는 단정은 덜어내거나 자료에 맞게 다시 쓰기, 자료 왜곡은 자료 핵심에 맞게 교정.
- 오타·깨진 표·잔존 LaTeX(surface_error)는 깔끔히 정리하세요.

[끌어올림 — 품질: depth/clarity/structure/persuasiveness/creativity/tone_problem, redundancy]
- 한 번에 완벽히 만들려 말고, 약한 축을 이번 패스에서 '한 단계' 끌어올리세요.
- redundancy는 중복·군더더기를 덜어 간결하게. 이미 높은 축은 망가뜨리지 말고 유지.

공통 규칙:
- review_json의 issues를 반드시 반영하세요. 문제 없는 좋은 부분은 최대한 유지하세요.
- unverified_numbers로 지적된 수치는 자료의 값으로 교체하거나 제거하세요.
- 수정 과정 설명 없이 최종 원고만 출력하세요. 마크다운 유지, 챕터 제목(H1, #)은 다시 쓰지 마세요.
"""


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

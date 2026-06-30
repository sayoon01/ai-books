"""
④ Revise agent — 심사 결과를 반영해 섹션 원고를 수정.

REVISE_SYS + 섹션 + 심사결과(review JSON) + 원문(draft) → 수정된 LaTeX 본문.
생성 모델(MODEL)로 수정한다(문체 일관성). 검수는 다른 모델, 수정은 생성과 같은 모델.
"""
import json

from core.llm import call_text
from core.config import T_REVISE
from core.textutil import strip_code_fence
from core.grounding import ground_block
from agents.common import section_block, block


REVISE_SYS = """
당신은 학술 논문 저자이자 교정자입니다. 심사위원이 지적한 문제를 반영해 섹션 원고를
더 정확하고 설득력 있게 수정합니다. 성격이 다른 두 갈래로 접근하세요.

[고침 — 오류/위반]
factual_error, claim_evidence_mismatch, unsupported_claim, overclaiming, missing_baseline,
unreferenced_artifact, logical_error, off_topic, missing_content, surface_error
- 반드시 전부 제거하세요. 사실/근거 오류는 정확히 교정, 누락은 자연스럽게 보충,
  과장·근거 없는 단정은 자료에 맞게 덜어내거나 다시 쓰기.
- 참조 안 된 표/그림은 본문에서 \\ref 로 인용하세요. 깨진 LaTeX·이스케이프 누락은 정리.

[끌어올림 — 품질]
related_work_gap, reproducibility_gap, clarity/structure/depth_problem, redundancy
- 한 번에 완벽히 만들려 말고, 약한 축을 이번 패스에서 '한 단계' 끌어올리세요.
- 이미 좋은 부분은 망가뜨리지 말고 유지하세요.

공통 규칙:
- review_json 의 issues 를 반드시 반영하세요.
- unverified_numbers 로 지적된 수치는 자료의 값으로 교체하거나 제거하세요.
- 출력은 수정된 LaTeX 본문 조각만. \\section 제목 줄·문서 골격은 쓰지 마세요.
- 수정 과정 설명·잡담 없이 최종 본문만 출력하세요.
"""


def revise_user(plan: dict, section: dict, review: dict, draft: str, grounding: str) -> str:
    return "\n".join(filter(None, [
        ground_block(grounding),
        section_block(section),
        block("심사 결과", json.dumps(review, ensure_ascii=False, indent=2)),
        block("원문", draft),
    ]))


def revise_section(plan: dict, section: dict, review: dict, draft: str, grounding: str) -> str:
    raw = call_text(REVISE_SYS, revise_user(plan, section, review, draft, grounding),
                    temperature=T_REVISE)
    return strip_code_fence(raw).strip()

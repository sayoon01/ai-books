"""
② Write agent — 섹션 단위 LaTeX 집필 + 길이 가드.

섹션의 write_brief + grounding(실측 자료) + 앞 섹션 요약 + 인용 자료 목록을 조립해
\\section 본문(LaTeX)을 생성한다. 제목 줄(\\section{...})은 조립 단계가 붙이므로 본문만.
abstract 는 특수 처리(짧은 한 문단).
"""
from core.llm import call_text
from core.config import T_WRITE, WRITE_MAX
from core.textutil import strip_code_fence
from core.grounding import ground_block
from agents.common import section_block, prev_block, artifacts_block, block


WRITE_SYS = """
당신은 학술 논문 저자입니다. 주어진 섹션 계획에 맞춰 해당 섹션의 본문을 LaTeX 로 작성합니다.

[출력 규칙]
- 출력은 LaTeX 본문 조각입니다. \\documentclass·\\begin{document} 등 전체 골격은 쓰지 마세요.
- 섹션 제목 줄(\\section{...})도 쓰지 마세요. 시스템이 자동으로 붙입니다. 본문부터 시작하세요.
- 하위 구분이 필요하면 \\subsection{...} 까지만 쓰세요.
- 수식은 LaTeX 정식 문법($...$, equation, align)으로 자유롭게 쓰세요(이 출력은 LaTeX 입니다).
- 표/그림은 새로 그리지 말고, 제공된 자료 목록의 id 를 \\ref{id} 로 참조만 하세요
  (예: "구조별 성능은 표~\\ref{tab:perf_main}에서...", "그림~\\ref{fig:tradeoff} 참조").
- LaTeX 특수문자(%, &, _, #, $)는 본문에서 쓸 때 반드시 이스케이프(\\%, \\&, \\_ ...)하세요.

[내용 규칙]
- 섹션의 role 과 key_points 를 빠짐없이 반영하고, write_brief 를 최우선 기준으로 따르세요.
- 앞 섹션 요약이 있으면 자연스럽게 이어가되 내용을 반복하지 마세요.
- 실측 자료가 있으면 그 수치·결과를 근거로 쓰고, 자료에 없는 구체 수치·결과는 단정하지 마세요.
- 학술적 어조로, 군더더기 없이. 설명·잡담 없이 완결된 본문만 출력하세요.
"""

# 초록은 길이·형식이 달라 별도 지시.
ABSTRACT_EXTRA = """
[초록 특칙]
- 이 섹션은 초록(abstract)입니다. 배경→문제→방법→핵심 결과→기여를 한 문단(또는 두 문단)으로 압축하세요.
- 표·그림·\\ref·수식·인용을 쓰지 말고, 자족적인 평문으로 쓰세요. 5~8문장 분량.
"""


def write_user(plan: dict, section: dict, grounding: str,
               prev_summaries: list[str], sec_artifacts: list[dict]) -> str:
    is_abstract = section.get("id") == "abstract"
    paper_ctx = block("논문 개요", (
        f"제목: {plan.get('title','')}\n"
        f"기여: {'; '.join(plan.get('contributions', []))}\n"
        f"연구 설계: {plan.get('research_design','')}\n"
        f"실험 계획: {plan.get('experiment_plan','')}"
    ))
    return "\n".join(filter(None, [
        paper_ctx,
        block("이 섹션 집필 지시", section.get("write_brief", "")),
        section_block(section),
        artifacts_block(sec_artifacts) if not is_abstract else "",
        ground_block(grounding),
        prev_block(prev_summaries),
        ABSTRACT_EXTRA if is_abstract else "",
    ]))


def write_section(plan: dict, section: dict, grounding: str,
                  prev_summaries: list[str], sec_artifacts: list[dict]) -> str:
    """섹션 LaTeX 본문 생성(자유 텍스트). 코드펜스가 끼면 벗긴다."""
    sys = WRITE_SYS + (ABSTRACT_EXTRA if section.get("id") == "abstract" else "")
    raw = call_text(sys, write_user(plan, section, grounding, prev_summaries, sec_artifacts),
                    temperature=T_WRITE)
    return strip_code_fence(raw).strip()


def length_decision(body: str, min_chars: int, write_count: int) -> tuple[str, int]:
    """길이 가드 판정(순수). 반환: (route 'ok'|'rewrite', 다음 write_count).

    min_chars 미만이면 재작성, WRITE_MAX 까지 짧으면 통과(flagged 는 호출부가 기록).
    abstract 처럼 짧은 게 정상인 섹션은 호출부가 min_chars 를 낮춰 부른다.
    """
    chars = len(body.strip())
    write_count += 1
    if chars >= min_chars or write_count >= WRITE_MAX:
        return "ok", write_count
    return "rewrite", write_count

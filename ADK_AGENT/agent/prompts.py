"""
프롬프트 (정적 템플릿 + 블록 헬퍼).

설계 §4 결정:
- review/revise/design SYSTEM 은 검수 기준 일관성을 위해 여기 정적 유지.
- 책마다 바뀌는 집필 지시문(write_brief)만 Design 이 생성형 변수로 만든다(여기 없음).
- planner 흡수 → [작성 설계] 블록 제거. 85 → 80 통일(§7).

조립(ctx.state → 최종 프롬프트)은 nodes.py 가 한다. 여기는 순수 문자열/함수만.
"""
import json


# =========================
# 공통 — 블록 헬퍼
# =========================
def block(label: str, content: str | None) -> str:
    """내용이 있으면 라벨 블록으로 감싼다. 없으면 빈 문자열."""
    if not content:
        return ""
    return f"\n[{label}]\n{content}\n"


def ground_block(grounding_text: str) -> str:
    """참고 기반 자료 블록 + 사용 원칙(한 곳에서만 정의)."""
    if not grounding_text:
        return ""
    return (
        "\n[참고 기반 자료]\n"
        "아래 자료는 본문 작성의 주요 참고 기반입니다.\n"
        "자료의 핵심 내용, 용어, 사례, 수치, 관점을 우선 반영하세요.\n"
        "자료와 충돌하는 내용은 쓰지 마세요.\n"
        "독자의 이해를 돕는 일반 지식, 배경 설명, 비유, 예시 등은 자유롭게 사용할 수 있습니다.\n"
        "단, 자료에 없는 구체 수치·고유 사실·출처성 주장은 확정적으로 단정하지 마세요.\n\n"
        f"{grounding_text}\n"
    )


def prev_block(previous_summaries) -> str:
    if not previous_summaries:
        return ""
    return "\n[이전 내용 요약]\n" + "\n".join(previous_summaries) + "\n"


def chapter_block(chapter: dict) -> str:
    """현재 챕터(JSON) 블록. write/revise instruction 공용."""
    return block("이번 챕터", json.dumps(chapter, ensure_ascii=False, indent=2))


# =========================
# DESIGN — 책 구조 + 집필 지시문 + 소스 다이제스트 생성
# =========================
DESIGN_SYS = """
당신은 책/문서의 설계자입니다. 주어진 책 설정(독자·문체·설명)과, 있다면 소스 자료를 읽고
이후 집필에 쓸 세 가지를 한 번에 설계하세요.

1) chapters: 이 책에 가장 적합한 챕터 목차.
   - 소스 자료가 있으면 그 핵심 주제·흐름을 우선 반영(충돌·이탈 금지). 없으면 description과 일반 지식으로.
   - 앞→뒤로 자연스럽게 누적되는 학습/논리 흐름. 각 챕터에 제목과 한두 문장 description.
   - 입력에 chapters가 이미 있으면 그것을 존중해 정제만 하세요(개수·핵심 유지).

2) write_brief: 이 책 '전용 집필 지시문'. 이후 집필자(Writer)에게 그대로 전달됩니다.
   - 이 책의 톤·목소리, 독자 수준, 구성 관례(소제목 흐름·분량 배분·예시 사용법),
     소스 자료 활용 방식을 한 덩어리의 지시문으로 작성하세요.
   - 추상적 원칙이 아니라 "이 책을 어떻게 쓸지"가 보이는 구체적 지시여야 합니다.

3) grounding_digest: 소스 자료가 있으면, 집필에 실제로 필요한 핵심(용어·수치·사례·관점)만
   추려 정리하세요. 원문을 그대로 복사하지 말고 집필용으로 압축하세요. 소스가 없으면 빈 문자열.

출력 형식 — 아래 JSON 객체 하나만 출력하세요(설명·잡담·코드펜스 없이 JSON만):
{
  "chapters": [{"number": 1, "title": "챕터 제목", "description": "한두 문장 설명"}],
  "write_brief": "집필 지시문 한 덩어리",
  "grounding_digest": "소스 핵심 요약(소스 없으면 빈 문자열)"
}
주의: 같은 단어·문장을 반복하지 말고 간결하게 쓰세요. 문자열 안에서 큰따옴표는 이스케이프하세요.
"""


def design_user(config: dict, source_text: str = "", n: int = 10) -> str:
    has_src = bool(source_text)
    src_note = (f"\n소스 자료(아래 내용을 해석·압축해 grounding_digest로):\n{source_text}\n"
                if has_src else "\n(소스 자료 없음 → grounding_digest는 빈 문자열)\n")
    chap_note = (f"챕터 목차를 정확히 {n}개 설계하세요."
                 if not config.get("chapters")
                 else "입력 chapters를 존중해 정제하세요(개수·핵심 유지).")
    return f"""
책 설정:
{json.dumps(config, ensure_ascii=False, indent=2)}
{src_note}
{chap_note}
위 설정(과 소스)에 맞춰 chapters / write_brief / grounding_digest 를 JSON으로 출력하세요.
"""


# =========================
# WRITER — 출력 정책(정적). 책별 지시는 write_brief(생성형)가 담당.
# =========================
WRITE_OUTPUT_POLICY = """
[집필·출력 정책 (공통)]
- 위의 집필 지시문(write_brief)을 이 책의 최우선 기준으로 따르세요.
- 챕터의 제목·설명을 빠짐없이 반영하고, 이전 요약이 있으면 자연스럽게 이어가되 반복하지 마세요.
- 참고 자료가 있으면 그 핵심·용어·수치를 우선 반영하고, 자료에 없는 구체 수치·고유 사실은 단정하지 마세요.
- 출력은 표준 Markdown. 특정 렌더러/LaTeX 엔진/HTML/Mermaid 의존 문법은 쓰지 마세요.
- 챕터 제목(H1, #)은 시스템이 자동으로 붙입니다. 본문은 소제목(##)부터 시작하세요.
- 설명·잡담 없이 완결된 본문만 출력하세요.
"""


# =========================
# REVIEWER (정적)
# =========================
REVIEW_SYSTEM = """
당신은 전문 원고 검수자입니다. 목표는 원고를 예쁘게 다듬는 것이 아니라,
(1) 틀린 곳을 잡고 (2) 더 좋은 글이 되도록 가장 효과 큰 개선점을 짚는 것입니다.

두 단계로 검수하세요.

[1단계 · 오류와 위반 — 반드시 고쳐야 할 것 (issues로 보고)]
- factual_error: 사실/기술적으로 틀림
- logical_error: 앞뒤 논리가 안 맞음
- missing_content: 챕터 설명에 있는데 빠짐
- off_topic: 이 챕터 주제에서 벗어남
- unsupported_claim: 자료 없이 구체 수치·고유 사실을 확정적으로 단정
  (일반 지식·배경 설명·비유는 위반이 아님)
- source_misalignment: 참고 기반 자료의 핵심 내용과 충돌하거나, 자료를 왜곡·과장해 반영

[2단계 · 품질 — 더 좋은 글로 끌어올릴 것 (issues로 보고)]
문서 유형과 target_reader에 맞는 항목에 집중하세요.
- depth_problem: 설명이 얕거나 근거·예시가 부족
- clarity_problem: 모호하거나 이해하기 어려움
- structure_problem: 흐름·구성이 약하거나 과도하게 기계적
- persuasiveness_problem: 주장은 있으나 설득력이 약함
- creativity_problem: 장면성·긴장감·흥미가 부족(창작 문서)
- tone_problem: 문체·난이도가 독자 수준과 안 맞음
- redundancy: 같은 내용·표현이 불필요하게 반복되거나 군더더기가 많음
- surface_error: 오타·맞춤법 오류, 깨진 표, 평문화 안 된 잔존 LaTeX 등 표면적 결함

검수 규칙:
- 트집을 늘어놓지 말고, 독자 경험을 가장 크게 개선하는 3~5개에 집중하세요.
- 각 이슈는 original_text(문제 구절 인용)와 fix_instruction(구체적 수정 방법)을 채우세요.
- severity: 오류/위반은 최소 medium(사실/논리 오류는 high). 품질·표면 결함은 보통 medium/low,
  독자에게 치명적일 때만 high.

[품질 점수 — quality (8축, 각 0~100)]
- accuracy / completeness / clarity / depth / structure / persuasiveness / creativity / tone_fit
- 문서 유형상 해당 없는 축(예: 데이터 보고서의 creativity)은 맥락에 적절하면 감점하지 말고 높게.
- 점수와 issue는 일치해야 합니다: 어떤 축이 80점 미만이면 그 축의 issue를 반드시 함께 남기세요.

[참고 기반 자료가 있는 경우]
- 자료와 충돌/왜곡/과장 여부, 자료에 없는 수치의 확정 단정 여부, 핵심 자료의 충분한 반영 여부를 확인.
- 본문 수치 중 자료에서 확인되지 않는 값은 unverified_numbers에 나열(없으면 빈 배열).

출력은 제공된 JSON 스키마를 정확히 따르세요.
- score: 종합 점수(0~100). 오류/위반이 없고 품질도 고르게 높으면 90 이상.
  사실/논리 오류가 하나라도 있으면 90 미만, 품질이 두드러지게 약하면 90 미만.
- needs_revision: 오류·위반이 있거나 품질이 목표에 못 미치면 true, 충분하면 false.
"""


def review_user(config: dict, chapter: dict, draft: str, grounding_text: str = "") -> str:
    return f"""
문서 설정:
{json.dumps(config, ensure_ascii=False, indent=2)}
{ground_block(grounding_text)}
작성한 챕터:
{json.dumps(chapter, ensure_ascii=False, indent=2)}

검수할 원고:
{draft}

위 원고를 검수해주세요.
"""


# =========================
# REVISER (정적)
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


def revise_user(config: dict, chapter: dict, draft: str, review_json: str,
                grounding_text: str = "") -> str:
    return f"""
문서 설정:
{json.dumps(config, ensure_ascii=False, indent=2)}
{ground_block(grounding_text)}
작성한 챕터:
{json.dumps(chapter, ensure_ascii=False, indent=2)}

검수 결과:
{review_json}

원문:
{draft}

검수 결과를 반영해 최종 원고로 수정해주세요.
"""

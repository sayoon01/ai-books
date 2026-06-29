"""
여러 단계가 공유하는 공용 조각 모음.

세 가지 성격이 한 파일에 있다(섹션으로 구분):
  1) 스키마      — 구조화 출력 데이터 계약(Pydantic). Design/Review 가 쓴다.
  2) 프롬프트 블록 — 프롬프트 문자열 조립 헬퍼. write/review/revise 가 쓴다.
  3) trace       — 챕터 진행 히스토리 기록 헬퍼. write/review/gate 노드가 쓴다.

각 단계의 SYSTEM 프롬프트·user 빌더는 해당 단계 파일에 있다(design/write/review/revise).
grounding 전용 ground_block 은 core/grounding.py 에 있다.
"""
import json
from typing import Literal

from pydantic import BaseModel, Field


# =====================================================================
# 1) 스키마 (Pydantic v2)
#    - 구조화 출력은 "판단/계획" 단계(Design/Review)에만 강제한다.
#    - "생성" 단계(Write/Revise)는 긴 마크다운이라 자유 텍스트로 둔다.
# =====================================================================

# --- REVIEW ---
IssueType = Literal[
    # 오류/위반
    "factual_error",
    "logical_error",
    "missing_content",
    "off_topic",
    "unsupported_claim",
    "source_misalignment",    # 참고 자료를 왜곡/과장하거나 잘못 반영함

    # 품질 문제
    "depth_problem",          # 설명이 얕음 / 근거가 부족함
    "clarity_problem",        # 이해가 어려움 / 모호함
    "structure_problem",      # 흐름·구성 약함
    "persuasiveness_problem", # 설득력 부족
    "creativity_problem",     # 창의성/장면성/흥미 부족
    "tone_problem",           # 문체·독자 수준 안 맞음
    "redundancy",             # 중복·장황 (같은 내용 반복, 군더더기)
    "surface_error",          # 오타·맞춤법·깨진 표·잔존 LaTeX 등 표면적 결함
]


class Issue(BaseModel):
    type: IssueType
    severity: Literal["low", "medium", "high"]
    problem: str = Field(description="문제 설명")
    original_text: str = Field(default="", description="문제가 되는 원문 문장 또는 구절")
    fix_instruction: str = Field(description="수정 지시")


class QualityScores(BaseModel):
    """글 자체의 품질을 축별로 분리 평가. 문서 유형상 해당 없는 축은 맥락에 맞으면 높게 둔다.
    어떤 축이 낮으면(<80) 그 축의 issue가 반드시 함께 있어야 한다(점수↔issue 일관성)."""
    accuracy: int = Field(ge=0, le=100, description="사실·근거 정확성")
    completeness: int = Field(ge=0, le=100, description="필수 내용 충족도")
    clarity: int = Field(ge=0, le=100, description="이해하기 쉬운 정도")
    depth: int = Field(ge=0, le=100, description="충분히 자세하고 깊이 있는 정도")
    structure: int = Field(ge=0, le=100, description="흐름과 구성의 자연스러움")
    persuasiveness: int = Field(ge=0, le=100, description="논리적 설득력")
    creativity: int = Field(ge=0, le=100, description="창의성·흥미·장면성")
    tone_fit: int = Field(ge=0, le=100, description="독자와 문서 유형에 맞는 문체")


class ReviewResult(BaseModel):
    needs_revision: bool = Field(description="수정이 필요한가(오류·위반 또는 품질 미달).")
    score: int = Field(ge=0, le=100, description="종합 점수. 90 이상이면 수정 불필요 수준.")
    quality: QualityScores
    issues: list[Issue] = Field(default_factory=list)
    summary: str = Field(default="", description="전체 검수 요약")
    # 참고 자료가 있을 때: 본문에 나왔지만 자료에서 확인 안 되는 수치. 없으면 빈 채로 둔다.
    unverified_numbers: list[str] = Field(default_factory=list)


# --- DESIGN: 책 구조 + 집필 지시문 + 소스 다이제스트 ---
class ChapterSpec(BaseModel):
    number: int = Field(default=0, description="챕터 번호. 0이면 코드가 순서대로 채운다.")
    title: str = Field(description="챕터 제목")
    description: str = Field(default="", description="이 챕터가 다루는 내용 한두 문장")


# --- CHARTS: grounding_digest의 표에서 그릴 차트 스펙 (숫자는 LLM이 만들지 않음) ---
ChartType = Literal["donut", "bar", "grouped_bar", "barh", "stacked100", "line", "scatter"]


class FigureSpec(BaseModel):
    """차트 1개의 '구조'. 숫자는 담지 않는다 — 렌더러가 digest 표에서 추출한다.
    웹/사람이 design.json에서 편집 가능."""
    chapter: int = Field(description="이 차트를 넣을 챕터 번호")
    type: ChartType = Field(description="차트 종류")
    title: str = Field(default="", description="차트 제목")
    caption: str = Field(default="", description="그림 캡션(아래 설명 한 문장)")
    table: str = Field(default="", description="digest에서 표를 찾을 키워드(표 제목/직전 문맥의 일부)")
    label_col: str = Field(description="범주(라벨) 열 이름 — 표 헤더와 일치/부분일치")
    value_cols: list[str] = Field(min_length=1, max_length=6,
        description="수치 시리즈 열 이름들(표 헤더와 일치/부분일치). scatter는 [x열, y열].")
    top_n: int = Field(default=0, description="0이면 전체, 양수면 상위 N개만(막대류)")
    sort: bool = Field(default=True, description="값 큰 순 정렬(막대류)")


class FigurePlan(BaseModel):
    """차트 디자이너 산출물. max_length 로 디코딩 폭주 방지."""
    figures: list[FigureSpec] = Field(default_factory=list, max_length=24)


class DesignPlan(BaseModel):
    """Design 산출물. output/<slug>/design.json 으로 저장되어 웹에서 편집 가능."""
    # max_length 필수: 상한이 없으면 ollama 제약 디코딩이 배열을 못 닫고 무한히 늘어진다.
    chapters: list[ChapterSpec] = Field(min_length=1, max_length=20,
        description="config에 chapters 없으면 생성, 있으면 정제해 그대로. 앞→뒤 누적 흐름.")
    write_brief: str = Field(
        description="이 책 전용 집필 지시문. 톤·독자·구성 관례·소스 활용법을 한 덩어리로. "
                    "= Write 노드에 그대로 넘길 프롬프트.")
    grounding_digest: str = Field(default="",
        description="source_text에서 집필에 필요한 핵심만 추린 텍스트. "
                    "write/review에 참고자료로 주입. source 없으면 빈 값.")
    figures: list[FigureSpec] = Field(default_factory=list, max_length=24,
        description="grounding_digest 표에서 그릴 차트 스펙(자동 제안·편집 가능). 없으면 빈 배열.")


# =====================================================================
# 2) 프롬프트 블록 — write/review/revise 가 공통으로 쓰는 조립 헬퍼.
#    조립(ctx.state → 최종 프롬프트)은 각 노드가 한다. 여기는 순수 문자열/함수만.
# =====================================================================

def block(label: str, content: str | None) -> str:
    """내용이 있으면 라벨 블록으로 감싼다. 없으면 빈 문자열."""
    if not content:
        return ""
    return f"\n[{label}]\n{content}\n"


def prev_block(previous_summaries) -> str:
    if not previous_summaries:
        return ""
    return "\n[이전 내용 요약]\n" + "\n".join(previous_summaries) + "\n"


def chapter_block(chapter: dict) -> str:
    """현재 챕터(JSON) 블록. write/revise instruction 공용."""
    return block("이번 챕터", json.dumps(chapter, ensure_ascii=False, indent=2))


# =====================================================================
# 3) trace — 챕터 진행 히스토리 기록 헬퍼.
#    각 노드(write/review/gate)가 자기 단계 결과를 state["history"]에 한 항목씩 남긴다.
#    드라이버(pipeline)가 이 history 를 logs/chapter-NN.json 에 통째로 저장.
#    주의: 리스트 in-place append 는 ADK state delta 로 안 잡힐 수 있어 '재할당'으로 추가한다.
#    history 는 어떤 instruction 에도 주입되지 않으므로 LLM 프롬프트를 키우지 않는다.
# =====================================================================

def record(ctx, **entry) -> None:
    ctx.state["history"] = ctx.state.get("history", []) + [entry]

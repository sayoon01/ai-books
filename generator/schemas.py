"""
단계별 출력 스키마 (Pydantic v2).

설계 원칙:
- 구조화 출력은 "판단/계획" 단계(Reviewer/Outline)에만 강제한다.
- "생성" 단계(Writer/Reviser)는 긴 마크다운이라 자유 텍스트로 둔다.
"""
from typing import Literal
from pydantic import BaseModel, Field


# =========================
# REVIEW
# =========================
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
]


class Issue(BaseModel):
    type: IssueType
    severity: Literal["low", "medium", "high"]
    problem: str = Field(description="문제 설명")
    original_text: str = Field(default="", description="문제가 되는 원문 문장 또는 구절")
    fix_instruction: str = Field(description="수정 지시")


class QualityScores(BaseModel):
    """글 자체의 품질을 축별로 분리 평가. 문서 유형상 해당 없는 축은 맥락에 맞으면 높게 둔다.
    어떤 축이 낮으면(<85) 그 축의 issue가 반드시 함께 있어야 한다(점수↔issue 일관성)."""
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


# =========================
# OUTLINE — 목차 자동 생성
# =========================
# chapters가 없을 때, grounding(없으면 description)을 토대로 목차를 자동 생성한다.

class ChapterSpec(BaseModel):
    number: int = Field(default=0, description="챕터 번호. 0이면 코드가 순서대로 채운다.")
    title: str = Field(description="챕터 제목")
    description: str = Field(default="", description="이 챕터가 다루는 내용 한두 문장")


class OutlinePlan(BaseModel):
    # max_length 필수: 상한이 없으면 ollama 제약 디코딩이 배열을 못 닫고 무한히 늘어진다.
    chapters: list[ChapterSpec] = Field(min_length=1, max_length=20,
                                        description="앞→뒤로 누적되는 챕터 목차")


# =========================
# CHAPTER PLANNER — 챕터별 본문 설계 (경량)
# =========================
class PlanStep(BaseModel):
    """본문 흐름의 한 마디(≈ 한 섹션). 위→아래로 읽으면 하나의 흐름이 된다."""
    heading: str = Field(description="이 step의 소제목(##로 쓰일 수 있는).")
    point: str = Field(description="이 step에서 전달할 핵심 내용 한 문장.")
    must_include: list[str] = Field(default_factory=list,
        description="이 step에서 반드시 다룰 요소(개념·사례·수치 등). 없으면 비움.")
    weight: Literal["minor", "normal", "major"] = Field(default="normal",
        description="분량·깊이 배분. major는 더 깊게, minor는 짧게.")


class UnitPlan(BaseModel):
    unit_id: str = Field(description="대상 챕터 식별자(번호나 제목).")
    thesis: str = Field(description="이 챕터가 결국 전달하려는 핵심 방향 한 문장.")
    reader_takeaway: str = Field(default="", description="독자가 얻어야 하는 것 한 문장.")
    steps: list[PlanStep] = Field(min_length=3, max_length=8, description="본문 흐름 3~8개.")
    avoid: list[str] = Field(default_factory=list, description="이 챕터에서 다루지 않을 내용.")

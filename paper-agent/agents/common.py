"""
모든 에이전트가 공유하는 데이터 계약(Pydantic) + 프롬프트 조립 헬퍼.

스키마는 두 부류:
  - 판단/계획 단계(Plan/Review)는 구조화 출력으로 강제한다.
  - 생성 단계(Write/Revise)는 긴 LaTeX 라 자유 텍스트로 둔다.
"""
import json
from typing import Literal

from pydantic import BaseModel, Field


# =====================================================================
# 1) PLAN — 논문 설계 산출물
#    "설계 계획 + 실험 계획 + 작성 계획 + 자료(표/그림/통계) 계획"을 한 객체에.
# =====================================================================

ArtifactKind = Literal["figure", "table", "stat"]


class ArtifactSpec(BaseModel):
    """'무엇을 만들지'만 정한다. 실제 수치/그림은 artifacts/build.py 가 데이터에서 생성한다.
    (LLM 이 수치를 지어내는 것을 원천 차단하는 핵심 분리.)"""
    id: str = Field(description="LaTeX 라벨에 쓸 식별자. 예: 'fig:cost', 'tab:main', 'stat:ttest'")
    kind: ArtifactKind = Field(description="figure(그림) / table(표) / stat(통계검정)")
    title: str = Field(description="캡션에 쓸 제목")
    purpose: str = Field(description="이 자료가 뒷받침할 주장/논점 한 문장")
    data_source: str = Field(default="",
        description="근거 데이터 위치. 예: 'results/<slug>/summary.json 의 orch별 token 평균'")
    method: str = Field(default="",
        description="만드는 방법. 예: 'grouped_bar: 구조별 평균 토큰', 'paired t-test: code vs llm 점수'")
    section_id: str = Field(default="", description="이 자료가 들어갈 섹션 id")


class SectionSpec(BaseModel):
    """논문 섹션 1개. 챕터와 달리 섹션마다 '역할'이 다르다(abstract≠method≠results)."""
    id: str = Field(description="섹션 식별자(영문 소문자). 예: 'abstract','intro','method','results'")
    title: str = Field(description="섹션 제목(LaTeX \\section 제목)")
    role: str = Field(description="이 섹션이 논문에서 해야 할 역할 한두 문장")
    key_points: list[str] = Field(default_factory=list, description="이 섹션이 반드시 담을 핵심 포인트")
    write_brief: str = Field(default="",
        description="이 섹션 전용 집필 지시문(톤·길이·구성). Writer 에게 그대로 전달된다.")
    artifact_ids: list[str] = Field(default_factory=list,
        description="이 섹션에서 참조(\\ref)할 ArtifactSpec.id 들")
    review_axes: list[str] = Field(default_factory=list,
        description="이 섹션에서 평가할 품질 축(비우면 역할 기반 기본값 사용). "
                    "예: method=['soundness','clarity','reproducibility']")
    target_chars: int = Field(default=0,
        description="이 섹션 목표 분량(글자). 0이면 등급(tier) 기본값. 장문일수록 크게.")


class PaperPlan(BaseModel):
    """Plan 산출물. output/<slug>/plan.json 으로 저장 — 사람이 편집 가능."""
    title: str = Field(description="논문 제목")
    venue: str = Field(default="", description="대상 학회/저널(문체·분량 기준). 없으면 빈 값")
    abstract_brief: str = Field(default="", description="초록에 담을 핵심 메시지(초록 자체는 아님)")
    contributions: list[str] = Field(default_factory=list, min_length=1, max_length=8,
        description="이 논문의 핵심 기여(주장). 결과로 뒷받침되어야 한다.")
    research_design: str = Field(default="",
        description="연구 설계: 무엇을 어떻게 비교/검증하는가(가설·변인·통제).")
    experiment_plan: str = Field(default="",
        description="실험 계획: 데이터셋·조건·반복·평가지표.")
    # max_length 필수 — 상한 없으면 제약 디코딩이 배열을 못 닫고 늘어진다(책 엔진 교훈).
    sections: list[SectionSpec] = Field(min_length=1, max_length=16,
        description="논문 섹션 목차. abstract→intro→...→conclusion 순서.")
    artifacts: list[ArtifactSpec] = Field(default_factory=list, max_length=24,
        description="만들 표/그림/통계 목록. 각 섹션의 artifact_ids 가 여기를 참조한다.")


# =====================================================================
# 2) REVIEW — 학회 리뷰어 관점 구조화 검수
#    책 엔진의 ReviewResult 를 논문 도메인으로 교체(IssueType·quality 축).
# =====================================================================

IssueType = Literal[
    # 오류/위반 (반드시 고침)
    "factual_error",            # 사실/기술적으로 틀림
    "claim_evidence_mismatch",  # 주장과 결과(표/그림/수치)가 안 맞음
    "unsupported_claim",        # 근거(데이터) 없는 수치·결과를 단정
    "overclaiming",             # 결과보다 과장된 일반화/주장
    "missing_baseline",         # 비교/대조군·기준선이 빠짐
    "unreferenced_artifact",    # 표/그림이 본문에서 참조(\\ref)되지 않음
    "logical_error",            # 앞뒤 논리가 안 맞음
    "off_topic",                # 섹션 역할에서 벗어남
    "missing_content",          # 섹션이 담아야 할 핵심이 빠짐

    # 품질 (끌어올림)
    "related_work_gap",         # 관련연구/맥락이 부족
    "reproducibility_gap",      # 재현에 필요한 정보 부족(설정·하이퍼파라미터 등)
    "clarity_problem",          # 모호/난해
    "structure_problem",        # 흐름·구성 약함
    "depth_problem",            # 분석/논의가 얕음
    "redundancy",               # 중복·장황
    "surface_error",            # 오타·맞춤법·깨진 LaTeX·라벨 오류 등 표면 결함
]


class Issue(BaseModel):
    type: IssueType
    severity: Literal["low", "medium", "high"]
    problem: str = Field(description="문제 설명")
    original_text: str = Field(default="", description="문제가 되는 원문 문장/구절")
    fix_instruction: str = Field(description="구체적 수정 지시")


class QualityScores(BaseModel):
    """논문 품질 축(각 0~100). 어떤 축이 낮으면(<80) 그 축의 issue 가 반드시 함께 있어야 한다."""
    novelty: int = Field(ge=0, le=100, description="기여의 새로움")
    soundness: int = Field(ge=0, le=100, description="방법·주장의 타당성/근거 적합성")
    clarity: int = Field(ge=0, le=100, description="명확성·가독성")
    significance: int = Field(ge=0, le=100, description="중요도·임팩트")
    reproducibility: int = Field(ge=0, le=100, description="재현 가능성(설정·데이터 기술 충분성)")
    related_work: int = Field(ge=0, le=100, description="맥락·관련연구 반영도")


class ReviewResult(BaseModel):
    needs_revision: bool = Field(description="수정이 필요한가(오류·위반 또는 품질 미달).")
    score: int = Field(ge=0, le=100, description="종합 점수. 90+면 게재 수준.")
    quality: QualityScores
    issues: list[Issue] = Field(default_factory=list)
    summary: str = Field(default="", description="리뷰 총평(메타리뷰 한 문단)")
    # 본문에 나왔지만 자료에서 확인 안 되는 수치(결정적 검출이 채워줌). 없으면 빈 채로.
    unverified_numbers: list[str] = Field(default_factory=list)


# =====================================================================
# 3) 프롬프트 블록 — write/review/revise 공용 조립 헬퍼.
# =====================================================================

def block(label: str, content: str | None) -> str:
    if not content:
        return ""
    return f"\n[{label}]\n{content}\n"


def section_block(section: dict) -> str:
    """현재 섹션(JSON) 블록. write/revise 공용."""
    return block("이번 섹션", json.dumps(section, ensure_ascii=False, indent=2))


def prev_block(prev_summaries) -> str:
    if not prev_summaries:
        return ""
    return "\n[앞 섹션 요약]\n" + "\n".join(prev_summaries) + "\n"


def artifacts_block(artifacts: list[dict]) -> str:
    """이 섹션이 참조할 표/그림/통계 목록 + 라벨. Writer 가 \\ref 로만 인용하게."""
    if not artifacts:
        return ""
    lines = ["\n[이 섹션에서 인용할 자료 — 본문에선 \\ref{id} 로만 참조하고 수치를 새로 짓지 마세요]"]
    for a in artifacts:
        lines.append(f"- {a['id']} ({a['kind']}): {a['title']} — {a.get('purpose','')}")
    return "\n".join(lines) + "\n"


# =====================================================================
# 4) 검수 스케일링 — (a) 섹션 역할별 적용 축, (b) 논문 등급(tier) 루브릭.
#    축은 "이 섹션에서 의미 있는 품질 축만" 채점하게 해 엉뚱한 감점/무한 재수정을 막는다.
#    루브릭은 같은 코드로 draft → conference → SCI 까지 기준을 끌어올린다.
# =====================================================================

AXIS_KEYS = ["novelty", "soundness", "clarity", "significance",
             "reproducibility", "related_work"]

# 섹션 id(별칭 포함) → 그 섹션에서 의미 있는 축. 없는 id 는 ALL.
_DEFAULT_SECTION_AXES = {
    "abstract": ["clarity", "significance"],
    "intro": ["clarity", "significance", "related_work"],
    "introduction": ["clarity", "significance", "related_work"],
    "related_work": ["related_work", "novelty", "clarity"],
    "background": ["clarity", "related_work"],
    "preliminaries": ["clarity", "soundness"],
    "method": ["soundness", "clarity", "reproducibility", "novelty"],
    "methods": ["soundness", "clarity", "reproducibility", "novelty"],
    "approach": ["soundness", "clarity", "reproducibility", "novelty"],
    "system": ["soundness", "clarity", "reproducibility"],
    "experiment": ["soundness", "reproducibility", "clarity"],
    "experiments": ["soundness", "reproducibility", "clarity"],
    "setup": ["reproducibility", "clarity"],
    "results": ["soundness", "clarity", "significance"],
    "evaluation": ["soundness", "clarity", "significance"],
    "discussion": ["significance", "soundness", "clarity"],
    "limitations": ["soundness", "significance"],
    "conclusion": ["clarity", "significance"],
    "future_work": ["significance", "novelty"],
}


def axes_for(section: dict) -> list[str]:
    """이 섹션에서 평가할 품질 축. 명시(review_axes) > id 기본맵 > 전체."""
    explicit = [a for a in (section.get("review_axes") or []) if a in AXIS_KEYS]
    if explicit:
        return explicit
    sid = (section.get("id") or "").strip().lower()
    return _DEFAULT_SECTION_AXES.get(sid, list(AXIS_KEYS))


# 논문 등급별 기준. 위로 갈수록 기준선·분량·엄격도↑.
RUBRICS: dict[str, dict] = {
    "draft": {
        "quality_gate": 70, "target_score": 80, "min_chars": 700, "abstract_chars": 300,
        "standard": "내부 초안 수준. 사실/논리 오류와 큰 누락만 잡고, 사소한 표현 트집은 피한다.",
        "length_hint": "각 섹션을 한두 문단으로 핵심만 간결하게.",
    },
    "workshop": {
        "quality_gate": 76, "target_score": 84, "min_chars": 1000, "abstract_chars": 350,
        "standard": "워크숍/포스터 수준. 기여가 분명하고 방법이 이해 가능해야 한다.",
        "length_hint": "각 섹션을 두세 문단으로, 핵심 근거를 포함해.",
    },
    "conference": {
        "quality_gate": 80, "target_score": 88, "min_chars": 1400, "abstract_chars": 400,
        "standard": ("국내/국제 학술대회(KIISE·IEEE conf.) 수준. 기여가 명확하고, 방법이 재현 가능하며, "
                     "관련연구가 적절히 다뤄지고, 주장이 결과로 뒷받침되어야 한다."),
        "length_hint": "각 섹션을 충분한 문단으로, 필요하면 \\subsection 으로 나눠 깊이 있게.",
    },
    "journal": {
        "quality_gate": 84, "target_score": 90, "min_chars": 2000, "abstract_chars": 450,
        "standard": ("학술지 수준. 신규성과 이론적 근거가 탄탄하고, 실험이 체계적이며, "
                     "관련연구가 폭넓고, 한계와 위협요인이 정직하게 논의되어야 한다."),
        "length_hint": "각 섹션을 여러 문단·\\subsection 으로 길고 깊게. 근거·예시·반례를 충실히.",
    },
    "sci": {
        "quality_gate": 88, "target_score": 93, "min_chars": 2600, "abstract_chars": 500,
        "standard": ("SCI(E) 저널 Q1 수준. 신규성·이론적 엄밀성·통계적 유의성(유의수준·효과크기)을 요구하고, "
                     "광범위한 최신 관련연구 비교, 완전한 재현 정보(설정·하이퍼파라미터·데이터), "
                     "타당성 위협(internal/external validity)에 대한 방어를 요구한다. 사소한 결함도 지적한다."),
        "length_hint": ("각 섹션을 학술지 분량으로 길고 정밀하게(\\subsection 적극 활용). "
                        "정의·표기·증명/논증·정량 근거를 빠짐없이."),
    },
}


def get_rubric(tier: str | None) -> dict:
    """tier 문자열 → 루브릭 dict. 모르는 값이면 conference 로 폴백."""
    return RUBRICS.get((tier or "conference").strip().lower(), RUBRICS["conference"])

"""
단계별 출력 스키마 (Pydantic v2).

설계 원칙:
- 구조화 출력은 "판단/계획" 단계(Reviewer/Planner)에만 강제한다.
- "생성" 단계(Writer/Reviser)는 긴 마크다운이라 자유 텍스트로 둔다.
- Digest는 데이터 모드 전용 그라운딩 객체. 책 모드에서는 digest=None.
관련 설계: MOLD_DX_AGENT_DESIGN.md §5, §6
"""
from typing import Literal
from pydantic import BaseModel, Field


# =========================
# REVIEW (책·기술서 공통)
# =========================
# 기존 prompts.py의 review JSON 모양(has_errors/score/issues/summary)을 그대로 스키마화.
# 정규식 파싱(_parse_review)을 대체해도 Reviewer 동작은 동일하다.

IssueType = Literal[
    # 오류/위반
    "factual_error",
    "logical_error",
    "missing_content",
    "off_topic",
    "unsupported_claim",

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
    """글 자체의 품질을 축별로 분리 평가. IssueType이 '고칠 문제 종류'라면
    이쪽은 '글이 얼마나 좋은가'의 점수. 문서 유형상 해당 없는 축은 맥락에 맞으면 높게 둔다.
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
    has_errors: bool
    score: int = Field(ge=0, le=100, description="종합 점수. 90 이상이면 수정 불필요 수준.")
    quality: QualityScores
    issues: list[Issue] = Field(default_factory=list)
    summary: str = Field(default="", description="전체 검수 요약")
    # 데이터 모드 전용: 본문에 나왔지만 digest에 없는 수치(환각 의심). 책 모드는 빈 채로 둔다.
    ungrounded_numbers: list[str] = Field(default_factory=list)


# =========================
# OUTLINE PLANNER (선택 단계)
# =========================
# Writer 앞에서 본문 흐름(outline)을 설계한다. 본문은 쓰지 않는다.
# Planner는 Writer를 묶는 규칙이 아니라 '방향 제시자'. steps는 권장 순서이고,
# Writer는 핵심 의도를 지키되 세부 전개를 자연스럽게 조정할 수 있다.
# grounding이 있으면 support/refs가 실제 근거로 강하게 묶이고, 없으면 자유롭게 설계.
# 장르 무관(챕터/섹션/장면/에피소드 공통) — 그래서 이름은 UnitPlan.


class PlanStep(BaseModel):
    """본문 흐름의 한 마디(≈ 한 섹션). 위→아래로 읽으면 하나의 흐름이 된다."""
    point: str = Field(description="이 step에서 전달할 핵심 내용. 기술서면 논점, 교재면 학습 포인트, 소설이면 사건, 웹툰이면 장면, 에세이면 생각.")
    role: str = Field(description="이 step의 기능. 예: 도입/전개/근거/분석/대조/장면/갈등/감정/전환/결론.")
    support: list[str] = Field(
        default_factory=list,
        description="이 step을 전개하는 데 쓸 근거·설정·예시·사실. 근거(grounding)가 있으면 실제 근거에서만 가져온다(지어내지 않음). 없으면 비워도 됨.",
    )
    refs: list[str] = Field(
        default_factory=list,
        description="근거가 있을 때만 쓰는 근거 키/출처명. 예: 'anomaly_rate', 'process_time.cool'. 없으면 빈 배열.",
    )
    figure: str | None = Field(default=None, description="필요한 표/그림/도식 제목(선택). 없으면 null.")
    weight: Literal["minor", "normal", "major"] = Field(
        default="normal", description="분량·깊이 배분. major는 더 깊게, minor는 짧게.",
    )


class UnitPlan(BaseModel):
    unit_id: str = Field(description="대상 작성 단위 식별자")
    thesis: str = Field(description="이 단위가 결국 전달하려는 핵심 방향 한 문장.")
    reader_takeaway: str = Field(default="", description="독자가 이 단위를 읽고 얻어야 하는 것 한 문장.")
    steps: list[PlanStep] = Field(
        min_length=3, max_length=8,
        description="본문 흐름 3~8개. 위→아래로 하나의 흐름이 되도록 배열(권장 순서).",
    )
    builds_on: list[str] = Field(
        default_factory=list,
        description="이전 요약에서 이미 다뤄 반복하지 않을 내용.",
    )
    out_of_scope: list[str] = Field(default_factory=list, description="이 단위에서 다루지 않을 내용.")
    hook: str = Field(default="", description="도입부에 활용할 문장/장면(선택).")
    bridge_to_next: str = Field(default="", description="다음 단위로 이어지는 연결 문장(선택).")


# =========================
# DIGEST (데이터 모드 전용 그라운딩)
# =========================

class Provenance(BaseModel):
    """이 digest가 언제·어디서 왔는지. 재현성 추적용."""
    source: str                       # "composite(api+excel)" / "api" / "excel"
    fetched_at: str                   # 스냅샷 시각 (외부에서 주입 — Date.now 회피)
    api_base: str | None = None


class StatBlock(BaseModel):
    """원분포 대신 5분위 + n으로 압축. 분포 모양은 살리고 크기는 최소화."""
    mean: float
    p1: float
    p25: float
    p75: float
    p99: float
    n: int


class FieldSpec(BaseModel):
    """엑셀 필드 사전 항목 — 용어 오독 방지."""
    name: str
    group: Literal["id", "material", "condition", "temp", "pressure", "time", "etc"]
    unit: str | None = None
    description: str


class MoldModelStat(BaseModel):
    model: str
    n_cycles: int
    anomaly_rate: float
    mean_ct_sec: float


class Corr(BaseModel):
    """상관행렬(30x30=900칸)은 통째로 넣지 않고 |r|>0.8 쌍만 남긴다."""
    a: str
    b: str
    r: float


class ClusterStat(BaseModel):
    cluster: int
    n: int
    center: dict[str, float] = Field(default_factory=dict)


class ModelMeta(BaseModel):
    name: str                         # "IsolationForest" / "GradientBoosting"
    task: str                         # "anomaly_detection" / "mold_identification"
    n_features: int
    notes: str = ""


class DataDigest(BaseModel):
    """LLM에 주입되는 유일한 그라운딩 객체. 모든 숫자는 코드가 계산한다(환각 차단)."""
    provenance: Provenance
    n_cycles: int
    period: str = ""
    cycle_type_dist: dict[str, int] = Field(default_factory=dict)
    anomaly_rate: float = 0.0
    mean_ct_sec: float = 0.0
    mold_models: list[MoldModelStat] = Field(default_factory=list)
    process_time: dict[str, StatBlock] = Field(default_factory=dict)
    top_correlations: list[Corr] = Field(default_factory=list)
    n_clusters: int = 0                 # 클러스터 총 개수(중심값은 토큰 예산상 미주입)
    models_in_use: list[ModelMeta] = Field(default_factory=list)
    field_dict: dict[str, FieldSpec] = Field(default_factory=dict)
    # --- 확장: 센서/분포 요약 (히스토그램은 빼고 요약 통계만) ---
    sensor_stats: dict[str, dict[str, float]] = Field(default_factory=dict)  # T1~8/P1~8 {mean,p1,p99}
    cycle_interval: dict[str, float] = Field(default_factory=dict)  # ci-hist {mean,p25,p50,p75,n}
    wait: dict[str, float] = Field(default_factory=dict)            # wait-dist {mean,p50,p75,p95,n}
    anomaly_categories: dict[str, int] = Field(default_factory=dict)  # {normal,genuine,quality}
    # 인용 가능 키(ref_keys)는 grounding.flatten_keys(digest.model_dump())로 데이터에서 자동 추출한다.
    # (도메인별 하드코딩 제거)

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
    "factual_error", "logical_error", "missing_content", "guideline_violation",
    "off_topic", "inconsistency", "unclear", "redundancy",
]


class Issue(BaseModel):
    type: IssueType
    severity: Literal["low", "medium", "high"]
    problem: str = Field(description="문제 설명")
    original_text: str = Field(default="", description="문제가 되는 원문 문장 또는 구절")
    fix_instruction: str = Field(description="수정 지시")


class ReviewResult(BaseModel):
    has_errors: bool
    score: int = Field(ge=0, le=100, description="0~100. 90 이상이면 수정 불필요")
    issues: list[Issue] = Field(default_factory=list)
    summary: str = Field(default="", description="전체 검수 요약")
    # 데이터 모드 전용: 본문에 나왔지만 digest에 없는 수치(환각 의심). 책 모드는 빈 채로 둔다.
    ungrounded_numbers: list[str] = Field(default_factory=list)


# =========================
# PLANNER (선택 단계)
# =========================
# Writer 앞에서 "무엇을 다룰지"만 구조체로 확정한다. 본문은 쓰지 않는다.
# 장르 무관(챕터/섹션/장면/에피소드 공통) — 그래서 이름은 UnitPlan.

class UnitPlan(BaseModel):
    unit_id: str = Field(description="대상 작성 단위 식별자")
    key_points: list[str] = Field(
        min_length=3, max_length=8,
        description="이 단위가 다룰 핵심 논점. 각 항목은 한 문장.",
    )
    data_refs: list[str] = Field(
        default_factory=list,
        description="인용할 digest 키 경로만(데이터 모드). 예: 'anomaly_rate', 'process_time.cool'.",
    )
    required_figures: list[str] = Field(default_factory=list, description="필요한 표/그림 제목 목록")
    out_of_scope: list[str] = Field(default_factory=list, description="이 단위에서 다루지 않을 것")


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

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
# OUTLINE PLANNER (선택 단계)
# =========================
# Writer 앞에서 본문 골격(outline)을 확정한다. 본문은 쓰지 않는다.
# 체크리스트(순서 없는 key_points)가 아니라 순서 있는 beats로 — writer가
# "창작"이 아니라 "설계서 구현"을 하도록 만든다. 분산↓, 하한↑.
# 장르 무관(챕터/섹션/장면/에피소드 공통) — 그래서 이름은 UnitPlan.

BeatRole = Literal["setup", "evidence", "analysis", "contrast", "payoff", "bridge"]


class Beat(BaseModel):
    """아웃라인의 한 노드 = 본문의 한 섹션. 위→아래로 읽으면 하나의 흐름이 된다."""
    claim: str = Field(description="완결된 단언 한 문장(토픽 나열 금지). 예: '쿨링타임이 변동의 최대 요인이다'")
    role: BeatRole = Field(description="이 beat가 글에서 하는 기능(도입/근거/분석/대조/결론/전환)")
    refs: list[str] = Field(
        default_factory=list,
        description="이 beat가 인용할 근거 키만(데이터 모드). 예: 'anomaly_rate', 'process_time.cool'. 없으면 빈 배열.",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="claim을 뒷받침하는 근거 속 실제 수치·사실·인용. 근거(grounding)에서 그대로 옮긴다(지어내지 않음). 근거가 없으면 빈 배열. 예: 'anomaly_rate=3.2%', '쿨링타임 p99=18s'.",
    )
    figure: str | None = Field(default=None, description="이 beat에 붙일 표/그림 제목(선택)")
    weight: Literal["minor", "normal", "major"] = Field(
        default="normal", description="분량·깊이 배분. major는 더 깊게, minor는 짧게.",
    )


class UnitPlan(BaseModel):
    unit_id: str = Field(description="대상 작성 단위 식별자")
    thesis: str = Field(description="이 단위가 결국 말하려는 것 한 문장. 모든 beat가 이를 받친다.")
    beats: list[Beat] = Field(
        min_length=3, max_length=8,
        description="thesis를 전개하는 순서 있는 본문 골격. 위→아래로 하나의 논증/서사가 되도록 배열.",
    )
    builds_on: list[str] = Field(
        default_factory=list,
        description="이전 단위에서 이미 다뤄 반복하지 않을 내용.",
    )
    out_of_scope: list[str] = Field(default_factory=list, description="이 단위에서 다루지 않을 것(옆 단위 몫).")
    hook: str = Field(default="", description="도입 한 문장(선택).")
    bridge_to_next: str = Field(default="", description="다음 단위로 넘기는 한 문장(선택).")


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

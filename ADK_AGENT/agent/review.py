"""
review 단계 — 구조화 검수(review) + 게이트 판정(gate). 판정 한 쌍.

- review: call_structured 로 ReviewResult(JSON) 강제 → state["review"]. 미수렴 시 flagged 후 종료 유도.
- gate: 현 while 루프 판단을 ctx.route 로. 위반은 0까지 고치고(must_fix), 품질은 오르는 한
  끌어올리고(want_lift), 천장(점수 정체)이나 상한(PASS_MAX)이면 수용 → finalize 로 라우팅.
"""
from google.adk.workflow import FunctionNode

from core.llm import call_structured, ConvergenceError
from core.source_reader import unverified_numbers
from agent.schemas import ReviewResult
from agent.prompts import REVIEW_SYSTEM, review_user

PASS_MAX = 3         # review→revise 재수정 상한
VIOLATION_TYPES = {
    "factual_error", "logical_error", "missing_content",
    "off_topic", "unsupported_claim", "source_misalignment",
}


def review_fn(ctx):
    s = ctx.state
    try:
        review = call_structured(
            REVIEW_SYSTEM,
            review_user(s["config"], s["chapter"], s["draft"], s.get("grounding", "")),
            ReviewResult, temperature=0.2)
        s["review"] = review.model_dump()
        print(f"    [검수] score {review.score} · issues {len(review.issues)} · "
              f"needs_revision {review.needs_revision}")
    except ConvergenceError as e:
        s["flagged"] = True
        s["force_done"] = True
        print(f"    [검수 미수렴] {e} — flagged 후 종료")


def gate_fn(ctx):
    s = ctx.state
    if s.get("force_done"):                            # 검수 실패 등 → 즉시 종료
        ctx.route = "done"
        return

    review = ReviewResult(**s["review"])
    bad = unverified_numbers(s["draft"], s.get("grounding", "")) if s.get("grounding") else []
    if bad:
        review.unverified_numbers = sorted(set(review.unverified_numbers) | set(bad))
        s["review"] = review.model_dump()

    violations = [i for i in review.issues if i.type in VIOLATION_TYPES]
    weak = {k: v for k, v in review.quality.model_dump().items() if v < s["quality_gate"]}
    must_fix = bool(violations or bad)
    want_lift = bool(weak) or review.score < s["target_score"] or review.needs_revision

    s["pass_count"] = s.get("pass_count", 0) + 1
    stop = False
    if not must_fix and not want_lift:
        stop = True                                    # 완료
    elif not must_fix and review.score <= s.get("last_score", -1):
        stop = True                                    # 천장(점수 정체) → 수용
    elif s["pass_count"] > PASS_MAX:
        stop = True                                    # 재수정 상한
    s["last_score"] = review.score

    if stop:
        kind = "완료" if (not must_fix and not want_lift) else "수용(천장/상한)"
        print(f"    [게이트] 종료 — {kind} (score {review.score}, 위반 {len(violations)})")
        ctx.route = "done"
    else:
        kind = "고침+끌어올림" if must_fix else "끌어올림"
        print(f"    [게이트] 재수정({kind}) 위반 {len(violations)} · 약한축 {list(weak)}")
        ctx.route = "revise"


def build_review_node() -> FunctionNode:
    return FunctionNode(func=review_fn, name="review")


def build_gate_node() -> FunctionNode:
    return FunctionNode(func=gate_fn, name="gate")

"""
③ Review agent — 학회 리뷰어 + 게이트 판정.

★ 생성과 다른 모델(REVIEW_MODEL, Qwen 계열)로 검수한다 — 자기 실수를 더 잘 잡는다.
  - do_review : call_structured(REVIEW_MODEL)로 ReviewResult 강제 + keep-best.
  - gate_decision : 위반은 0까지 고치고(must_fix), 품질은 오르는 한 끌어올리되(want_lift),
    천장(점수 정체)이나 상한(PASS_MAX)이면 수용.
"""
from core.llm import call_structured, ConvergenceError
from core.config import REVIEW_MODEL, PASS_MAX, T_REVIEW
from core.grounding import unverified_numbers, ground_block
from agents.common import ReviewResult


REVIEW_SYS = """
당신은 학술 논문 심사위원(reviewer)입니다. 한 섹션의 원고를 심사합니다.
목표는 문장을 예쁘게 다듬는 것이 아니라, (1) 틀리거나 근거 없는 곳을 잡고
(2) 게재 수준으로 끌어올릴 가장 효과 큰 개선점을 짚는 것입니다.

[1단계 · 오류와 위반 — 반드시 고쳐야 할 것 (issues로 보고)]
- factual_error: 사실/기술적으로 틀림
- claim_evidence_mismatch: 주장과 결과(표/그림/수치)가 어긋남
- unsupported_claim: 근거(데이터) 없이 구체 수치·결과를 단정
- overclaiming: 결과가 뒷받침하는 것보다 과장된 일반화
- missing_baseline: 비교 대상/기준선이 없어 주장 검증 불가
- unreferenced_artifact: 표/그림이 본문에서 \\ref 로 참조되지 않음
- logical_error: 앞뒤 논리가 안 맞음
- off_topic: 이 섹션의 role 에서 벗어남
- missing_content: 섹션 key_points 에 있는데 빠짐

[2단계 · 품질 — 게재 수준으로 끌어올릴 것 (issues로 보고)]
- related_work_gap: 맥락/관련연구 반영 부족
- reproducibility_gap: 재현에 필요한 설정·조건·지표 정의가 부족
- clarity_problem / structure_problem / depth_problem / redundancy
- surface_error: 오타·깨진 LaTeX·이스케이프 안 된 특수문자·라벨 오류

심사 규칙:
- 트집을 늘어놓지 말고, 논문의 설득력을 가장 크게 높이는 3~6개에 집중하세요.
- 각 이슈는 original_text(문제 구절 인용)와 fix_instruction(구체적 수정법)을 채우세요.
- severity: 오류/위반은 최소 medium(사실/근거 오류는 high). 품질·표면은 보통 medium/low.

[품질 점수 — quality (6축, 0~100)]
- novelty / soundness / clarity / significance / reproducibility / related_work
- 섹션 성격상 해당 약한 축(예: method 의 novelty)은 맥락이 적절하면 감점하지 말고 높게.
- 점수와 issue 는 일치해야 합니다: 어떤 축이 80 미만이면 그 축의 issue 를 반드시 남기세요.

[실측 자료가 있는 경우]
- 본문 수치 중 자료에서 확인되지 않는 값은 unverified_numbers 에 나열(없으면 빈 배열).
- 자료와 충돌/왜곡/과장 여부를 확인하세요.

출력은 제공된 JSON 스키마를 정확히 따르세요.
- score: 종합 점수. 오류·위반이 없고 품질이 고르게 높으면 90+. 사실/근거 오류가 있으면 90 미만.
- needs_revision: 오류·위반이 있거나 품질이 목표에 못 미치면 true.
"""


def review_user(plan: dict, section: dict, draft: str, grounding: str = "") -> str:
    import json
    return f"""
논문 개요:
제목: {plan.get('title','')}
기여: {'; '.join(plan.get('contributions', []))}

이 섹션의 계획:
{json.dumps(section, ensure_ascii=False, indent=2)}
{ground_block(grounding)}
심사할 원고(LaTeX 본문):
{draft}

위 원고를 심사해주세요.
"""


VIOLATION_TYPES = {
    "factual_error", "claim_evidence_mismatch", "unsupported_claim", "overclaiming",
    "missing_baseline", "unreferenced_artifact", "logical_error",
    "off_topic", "missing_content",
}


def do_review(state: dict) -> tuple[dict, str | None]:
    """검수 실행(다른 모델) + keep-best 계산. 반환: (state 변경분, 에러 or None).

    keep-best: revise 가 초안을 망가뜨려도 최고 점수 버전을 보존한다.
    """
    try:
        review = call_structured(
            REVIEW_SYS,
            review_user(state["plan"], state["section"], state["draft"], state.get("grounding", "")),
            ReviewResult, temperature=T_REVIEW, model=REVIEW_MODEL)
    except ConvergenceError as e:
        return {"flagged": True, "force_done": True}, str(e)

    updates = {"review": review.model_dump()}
    if review.score > state.get("best_score", -1):
        updates["best_score"] = review.score
        updates["best_draft"] = state.get("draft", "")
        updates["best_review"] = review.model_dump()
    return updates, None


def gate_decision(state: dict) -> tuple[bool, dict, dict]:
    """게이트 판정(순수). 반환: (stop, info(로그용), state 변경분)."""
    if state.get("force_done"):
        return True, {"kind": "완료(검수실패)", "score": 0, "violations": 0,
                      "weak": {}, "unverified": []}, {}

    review = ReviewResult(**state["review"])
    bad = (unverified_numbers(state["draft"], state.get("grounding", ""))
           if state.get("grounding") else [])
    updates: dict = {}
    if bad:
        review.unverified_numbers = sorted(set(review.unverified_numbers) | set(bad))
        updates["review"] = review.model_dump()

    violations = [i for i in review.issues if i.type in VIOLATION_TYPES]
    weak = {k: v for k, v in review.quality.model_dump().items() if v < state["quality_gate"]}
    must_fix = bool(violations or bad)
    want_lift = bool(weak) or review.score < state["target_score"] or review.needs_revision

    pass_count = state.get("pass_count", 0) + 1
    updates["pass_count"] = pass_count
    stop = False
    if not must_fix and not want_lift:
        stop = True                                    # 완료
    elif not must_fix and review.score <= state.get("last_score", -1):
        stop = True                                    # 천장(점수 정체) → 수용
    elif pass_count > PASS_MAX:
        stop = True                                    # 재수정 상한
    updates["last_score"] = review.score

    if stop:
        kind = "완료" if (not must_fix and not want_lift) else "수용(천장/상한)"
    else:
        kind = "고침+끌어올림" if must_fix else "끌어올림"
    info = {"kind": kind, "score": review.score, "violations": len(violations),
            "weak": weak, "unverified": bad}
    return stop, info, updates

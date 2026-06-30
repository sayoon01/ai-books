"""
review 단계 — 구조화 검수(review) + 게이트 판정(gate). 판정 한 쌍.

- review: call_structured 로 ReviewResult(JSON) 강제 → state["review"]. 미수렴 시 flagged 후 종료 유도.
- gate: 현 while 루프 판단을 ctx.route 로. 위반은 0까지 고치고(must_fix), 품질은 오르는 한
  끌어올리고(want_lift), 천장(점수 정체)이나 상한(PASS_MAX)이면 수용 → finalize 로 라우팅.
"""
import json

from google.adk.workflow import FunctionNode

from core.llm import call_structured, ConvergenceError
from core.grounding import unverified_numbers, ground_block
from core.config import PASS_MAX        # review→revise 재수정 상한
from agent.common import ReviewResult, record


# =========================
# REVIEWER 프롬프트 (정적)
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


VIOLATION_TYPES = {
    "factual_error", "logical_error", "missing_content",
    "off_topic", "unsupported_claim", "source_misalignment",
}


def do_review(state: dict) -> tuple[dict, str | None]:
    """검수 실행 + keep-best 계산(순수). 반환: (state 변경분 updates, 에러메시지 or None).

    그래프 review_fn 과 멀티에이전트 Reviewer 가 공유한다(단일 출처).
    keep-best: revise 가 초안을 망가뜨려도(점수 급락) 최고 점수 버전을 보존한다.
    (배경: revise 가 본문 대신 "수정 완료" 메시지를 뱉어 4808자→1045자로 붕괴한 사건.)
    """
    try:
        review = call_structured(
            REVIEW_SYSTEM,
            review_user(state["config"], state["chapter"], state["draft"], state.get("grounding", "")),
            ReviewResult, temperature=0.2)
    except ConvergenceError as e:
        return {"flagged": True, "force_done": True}, str(e)

    updates = {"review": review.model_dump()}
    if review.score > state.get("best_score", -1):
        updates["best_score"] = review.score
        updates["best_draft"] = state.get("draft", "")
        updates["best_review"] = review.model_dump()
    return updates, None


def gate_decision(state: dict) -> tuple[bool, dict, dict]:
    """게이트 판정(순수). 반환: (stop, info(로그용), state 변경분 updates).

    그래프 gate_fn 과 멀티에이전트 Gate 가 공유한다(단일 출처).
    """
    if state.get("force_done"):                        # 검수 실패 등 → 즉시 종료
        return True, {"kind": "완료(검수실패)", "score": 0, "violations": 0,
                      "weak": {}, "unverified": []}, {}

    review = ReviewResult(**state["review"])
    bad = unverified_numbers(state["draft"], state.get("grounding", "")) if state.get("grounding") else []
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


def review_fn(ctx):
    s = ctx.state
    updates, err = do_review(s)
    s.update(updates)
    if err:
        print(f"    [검수 미수렴] {err} — flagged 후 종료")
        record(ctx, stage="review", error=err, reviewed_draft=s.get("draft", ""))
    else:
        r = updates["review"]
        print(f"    [검수] score {r['score']} · issues {len(r['issues'])} · "
              f"needs_revision {r['needs_revision']} · best {s.get('best_score')}")
        record(ctx, stage="review", reviewed_draft=s.get("draft", ""), review=r)


def gate_fn(ctx):
    s = ctx.state
    stop, info, updates = gate_decision(s)
    s.update(updates)
    ctx.route = "done" if stop else "revise"
    if stop:
        print(f"    [게이트] 종료 — {info['kind']} (score {info['score']}, 위반 {info['violations']})")
    else:
        print(f"    [게이트] 재수정({info['kind']}) 위반 {info['violations']} · 약한축 {list(info['weak'])}")
    record(ctx, stage="gate", route=ctx.route, decision=info["kind"], score=info["score"],
           pass_count=s.get("pass_count"), violations=info["violations"],
           weak_axes=info["weak"], unverified=info["unverified"])


def build_review_node() -> FunctionNode:
    return FunctionNode(func=review_fn, name="review")


def build_gate_node() -> FunctionNode:
    return FunctionNode(func=gate_fn, name="gate")

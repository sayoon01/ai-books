import json
from pathlib import Path

from prompts import (
    WRITE_SYSTEM, REVIEW_SYSTEM, REVISE_SYSTEM, PLAN_SYSTEM,
    write_user, review_user, revise_user, plan_user,
)
from llm import _call, call_structured, ConvergenceError
from schemas import ReviewResult, UnitPlan
from grounding import resolve_grounding, ungrounded_numbers
from github_push import push_unit, update_meta, update_readme

# 작성 단위 키 (신규 표준 units, 옛 toc 폴백)
_UNITS_KEYS = ("units", "chapters", "sections")
# config에서 제외할 키 (단위 목록 + grounding 설정)
_SKIP_KEYS = set(_UNITS_KEYS) | {"grounding"}


def _units(doc: dict) -> list:
    for k in _UNITS_KEYS:
        if k in doc:
            return doc[k]
    return []


def _config(doc: dict) -> dict:
    """단위 목록과 grounding 설정을 제외한 문서 설정."""
    return {k: v for k, v in doc.items() if k not in _SKIP_KEYS}


def _strip_title_h1(text: str) -> str:
    """본문 맨 앞에 단위 제목 H1(`# ...`)이 중복되면 제거. 소제목(`## ...`)은 보존."""
    s = text.lstrip()
    if s.startswith("# "):
        parts = s.split("\n", 1)
        return parts[1].lstrip("\n") if len(parts) > 1 else ""
    return text


# =========================
# 단계별 호출
# =========================
def _plan_unit(config, unit, previous, grounding) -> UnitPlan:
    print("  [계획] 단위 설계 중...")
    gtext = grounding.payload if grounding else ""

    def _check(plan: UnitPlan) -> UnitPlan:
        if grounding and grounding.ref_keys:
            bad = sorted({r for s in plan.steps for r in s.refs
                          if r not in grounding.ref_keys})
            if bad:
                raise ValueError(f"근거에 없는 step refs: {bad}")
        if grounding:
            # 근거가 있으면 support는 실제 근거에서만 가져와야 한다(결정적 수치 검증).
            sup = " ".join(t for s in plan.steps for t in s.support)
            bad_nums = ungrounded_numbers(sup, grounding.payload)
            if bad_nums:
                raise ValueError(f"근거에 없는 support 수치: {bad_nums}")
        return plan

    return call_structured(PLAN_SYSTEM, plan_user(config, unit, previous, gtext),
                           UnitPlan, temperature=0.3, post_validate=_check)


def _write_unit(config, unit, previous, gtext, plan=None) -> str:
    print(f"  [초안] {unit.get('title', '')}")
    return _call(WRITE_SYSTEM, write_user(config, unit, previous, gtext, plan), temperature=0.8)


def _review_unit(config, unit, draft, gtext, step="검수", plan=None) -> ReviewResult:
    print(f"  [{step}] 검수 중...")
    result = call_structured(REVIEW_SYSTEM, review_user(config, unit, draft, gtext, plan),
                             ReviewResult, temperature=0.2)
    print(f"         → score: {result.score}  issues: {len(result.issues)}  "
          f"has_errors: {result.has_errors}  ungrounded: {len(result.ungrounded_numbers)}")
    return result


def _revise_unit(config, unit, draft, review: ReviewResult, gtext, plan=None) -> str:
    print("  [수정] 수정 중...")
    return _call(REVISE_SYSTEM,
                 revise_user(config, unit, draft, review.model_dump_json(indent=2), gtext, plan),
                 temperature=0.5)


# 게이트 기준 — 두 family를 다르게 다룬다.
# - 위반(사실·논리·누락·이탈·미근거 단정)은 "고친다": 0이 될 때까지.
# - 품질(깊이·명료·구성·설득·창의·문체)은 "끌어올린다": 점수가 오르는 한 계속, 천장이면 수용.
# doc_type로 장르 분기하지 않고, reviewer가 해당 없는 축을 높게 주는 전제의 범용 임계.
QUALITY_GATE = 80   # 이 점수 미만 축이 있으면 끌어올림 대상
TARGET_SCORE = 90   # 종합 목표 점수
MAX_PASSES = 3      # 재수정 최대 횟수 (무한루프·천장 방지)

# "반드시 고칠" 오류/위반 타입. 나머지(*_problem)는 "끌어올릴" 품질.
VIOLATION_TYPES = {
    "factual_error", "logical_error", "missing_content",
    "off_topic", "unsupported_claim",
}


def _violations(review: ReviewResult) -> list:
    """반드시 고쳐야 할 오류/위반 issue (품질 issue 제외)."""
    return [i for i in review.issues if i.type in VIOLATION_TYPES]


def _weak_axes(review: ReviewResult) -> dict[str, int]:
    """QUALITY_GATE 미만인 품질 축 {이름: 점수} — 끌어올림 대상."""
    return {k: v for k, v in review.quality.model_dump().items() if v < QUALITY_GATE}


# =========================
# 메인 루프 (장르 무관)
# =========================
def generate(doc: dict, output_dir: Path, slug: str, *, use_planner: bool = False) -> None:
    title = doc["title"]
    units = _units(doc)
    config = _config(doc)
    grounding = resolve_grounding(doc.get("grounding"), slug)
    gtext = grounding.payload if grounding else ""

    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    g_src = grounding.provenance.get("source", "?") if grounding else "없음"
    print(f"\n생성 시작: {title}  (단위 {len(units)}개, grounding={g_src})\n")

    summaries = []  # 이전 단위 요약 (다음 단위 프롬프트에 주입)

    for i, unit in enumerate(units, 1):
        num = unit.get("number", i)
        utitle = unit["title"]
        print(f"--- 단위 {num}: {utitle} ---")

        draft = None
        plan = None
        quality_log = {"unit": {"number": num, "title": utitle},
                       "revised": False, "re_review": None, "flagged": False}
        try:
            if use_planner:
                plan = _plan_unit(config, unit, summaries[:], grounding)
                quality_log["plan"] = plan.model_dump()

            plan_dump = plan.model_dump() if plan else None
            draft = _write_unit(config, unit, summaries[:], gtext, plan_dump)
            review = _review_unit(config, unit, draft, gtext, plan=plan_dump)
            quality_log["initial_review"] = review.model_dump()
            quality_log["passes"] = []
            final = draft

            # 위반은 0이 될 때까지 "고치고", 품질은 점수가 오르는 한 "끌어올린다".
            passes = 0
            while passes < MAX_PASSES:
                # 결정적 수치 검증: 본문 수치가 근거에 실재하는지 코드로 대조(LLM 판단과 무관).
                bad_nums = ungrounded_numbers(final, gtext) if grounding else []
                if bad_nums:
                    review.ungrounded_numbers = sorted(
                        set(review.ungrounded_numbers) | set(bad_nums))

                violations = _violations(review)      # 고칠 것
                weak = _weak_axes(review)             # 끌어올릴 것
                must_fix = bool(review.has_errors or violations or bad_nums)
                want_lift = bool(weak) or review.score < TARGET_SCORE

                if passes == 0:
                    if bad_nums:
                        quality_log["ungrounded_detected"] = bad_nums
                        print(f"  [근거검증] 본문 미근거 수치 {len(bad_nums)}건: {bad_nums[:8]}")
                    if weak:
                        quality_log["weak_axes"] = weak
                        print(f"  [품질] 약한 축: {weak}")

                if not must_fix and not want_lift:
                    if passes == 0:
                        print(f"  [수정 불필요] score {review.score} — 저장")
                    break

                kind = "고침+끌어올림" if must_fix else "끌어올림"
                print(f"  [수정·{passes + 1}] ({kind}) 위반 {len(violations)} · 약한축 {list(weak)}")
                revised = _revise_unit(config, unit, final, review, gtext, plan=plan_dump)
                re_review = _review_unit(config, unit, revised, gtext, step="재검수", plan=plan_dump)
                improved = re_review.score > review.score
                passes += 1

                re_bad = ungrounded_numbers(revised, gtext) if grounding else []
                quality_log["passes"].append({
                    "re_review": re_review.model_dump(),
                    "improved": improved,
                    "ungrounded_remaining": re_bad,
                    "weak_axes_remaining": _weak_axes(re_review),
                })

                final = revised
                review = re_review

                # 끌어올림만 남았는데(위반·미근거 없음) 점수가 더 안 오르면 천장 → 수용.
                if not (re_review.has_errors or _violations(re_review) or re_bad) and not improved:
                    print(f"  [천장] 품질 점수 정체(score {re_review.score}) — 현재 버전 수용")
                    break

            quality_log["revised"] = passes > 0

            # 종료 후 잔여 위반/미근거 점검 → 경고(고침은 0이 목표였으므로).
            final_bad = ungrounded_numbers(final, gtext) if grounding else []
            final_violations = _violations(review)
            if final_violations or final_bad or review.has_errors:
                high = [i for i in final_violations if i.severity == "high"]
                quality_log["unresolved"] = {
                    "violations": [i.model_dump() for i in final_violations],
                    "ungrounded": final_bad,
                }
                print(f"  [잔여] 위반 {len(final_violations)}건(high {len(high)}) · "
                      f"미근거수치 {len(final_bad)}건 — 현재 버전으로 저장")

        except ConvergenceError as e:
            quality_log["flagged"] = True
            quality_log["error"] = str(e)
            print(f"  [미수렴] {e} — 플래그 후 진행")
            final = draft if draft is not None else f"<!-- 생성 실패: {e} -->"

        content = f"# {num}. {utitle}\n\n{_strip_title_h1(final)}"
        filename = f"unit-{num:02d}.md"
        (output_dir / filename).write_text(content, encoding="utf-8")
        (log_dir / f"unit-{num:02d}-review.json").write_text(
            json.dumps(quality_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  저장: {filename}")

        # 항상 자동 푸시
        push_unit(slug, num, utitle, content)
        update_meta(slug, doc, completed=num)

        # 다음 단위 연결: 설계의 bridge_to_next가 있으면 그것을, 없으면 단위 설명을 요약으로.
        desc = (plan.bridge_to_next if plan and plan.bridge_to_next
                else unit.get("description") or unit.get("intent", ""))
        summaries.append(f"{num}. {utitle}: {desc}")
        print()

    update_readme(slug, doc)
    print(f"[완료] {title}")


# 하위호환 — 기존 호출부 유지
def generate_book(toc: dict, output_dir: Path, slug: str) -> None:
    generate(toc, output_dir, slug)

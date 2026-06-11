import json
from pathlib import Path

from prompts import (
    WRITE_SYSTEM, REVIEW_SYSTEM, REVISE_SYSTEM, PLAN_SYSTEM,
    write_user, review_user, revise_user, plan_user,
)
from llm import _call, call_structured, ConvergenceError
from schemas import ReviewResult, UnitPlan
from grounding import resolve_grounding
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
            bad = [r for r in plan.data_refs if r not in grounding.ref_keys]
            if bad:
                raise ValueError(f"근거에 없는 data_refs: {bad}")
        return plan

    return call_structured(PLAN_SYSTEM, plan_user(config, unit, previous, gtext),
                           UnitPlan, temperature=0.3, post_validate=_check)


def _write_unit(config, unit, previous, gtext) -> str:
    print(f"  [초안] {unit.get('title', '')}")
    return _call(WRITE_SYSTEM, write_user(config, unit, previous, gtext), temperature=0.8)


def _review_unit(config, unit, draft, gtext, step="검수") -> ReviewResult:
    print(f"  [{step}] 검수 중...")
    result = call_structured(REVIEW_SYSTEM, review_user(config, unit, draft, gtext),
                             ReviewResult, temperature=0.2)
    print(f"         → score: {result.score}  issues: {len(result.issues)}  "
          f"has_errors: {result.has_errors}  ungrounded: {len(result.ungrounded_numbers)}")
    return result


def _revise_unit(config, unit, draft, review: ReviewResult, gtext) -> str:
    print("  [수정] 수정 중...")
    return _call(REVISE_SYSTEM,
                 revise_user(config, unit, draft, review.model_dump_json(indent=2), gtext),
                 temperature=0.5)


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
        quality_log = {"unit": {"number": num, "title": utitle},
                       "revised": False, "re_review": None, "flagged": False}
        try:
            ctx = unit
            if use_planner:
                plan = _plan_unit(config, unit, summaries[:], grounding)
                ctx = {**unit, "_plan": plan.model_dump()}
                quality_log["plan"] = plan.model_dump()

            draft = _write_unit(config, ctx, summaries[:], gtext)
            review = _review_unit(config, ctx, draft, gtext)
            quality_log["initial_review"] = review.model_dump()
            final = draft

            if review.has_errors or review.score < 90:
                revised = _revise_unit(config, ctx, draft, review, gtext)
                re_review = _review_unit(config, ctx, revised, gtext, step="재검수")
                final = revised
                quality_log["revised"] = True
                quality_log["re_review"] = re_review.model_dump()
                if re_review.has_errors or re_review.score < 90:
                    remaining = [x for x in re_review.issues if x.severity == "high"]
                    print(f"  [재검수] 잔여 high 이슈 {len(remaining)}건 — 현재 버전으로 저장")
            else:
                print(f"  [수정 불필요] score {review.score} — 저장")

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

        desc = unit.get("description") or unit.get("intent", "")
        summaries.append(f"{num}. {utitle}: {desc}")
        print()

    update_readme(slug, doc)
    print(f"[완료] {title}")


# 하위호환 — 기존 호출부 유지
def generate_book(toc: dict, output_dir: Path, slug: str) -> None:
    generate(toc, output_dir, slug)

"""
책/문서 생성기 (장르 무관).

흐름: (목차 자동생성) → 챕터마다 [초안 → 검수 → 수정] → 저장 + GitHub 푸시
- chapters가 있으면 그대로, 없으면 grounding(없으면 description)으로 목차 자동 생성.
- 검수/목차는 Pydantic 구조화 출력(call_structured)으로 형식 보장 + 재시도.
- 모델은 gemma4:31b 고정 (별도 llm.py 없이 이 파일에 내장).
"""
import json
import re
from pathlib import Path
from typing import Callable, TypeVar

import ollama
from pydantic import BaseModel, ValidationError

from prompts import (
    OUTLINE_SYSTEM, outline_user,
    WRITE_SYSTEM,  write_user,
    REVIEW_SYSTEM, review_user,
    REVISE_SYSTEM, revise_user,
    PLAN_SYSTEM, plan_user,
)
from schemas import ReviewResult, OutlinePlan, UnitPlan
from grounding import resolve_grounding, unverified_numbers
from github_push import push_chapter, update_meta, update_readme, push_pdf, REPO_ROOT
from pdf_export import build_pdf


# =========================
# LLM 호출 (gemma 고정, 내장)
# =========================
MODEL = "gemma4:31b"
_OPTIONS = {"temperature": 0.7, "num_ctx": 32768, "repeat_penalty": 1.2}

T = TypeVar("T", bound=BaseModel)


class ConvergenceError(Exception):
    """재시도 한도까지 스키마 검증을 통과하지 못함. 해당 챕터는 플래그 후 진행."""


def _call(system: str, user: str, temperature: float) -> str:
    """자유 텍스트 생성 (초안·수정)."""
    res = ollama.chat(
        model=MODEL,
        options={**_OPTIONS, "temperature": temperature},
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    return res["message"]["content"]


def call_structured(system: str, user: str, schema: type[T], temperature: float,
                    retries: int = 2, post_validate: Callable[[T], T] | None = None) -> T:
    """Pydantic 스키마 강제(ollama format=) + 실패 시 에러를 모델에 되먹여 재시도."""
    msg = [{"role": "system", "content": system},
           {"role": "user", "content": user}]
    last_err: Exception | None = None

    for _ in range(retries + 1):
        raw = ollama.chat(
            model=MODEL,
            format=schema.model_json_schema(),          # ★ 구조화 출력 강제
            options={**_OPTIONS, "temperature": temperature},
            messages=msg,
        )["message"]["content"]
        try:
            obj = schema.model_validate_json(raw)
            return post_validate(obj) if post_validate else obj
        except (ValidationError, ValueError) as e:
            last_err = e
            msg.append({"role": "assistant", "content": raw})
            msg.append({"role": "user",
                        "content": f"검증 실패:\n{e}\n같은 JSON 스키마를 정확히 지켜 다시 작성하세요."})

    raise ConvergenceError(f"{schema.__name__} 미수렴 ({retries + 1}회 시도): {last_err}")


# =========================
# spec(config) 처리
# =========================
# config에서 제외할 키: 챕터 목록(루프로 따로) + grounding(설정값, 따로 해소)
_SKIP_KEYS = {"chapters", "grounding"}
# 필수 필드
_REQUIRED = ("title", "language", "description", "target_reader", "writing_guidelines")
# 목차 자동 생성 시 챕터 수
DEFAULT_CHAPTER_COUNT = 10


def validate_spec(doc: dict) -> None:
    missing = [k for k in _REQUIRED if not doc.get(k)]
    if missing:
        raise ValueError(f"필수 필드 누락: {missing}")


def _config(doc: dict) -> dict:
    """챕터 목록·grounding을 제외한 책 설정(정체성). 프롬프트에 통째로 주입됨."""
    return {k: v for k, v in doc.items() if k not in _SKIP_KEYS}


def _chapters(doc: dict) -> list:
    return doc.get("chapters", [])


def _slugify(text: str) -> str:
    """제목 → 파일명 슬러그. 한국어(\\w)는 보존하고 공백/언더스코어는 '-'로."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)          # 연속 하이픈 합치기
    return s.strip("-")


def _chapter_filename(num: int, title: str) -> str:
    slug = _slugify(title)
    return f"chapter-{num:02d}-{slug}.md" if slug else f"chapter-{num:02d}.md"


def _strip_title_h1(text: str) -> str:
    """본문 맨 앞에 제목 H1(`# ...`)이 중복되면 제거. 소제목(`## ...`)은 보존."""
    s = text.lstrip()
    if s.startswith("# "):
        parts = s.split("\n", 1)
        return parts[1].lstrip("\n") if len(parts) > 1 else ""
    return text


# =========================
# 목차 자동 생성
# =========================
def _parse_json(raw: str) -> dict:
    """자유 텍스트 응답에서 JSON 객체만 추출해 파싱."""
    text = raw.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group()
    return json.loads(text.strip())


def plan_outline(config: dict, gtext: str, n: int = DEFAULT_CHAPTER_COUNT) -> list[dict]:
    src = "근거 자료" if gtext else "책 설명(description)"
    print(f"  [목차 생성] {src} 기반 {n}개 챕터 생성 중...")
    # 목차는 구조화 출력(format=schema) 대신 자유 텍스트+파싱.
    # 제약 디코딩이 목차(리스트) 생성에서 비정상적으로 느려 자유 생성으로 대체한다.
    raw = _call(OUTLINE_SYSTEM, outline_user(config, gtext, n), temperature=0.5)
    plan = OutlinePlan(**_parse_json(raw))           # JSON 파싱 후 Pydantic 검증
    chapters = [c.model_dump() for c in plan.chapters]
    for i, c in enumerate(chapters, 1):
        if not c.get("number"):
            c["number"] = i
    return chapters


# =========================
# 챕터 단계별 호출
# =========================
def _plan_chapter(config, chapter, previous, grounding) -> UnitPlan:
    """챕터별 본문 설계(thesis/steps)."""
    print("  [계획] 챕터 설계 중...")
    gtext = grounding.payload if grounding else ""
    return call_structured(PLAN_SYSTEM, plan_user(config, chapter, previous, gtext),
                           UnitPlan, temperature=0.3)


def _write_chapter(config, chapter, previous, gtext, plan=None) -> str:
    print(f"  [초안] {chapter.get('title', '')}")
    return _call(WRITE_SYSTEM, write_user(config, chapter, previous, gtext, plan), temperature=0.8)


def _review_chapter(config, chapter, draft, gtext, step="검수", plan=None) -> ReviewResult:
    print(f"  [{step}] 검수 중...")
    result = call_structured(REVIEW_SYSTEM, review_user(config, chapter, draft, gtext, plan),
                             ReviewResult, temperature=0.2)
    print(f"         → score: {result.score}  issues: {len(result.issues)}  "
          f"needs_revision: {result.needs_revision}  unverified: {len(result.unverified_numbers)}")
    return result


def _revise_chapter(config, chapter, draft, review: ReviewResult, gtext, plan=None) -> str:
    print("  [수정] 수정 중...")
    return _call(REVISE_SYSTEM,
                 revise_user(config, chapter, draft, review.model_dump_json(indent=2), gtext, plan),
                 temperature=0.5)


# 게이트 기준 — 두 family를 다르게 다룬다.
# - 위반(사실·논리·누락·이탈·미근거 단정)은 "고친다": 0이 될 때까지.
# - 품질(깊이·명료·구성·설득·창의·문체)은 "끌어올린다": 점수가 오르는 한 계속, 천장이면 수용.
QUALITY_GATE = 80   # 이 점수 미만 축이 있으면 끌어올림 대상
TARGET_SCORE = 90   # 종합 목표 점수
MAX_PASSES = 3      # 재수정 최대 횟수 (무한루프·천장 방지)

VIOLATION_TYPES = {
    "factual_error", "logical_error", "missing_content",
    "off_topic", "unsupported_claim", "source_misalignment",
}


def _violations(review: ReviewResult) -> list:
    return [i for i in review.issues if i.type in VIOLATION_TYPES]


def _weak_axes(review: ReviewResult) -> dict[str, int]:
    return {k: v for k, v in review.quality.model_dump().items() if v < QUALITY_GATE}


# =========================
# 메인 루프
# =========================
def generate(doc: dict, output_dir: Path, slug: str, *, use_planner: bool = False) -> None:
    validate_spec(doc)
    title = doc["title"]
    config = _config(doc)
    grounding = resolve_grounding(doc.get("grounding"), slug)
    gtext = grounding.payload if grounding else ""

    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    chapters = _chapters(doc)
    if not chapters:                                   # 목차 자동 생성
        chapters = plan_outline(config, gtext)
        (output_dir / "_outline.json").write_text(
            json.dumps(chapters, ensure_ascii=False, indent=2), encoding="utf-8")
        doc["chapters"] = chapters                     # meta/readme용
        print(f"  [목차 생성] {len(chapters)}개 챕터 완성 → _outline.json")

    g_src = grounding.provenance.get("source", "?") if grounding else "없음"
    print(f"\n생성 시작: {title}  (챕터 {len(chapters)}개, grounding={g_src})\n")

    summaries = []  # 이전 챕터 요약 (다음 챕터 프롬프트에 주입)

    for i, chapter in enumerate(chapters, 1):
        num = chapter.get("number", i)
        ctitle = chapter["title"]
        print(f"--- 챕터 {num}: {ctitle} ---")

        draft = None
        plan = None
        quality_log = {"chapter": {"number": num, "title": ctitle},
                       "revised": False, "flagged": False}
        try:
            if use_planner:
                plan = _plan_chapter(config, chapter, summaries[:], grounding)
                quality_log["plan"] = plan.model_dump()

            plan_dump = plan.model_dump() if plan else None
            draft = _write_chapter(config, chapter, summaries[:], gtext, plan_dump)
            review = _review_chapter(config, chapter, draft, gtext, plan=plan_dump)
            quality_log["initial_review"] = review.model_dump()
            quality_log["passes"] = []
            final = draft

            # 위반은 0이 될 때까지 "고치고", 품질은 점수가 오르는 한 "끌어올린다".
            passes = 0
            while passes < MAX_PASSES:
                bad_nums = unverified_numbers(final, gtext) if grounding else []
                if bad_nums:
                    review.unverified_numbers = sorted(
                        set(review.unverified_numbers) | set(bad_nums))

                violations = _violations(review)
                weak = _weak_axes(review)
                must_fix = bool(violations or bad_nums)
                want_lift = bool(weak) or review.score < TARGET_SCORE or review.needs_revision

                if passes == 0:
                    if bad_nums:
                        quality_log["unverified_detected"] = bad_nums
                        print(f"  [근거검증] 미확인 수치 {len(bad_nums)}건: {bad_nums[:8]}")
                    if weak:
                        quality_log["weak_axes"] = weak
                        print(f"  [품질] 약한 축: {weak}")

                if not must_fix and not want_lift:
                    if passes == 0:
                        print(f"  [수정 불필요] score {review.score} — 저장")
                    break

                kind = "고침+끌어올림" if must_fix else "끌어올림"
                print(f"  [수정·{passes + 1}] ({kind}) 위반 {len(violations)} · 약한축 {list(weak)}")
                revised = _revise_chapter(config, chapter, final, review, gtext, plan=plan_dump)
                re_review = _review_chapter(config, chapter, revised, gtext, step="재검수", plan=plan_dump)
                improved = re_review.score > review.score
                passes += 1

                re_bad = unverified_numbers(revised, gtext) if grounding else []
                quality_log["passes"].append({
                    "re_review": re_review.model_dump(),
                    "improved": improved,
                    "unverified_remaining": re_bad,
                    "weak_axes_remaining": _weak_axes(re_review),
                })

                final = revised
                review = re_review

                # 끌어올림만 남았는데 점수가 더 안 오르면 천장 → 수용.
                if not (_violations(re_review) or re_bad) and not improved:
                    print(f"  [천장] 품질 점수 정체(score {re_review.score}) — 현재 버전 수용")
                    break

            quality_log["revised"] = passes > 0

            final_bad = unverified_numbers(final, gtext) if grounding else []
            final_violations = _violations(review)
            if final_violations or final_bad:
                high = [i for i in final_violations if i.severity == "high"]
                quality_log["unresolved"] = {
                    "violations": [i.model_dump() for i in final_violations],
                    "unverified": final_bad,
                }
                print(f"  [잔여] 위반 {len(final_violations)}건(high {len(high)}) · "
                      f"미확인수치 {len(final_bad)}건 — 현재 버전으로 저장")

        except ConvergenceError as e:
            quality_log["flagged"] = True
            quality_log["error"] = str(e)
            print(f"  [미수렴] {e} — 플래그 후 진행")
            final = draft if draft is not None else f"<!-- 생성 실패: {e} -->"

        content = f"# {num}. {ctitle}\n\n{_strip_title_h1(final)}"
        filename = _chapter_filename(num, ctitle)
        (output_dir / filename).write_text(content, encoding="utf-8")
        (log_dir / f"chapter-{num:02d}-review.json").write_text(
            json.dumps(quality_log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  저장: {filename}")

        # 자동 푸시
        push_chapter(slug, num, ctitle, content, filename=filename)
        update_meta(slug, doc, completed=num)

        # 다음 챕터 연결: 설계의 thesis가 있으면 그것을, 없으면 챕터 설명을 요약으로.
        desc = (plan.thesis if plan and plan.thesis
                else chapter.get("description", ""))
        summaries.append(f"{num}. {ctitle}: {desc}")
        print()

    # 전권 PDF 생성 + 푸시 (실패해도 생성 자체는 성공 처리)
    try:
        pdf_path = build_pdf(REPO_ROOT / slug, slug, title,
                             subtitle=config.get("description", "")[:80],
                             model=MODEL)
        if pdf_path:
            push_pdf(slug, pdf_path)
    except Exception as e:
        print(f"  [PDF] 생성 실패(건너뜀): {e}")

    update_readme(slug, doc)
    print(f"[완료] {title}")


# 하위호환 — 기존 호출부 유지
def generate_book(toc: dict, output_dir: Path, slug: str) -> None:
    generate(toc, output_dir, slug)

import json
import ollama
from pathlib import Path

from prompts import (
    WRITE_SYSTEM,  write_user,
    REVIEW_SYSTEM, review_user,
    REVISE_SYSTEM, revise_user,
)
from github_push import push_chapter, update_meta, update_readme

MODEL = "gemma4:31b"

# 필수 키 — 모든 책 유형에 공통
BOOK_CONFIG_REQUIRED = (
    "title", "language", "description", "goal",
    "target_reader", "book_style", "writing_guidelines",
)

BOOK_CONFIG_KEYS = BOOK_CONFIG_REQUIRED


def _call(system: str, user: str, temperature: float) -> str:
    res = ollama.chat(
        model=MODEL,
        options={
            "temperature":    temperature,
            "num_ctx":        32768,
            "repeat_penalty": 1.2,
        },
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ]
    )
    return res["message"]["content"]


def _book_config(toc: dict) -> dict:
    """chapters를 제외한 책 설정만 추출"""
    return {k: toc[k] for k in BOOK_CONFIG_KEYS if k in toc}


def _parse_review(raw: str) -> dict:
    import re
    text = raw.strip()

    # 1) ```json ... ``` 블록 추출
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    # 2) 앞뒤 자연어 제거 — { } 사이 JSON만 추출 (2번 케이스 대응)
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        text = match.group()

    try:
        return json.loads(text.strip())
    except Exception:
        # JSON 자체가 잘리거나 진짜 파싱 불가 → 강제 재수정
        print("  [경고] 검수 JSON 파싱 실패 → 수정 단계 강제 실행")
        return {
            "has_errors": True,
            "score": 0,
            "issues": [{"type": "unclear", "severity": "high",
                        "problem": "검수 결과를 파싱할 수 없습니다.",
                        "original_text": "",
                        "fix_instruction": "원고 전체를 writing_guidelines에 맞게 재검토하세요."}],
            "summary": "검수 JSON 파싱 실패 — 전체 재수정",
        }


def write_chapter(book_config: dict, chapter: dict, previous_summaries: list = None) -> str:
    print(f"  [1/4] 초안 작성 중: {chapter['title']}")
    return _call(WRITE_SYSTEM, write_user(book_config, chapter, previous_summaries), temperature=0.8)


def review_chapter(book_config: dict, chapter: dict, draft: str, step: str = "2/4") -> dict:
    print(f"  [{step}] 검수 중...")
    raw = _call(REVIEW_SYSTEM, review_user(book_config, chapter, draft), temperature=0.2)
    data = _parse_review(raw)
    score = data.get("score", 0)
    issues = len(data.get("issues", []))
    print(f"         → score: {score}  issues: {issues}  has_errors: {data.get('has_errors')}")
    return data


def revise_chapter(book_config: dict, chapter: dict, draft: str, review_data: dict) -> str:
    print(f"  [3/4] 수정 중...")
    review_json = json.dumps(review_data, ensure_ascii=False, indent=2)
    return _call(REVISE_SYSTEM, revise_user(book_config, chapter, draft, review_json), temperature=0.5)


def generate_book(toc: dict, output_dir: Path, slug: str) -> None:
    title    = toc["title"]
    chapters = toc["chapters"]
    config   = _book_config(toc)

    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    print(f"\n책 생성 시작: {title}")
    print(f"챕터 수: {len(chapters)}\n")

    chapter_summaries = []  # 나중에 [-8:] 슬라이싱으로 교체 가능

    for chapter in chapters:
        num    = chapter["number"]
        ctitle = chapter["title"]
        print(f"--- 챕터 {num}: {ctitle} ---")

        draft       = write_chapter(config, chapter, chapter_summaries[:])
        review_data = review_chapter(config, chapter, draft, step="2/4")

        quality_log = {
            "chapter": {"number": num, "title": ctitle},
            "initial_review": review_data,
            "revised": False,
            "re_review": None,
        }

        if review_data.get("has_errors") or review_data.get("score", 100) < 90:
            revised   = revise_chapter(config, chapter, draft, review_data)
            re_review = review_chapter(config, chapter, revised, step="4/4")
            final     = revised
            quality_log["revised"]   = True
            quality_log["re_review"] = re_review
            if re_review.get("has_errors") or re_review.get("score", 100) < 90:
                remaining = [i for i in re_review.get("issues", []) if i.get("severity") == "high"]
                print(f"  [4/4] 재검수 후 잔여 이슈 {len(remaining)}건 — 현재 버전으로 저장")
        else:
            print(f"  [수정 불필요] score {review_data.get('score')} — 저장")
            final = draft

        content  = f"# 챕터 {num}: {ctitle}\n\n{final}"
        filename = f"chapter-{num:02d}.md"
        (output_dir / filename).write_text(content, encoding="utf-8")
        (log_dir / f"chapter-{num:02d}-review.json").write_text(
            json.dumps(quality_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  저장: {filename}")

        push_chapter(slug, num, ctitle, content)
        update_meta(slug, toc, completed=num)

        chapter_summaries.append(f"{num}장 {ctitle}: {chapter.get('description', '')}")
        print()

    update_readme(slug, toc)
    print(f"[완료] {title} — 모든 챕터 GitHub 푸시 완료")

import json
import ollama
from pathlib import Path

from prompts import (
    build_write_system,  write_user,
    build_review_system, review_user,
    build_revise_system, revise_user,
)
from github_push import push_chapter, update_meta, update_readme

MODEL = "gemma4:31b"

# 필수 키 — 모든 책 유형에 공통
BOOK_CONFIG_REQUIRED = (
    "title", "language", "description", "goal",
    "target_reader", "book_style", "writing_guidelines",
)

# 선택 키 — 시스템 프롬프트에서 직접 처리 (book_config에는 포함하되 user 메시지에선 제외)
BOOK_CONFIG_OPTIONAL = (
    "chapter_template",    # 시스템 프롬프트에 챕터 구성 구조로 주입
    "output_requirements", # 시스템 프롬프트에 출력 요구사항으로 주입
)

BOOK_CONFIG_KEYS = BOOK_CONFIG_REQUIRED + BOOK_CONFIG_OPTIONAL


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
    """JSON 파싱 실패 시 안전하게 폴백"""
    try:
        # 모델이 ```json ... ``` 로 감쌀 때도 처리
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception:
        return {"has_errors": False, "score": 99, "issues": [], "summary": "JSON 파싱 실패 — 원고 그대로 사용"}


def write_chapter(book_config: dict, chapter: dict) -> str:
    print(f"  [1/3] 초안 작성 중: {chapter['title']}")
    return _call(build_write_system(book_config), write_user(book_config, chapter), temperature=0.8)


def review_chapter(book_config: dict, chapter: dict, draft: str) -> dict:
    print(f"  [2/3] 검수 중...")
    raw = _call(build_review_system(book_config), review_user(book_config, chapter, draft), temperature=0.2)
    data = _parse_review(raw)
    score = data.get("score", 0)
    issues = len(data.get("issues", []))
    print(f"         → score: {score}  issues: {issues}  has_errors: {data.get('has_errors')}")
    return data


def revise_chapter(book_config: dict, chapter: dict, draft: str, review_data: dict) -> str:
    print(f"  [3/3] 수정 중...")
    review_json = json.dumps(review_data, ensure_ascii=False, indent=2)
    return _call(build_revise_system(book_config), revise_user(book_config, chapter, draft, review_json), temperature=0.5)


def generate_book(toc: dict, output_dir: Path, slug: str) -> None:
    title    = toc["title"]
    chapters = toc["chapters"]
    config   = _book_config(toc)

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n책 생성 시작: {title}")
    print(f"챕터 수: {len(chapters)}\n")

    for chapter in chapters:
        num    = chapter["number"]
        ctitle = chapter["title"]
        print(f"--- 챕터 {num}: {ctitle} ---")

        draft       = write_chapter(config, chapter)
        review_data = review_chapter(config, chapter, draft)

        if review_data.get("has_errors") or review_data.get("score", 100) < 90:
            final = revise_chapter(config, chapter, draft, review_data)
        else:
            print(f"  [3/3] 수정 불필요 (score {review_data.get('score')})")
            final = draft

        content  = f"# 챕터 {num}: {ctitle}\n\n{final}"
        filename = f"chapter-{num:02d}.md"
        (output_dir / filename).write_text(content, encoding="utf-8")
        print(f"  저장: {filename}")

        push_chapter(slug, num, ctitle, content)
        update_meta(slug, toc, completed=num)
        print()

    update_readme(slug, toc)
    print(f"[완료] {title} — 모든 챕터 GitHub 푸시 완료")

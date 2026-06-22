"""
챕터 완성마다 GitHub에 자동 커밋+푸시하는 모듈
"""
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent  # ai-books/

# 파일은 로컬에 항상 쓰되, git commit/push만 켜고 끈다 (--no-push 용).
PUSH_ENABLED = True


def set_push(enabled: bool) -> None:
    global PUSH_ENABLED
    PUSH_ENABLED = enabled
    if not enabled:
        print("  [GitHub] 자동 푸시 비활성화 — 로컬 생성만 수행")


def _git(args: list[str]) -> str:
    result = subprocess.run(
        ["git"] + args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 실패:\n{result.stderr}")
    return result.stdout.strip()


def push_chapter(slug: str, chapter_num: int, chapter_title: str, content: str,
                 filename: str | None = None) -> None:
    """챕터 파일을 저장하고 GitHub에 커밋+푸시"""
    book_dir = REPO_ROOT / slug
    book_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        filename = f"chapter-{chapter_num:02d}.md"
    (book_dir / filename).write_text(content, encoding="utf-8")

    if not PUSH_ENABLED:
        return
    _git(["add", str(book_dir / filename)])
    _git(["commit", "-m", f"feat({slug}): chapter-{chapter_num:02d} {chapter_title}"])
    _git(["push"])
    print(f"  [GitHub] 푸시 완료: {slug}/{filename}")


def update_meta(slug: str, toc: dict, completed: int) -> None:
    """meta.json 갱신 후 커밋+푸시"""
    book_dir = REPO_ROOT / slug
    book_dir.mkdir(parents=True, exist_ok=True)

    total = len(toc["chapters"])
    meta = {
        "title":              toc["title"],
        "language":           toc.get("language", "ko"),
        "model":              "gemma4:31b",
        "total_chapters":     total,
        "completed_chapters": completed,
        "status":             "done" if completed >= total else "in_progress",
    }
    meta_path = book_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if not PUSH_ENABLED:
        return
    _git(["add", str(meta_path)])
    _git(["commit", "-m", f"chore({slug}): meta.json 업데이트 ({completed}/{total})"])
    _git(["push"])


def push_pdf(slug: str, pdf_path: Path) -> None:
    """생성된 PDF를 커밋+푸시"""
    if not PUSH_ENABLED:
        return
    _git(["add", str(pdf_path)])
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT)
    if result.returncode != 0:
        _git(["commit", "-m", f"feat({slug}): {pdf_path.name} 생성"])
        _git(["push"])
        print(f"  [GitHub] PDF 푸시 완료: {slug}/{pdf_path.name}")


def update_readme(slug: str, toc: dict) -> None:
    """루트 README.md 책 목록 테이블 갱신 후 커밋+푸시"""
    readme_path = REPO_ROOT / "README.md"

    # 기존 책 목록 파싱
    books: dict[str, dict] = {}
    for meta_file in sorted(REPO_ROOT.glob("*/meta.json")):
        book_slug = meta_file.parent.name
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        books[book_slug] = meta

    # 테이블 생성
    rows = ["| 제목 | 언어 | 챕터 | 모델 | 상태 |",
            "|---|---|---|---|---|"]
    for s, m in books.items():
        status = "✅ 완료" if m.get("status") == "done" else "🔄 진행중"
        # 키 스타일 혼용 대응: total_chapters/completed_chapters(구) · total/completed(신)
        total = m.get("total_chapters", m.get("total", "?"))
        done = m.get("completed_chapters", m.get("completed", "?"))
        rows.append(
            f"| [{m.get('title', s)}](./{s}) "
            f"| {m.get('language', 'ko')} "
            f"| {done}/{total} "
            f"| {m.get('model', '')} "
            f"| {status} |"
        )

    content = "# AI Generated Books\n\n" + "\n".join(rows) + "\n"
    readme_path.write_text(content, encoding="utf-8")

    if not PUSH_ENABLED:
        return
    _git(["add", "README.md"])
    # 변경사항 없으면 커밋 스킵
    import subprocess
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT)
    if result.returncode != 0:
        _git(["commit", "-m", "docs: README 책 목록 업데이트"])
        _git(["push"])
    print("  [GitHub] README.md 업데이트 완료")

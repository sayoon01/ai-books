"""
챕터 완성마다 GitHub에 자동 커밋+푸시하는 모듈
"""
import json
import subprocess
from pathlib import Path

from core.config import REPO_ROOT, PUSH_ENABLED        # ai-books/ 루트, 푸시 기본값

# 파일은 로컬에 항상 쓰되, git commit/push만 켜고 끈다 (--no-push 용).
# PUSH_ENABLED 는 config 기본값으로 시작하되 set_push() 로 런타임 토글된다.


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
    book_dir = REPO_ROOT / "ADK_AGENT" / slug      # ADK 결과는 ADK_AGENT/ 하위로(시스템 분리)
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
    book_dir = REPO_ROOT / "ADK_AGENT" / slug      # ADK 결과는 ADK_AGENT/ 하위로(시스템 분리)
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


# 루트 README 두 섹션 구성 — (폴더명, 표제). 폴더 하위 <책>/meta.json 을 스캔.
_README_SYSTEMS = [
    ("5_AGENT", "🟦 5_AGENT — 기존 generator 파이프라인"),
    ("ADK_AGENT", "🟩 ADK_AGENT — 신규 Google ADK 기반 파이프라인"),
]


def _readme_section(sysdir: str, heading: str) -> list[str]:
    metas = sorted((REPO_ROOT / sysdir).glob("*/meta.json"))
    if not metas:
        return []
    out = [f"## {heading}", "",
           "| 제목 | 언어 | 챕터 | 모델 | 상태 |", "|---|---|---|---|---|"]
    for mf in metas:
        book = mf.parent.name
        m = json.loads(mf.read_text(encoding="utf-8"))
        status = "✅ 완료" if m.get("status") == "done" else "🔄 진행중"
        total = m.get("total_chapters", m.get("total", "?"))      # 구/신 메타 키 혼용 대응
        done = m.get("completed_chapters", m.get("completed", "?"))
        out.append(f"| [{m.get('title', book)}](./{sysdir}/{book}) "
                   f"| {m.get('language', 'ko')} | {done}/{total} "
                   f"| {m.get('model', '')} | {status} |")
    out.append("")
    return out


def update_readme(slug: str | None = None, toc: dict | None = None) -> None:
    """루트 README 자동 생성 — 5_AGENT / ADK_AGENT 두 섹션.
    각 시스템 폴더(ai-books/<sys>/) 하위의 <책>/meta.json 을 스캔해 표를 만든다.
    (책이 시스템 폴더 안에 있으므로 루트 1단계가 아니라 sys/* 를 본다.)"""
    readme_path = REPO_ROOT / "README.md"
    out = ["# AI Generated Books", "",
           "AI가 생성·검수한 기술 도서 모음. **생성 시스템별로** 나눠 정리했습니다.", ""]
    for sysdir, heading in _README_SYSTEMS:
        out += _readme_section(sysdir, heading)
    readme_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")

    if not PUSH_ENABLED:
        return
    _git(["add", "README.md"])
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT)
    if result.returncode != 0:
        _git(["commit", "-m", "docs: README 책 목록 업데이트(2섹션)"])
        _git(["push"])
    print("  [GitHub] README.md 업데이트 완료")

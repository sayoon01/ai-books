"""
일회성 마이그레이션: 기존 책들의 챕터 파일명을 새 형식으로 바꾸고 PDF(v1)를 생성한다.
- chapter-NN.md → chapter-NN-[제목 슬러그].md  (git mv로 이력 보존)
- 제목은 각 파일 첫 줄 H1에서 추출 ("# 1. 제목" / "# 챕터 1: 제목" 모두 지원)
- 마지막에 {slug}-v1.pdf 생성

실행: python generator/migrate_filenames.py
"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from book_writer import _slugify           # noqa: E402
from pdf_export import build_pdf           # noqa: E402

REPO_ROOT = Path(__file__).parent.parent
OLD_RE = re.compile(r"^chapter-(\d+)\.md$")        # 옛 형식만 대상
# H1에서 번호 접두 제거: "1. ", "챕터 1: ", "chapter 1 - " 등
NUM_PREFIX = re.compile(r"^\s*(?:챕터|chapter)?\s*\d+\s*[.:\-–—]\s*", re.IGNORECASE)


def _git(args: list[str]) -> None:
    r = subprocess.run(["git"] + args, cwd=REPO_ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 실패:\n{r.stderr}")


def _title_from_md(path: Path) -> str:
    first = path.read_text(encoding="utf-8").lstrip().split("\n", 1)[0]
    h1 = first.lstrip("#").strip()
    return NUM_PREFIX.sub("", h1).strip()


def migrate_book(book_dir: Path) -> bool:
    slug = book_dir.name
    renamed = 0
    for old in sorted(book_dir.glob("chapter-*.md")):
        m = OLD_RE.match(old.name)
        if not m:
            continue
        num = int(m.group(1))
        title = _title_from_md(old)
        title_slug = _slugify(title)
        if not title_slug:
            continue
        new_name = f"chapter-{num:02d}-{title_slug}.md"
        if new_name == old.name:
            continue
        _git(["mv", str(old), str(book_dir / new_name)])
        print(f"  rename: {old.name} → {new_name}")
        renamed += 1
    return renamed > 0


def main():
    books = [p.parent for p in sorted(REPO_ROOT.glob("*/meta.json"))]
    for book_dir in books:
        chapters = list(book_dir.glob("chapter-*.md"))
        if not chapters:
            continue
        slug = book_dir.name
        title = (book_dir / "meta.json")
        import json
        title = json.loads(title.read_text(encoding="utf-8")).get("title", slug)
        print(f"\n=== {slug} ===")

        changed = migrate_book(book_dir)

        pdf = build_pdf(book_dir, slug, title)   # 새 파일명 기준으로 v1 생성

        # 커밋
        _git(["add", "-A", str(book_dir)])
        r = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT)
        if r.returncode != 0:
            msg = f"chore({slug}): 챕터 파일명 슬러그화 + PDF 생성"
            _git(["commit", "-m", msg])
            print(f"  committed: {msg}")
        else:
            print("  변경 없음")

    print("\n[완료] 마이그레이션. 확인 후 git push 하세요.")


if __name__ == "__main__":
    main()

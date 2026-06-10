"""
실행 방법:
  python generator/main.py --toc toc/my-book.json
"""
import argparse
import json
import re
from pathlib import Path
from book_writer import generate_book


def title_to_slug(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug


def main():
    parser = argparse.ArgumentParser(description="AI 책 생성기")
    parser.add_argument("--toc", required=True, help="목차 JSON 파일 경로")
    args = parser.parse_args()

    toc_path = Path(args.toc)
    if not toc_path.exists():
        print(f"[오류] 목차 파일을 찾을 수 없습니다: {toc_path}")
        return

    toc  = json.loads(toc_path.read_text(encoding="utf-8"))
    slug = title_to_slug(toc["title"])
    output_dir = Path(__file__).parent.parent / "output" / slug

    generate_book(toc, output_dir, slug)


if __name__ == "__main__":
    main()

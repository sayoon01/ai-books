"""
실행 방법:
  python generator/main.py --toc toc/python-ml.json          # 책 (grounding 없음)
  python generator/main.py --toc toc/mold-dx-report.json --planner   # 기술서 (grounding 있음)

문서 유형은 toc JSON의 doc_type/필드가 정한다. grounding 필드가 있으면 자동 해소된다.
"""
import argparse
import json
import re
from pathlib import Path

from book_writer import generate


def title_to_slug(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug


def main():
    parser = argparse.ArgumentParser(description="AI 문서 생성기 (장르 무관)")
    parser.add_argument("--toc", required=True, help="문서 사양 JSON 경로 (toc/*.json)")
    parser.add_argument("--planner", action="store_true", help="Planner 단계 활성화")
    args = parser.parse_args()

    doc_path = Path(args.toc)
    if not doc_path.exists():
        print(f"[오류] 파일을 찾을 수 없습니다: {doc_path}")
        return

    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    slug = title_to_slug(doc["title"])
    output_dir = Path(__file__).parent.parent / "output" / slug

    generate(doc, output_dir, slug, use_planner=args.planner)


if __name__ == "__main__":
    main()

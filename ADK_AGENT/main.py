"""
ADK 기반 책/문서 생성기 (generator/ 와 독립).

실행:
  .venv/bin/python main.py --toc ../toc/some.json
  .venv/bin/python main.py --toc ... --no-push        # 로컬 생성만(파일 output/ 에만)
  .venv/bin/python main.py --toc ... --redesign       # design.json 강제 재생성

문서 정체성·독자·문체는 toc JSON의 description/target_reader/writing_guidelines가 정한다.
chapters가 없으면 source(없으면 description)로 Design이 목차를 생성한다.
"""
import argparse
import asyncio
import json
import re
from pathlib import Path

from pipeline import generate


def title_to_slug(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug


def main():
    parser = argparse.ArgumentParser(description="ADK 기반 AI 책/문서 생성기")
    parser.add_argument("--toc", required=True, help="문서 사양 JSON 경로")
    parser.add_argument("--no-push", action="store_true", help="자동 푸시·PDF 끄고 로컬 생성만")
    parser.add_argument("--redesign", action="store_true", help="design.json 무시하고 재생성")
    parser.add_argument("--out", default=None, help="출력 폴더(기본 ../output/<slug>)")
    args = parser.parse_args()

    doc_path = Path(args.toc)
    if not doc_path.exists():
        print(f"[오류] 파일을 찾을 수 없습니다: {doc_path}")
        return

    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    slug = title_to_slug(doc["title"])
    output_dir = Path(args.out) if args.out else Path(__file__).parent.parent / "output" / slug

    asyncio.run(generate(doc, output_dir, slug,
                         force_redesign=args.redesign, push=not args.no_push,
                         do_pdf=not args.no_push))


if __name__ == "__main__":
    main()

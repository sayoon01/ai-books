"""
ADK 기반 책/문서 생성기 (generator/ 와 독립).

실행:
  .venv/bin/python main.py --toc toc/mold-dx-auto.json
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
    parser.add_argument("--no-push", action="store_true", help="GitHub 자동 푸시 끄고 로컬 생성만")
    parser.add_argument("--no-pdf", action="store_true", help="PDF 생성 끄기")
    parser.add_argument("--redesign", action="store_true", help="design.json 무시하고 재생성")
    parser.add_argument("--design-only", action="store_true",
                        help="design.json 만 생성(또는 로드)하고 챕터 생성 전에 종료. "
                             "digest 의 grounding 패치를 챕터 생성 전에 끼워 넣을 때 쓴다.")
    parser.add_argument("--out", default=None, help="출력 폴더(기본 ./output/<slug>)")
    parser.add_argument("--no-trace", action="store_true",
                        help="트레이싱 끄기. 기본은 자동 — env(PHOENIX/LANGFUSE) 설정된 백엔드로 자동 전송")
    parser.add_argument("--engine", choices=["graph", "agent"], default="graph",
                        help="챕터 엔진. graph=신 그래프(기본), agent=표준 멀티에이전트(Sequential/Loop)")
    args = parser.parse_args()

    doc_path = Path(args.toc)
    if not doc_path.exists():
        print(f"[오류] 파일을 찾을 수 없습니다: {doc_path}")
        return

    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    slug = title_to_slug(doc["title"])
    output_dir = Path(args.out) if args.out else Path(__file__).parent / "output" / slug

    asyncio.run(generate(doc, output_dir, slug,
                         force_redesign=args.redesign, push=not args.no_push,
                         do_pdf=not args.no_pdf, trace=not args.no_trace, engine=args.engine,
                         design_only=args.design_only))


if __name__ == "__main__":
    main()

"""
GitHub Pages 용 책 목록(docs/books.json) 생성기.
5_AGENT/ 와 ADK_AGENT/ 하위의 <책>/meta.json·chapter-*.md·*.pdf 를 스캔한다.
실행:  python3 docs/make_index.py   (새 책 생기면 다시 실행 후 커밋)
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # ai-books/
SYSTEMS = [
    ("5_AGENT", "🟦 5_AGENT — 기존 generator 파이프라인"),
    ("ADK_AGENT", "🟩 ADK_AGENT — 신규 Google ADK 파이프라인"),
]
_CH = re.compile(r"^(chapter|unit)-\d+.*\.md$")


def _book(sysdir: str, d: Path) -> dict:
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    chapters = sorted(f.name for f in d.iterdir() if _CH.match(f.name))
    pdfs = sorted(f.name for f in d.iterdir() if f.suffix == ".pdf")
    return {
        "slug": d.name,
        "path": f"{sysdir}/{d.name}",
        "title": meta.get("title", d.name),
        "language": meta.get("language", "ko"),
        "model": meta.get("model", ""),
        "total": meta.get("total_chapters", meta.get("total", len(chapters))),
        "completed": meta.get("completed_chapters", meta.get("completed", len(chapters))),
        "status": meta.get("status", "done"),
        "chapters": chapters,
        "pdfs": pdfs,
    }


def main() -> None:
    systems = []
    for sysdir, label in SYSTEMS:
        base = ROOT / sysdir
        books = [_book(sysdir, d) for d in sorted(base.iterdir())
                 if d.is_dir() and (d / "meta.json").exists()]
        if books:
            systems.append({"id": sysdir, "label": label, "books": books})
    out = ROOT / "docs" / "books.json"
    out.write_text(json.dumps({"systems": systems}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    n = sum(len(s["books"]) for s in systems)
    print(f"docs/books.json 생성 — 시스템 {len(systems)}개, 책 {n}권")


if __name__ == "__main__":
    main()

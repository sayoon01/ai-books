"""
완성된 챕터 마크다운을 한 권으로 합쳐 PDF로 변환한다.
- 출력명: {slug}-v{N}.pdf  (기존 PDF를 보고 버전 자동 증가)
- markdown → HTML → weasyprint, 한글 폰트(Noto Serif CJK KR) 지정.
"""
import re
from pathlib import Path

import markdown
from weasyprint import HTML

# 한글 본문용 CSS. 시스템에 깔린 Noto Serif CJK KR을 사용한다.
_CSS = """
@page { size: A4; margin: 22mm 20mm; }
body { font-family: "Noto Serif CJK KR", serif; font-size: 11pt; line-height: 1.7;
       color: #1a1a1a; }
h1 { font-size: 20pt; margin: 1.4em 0 0.6em; page-break-before: always; }
h1:first-of-type { page-break-before: avoid; }
h2 { font-size: 15pt; margin: 1.2em 0 0.5em; }
h3 { font-size: 12.5pt; margin: 1em 0 0.4em; }
p { margin: 0.5em 0; text-align: justify; }
code, pre { font-family: "Noto Sans Mono CJK KR", monospace; font-size: 9.5pt; }
pre { background: #f4f4f4; padding: 0.8em; border-radius: 4px; white-space: pre-wrap; }
table { border-collapse: collapse; width: 100%; margin: 0.8em 0; }
th, td { border: 1px solid #ccc; padding: 5px 8px; font-size: 10pt; }
.cover { text-align: center; page-break-after: always; }
.cover h1 { font-size: 30pt; page-break-before: avoid; margin-top: 35vh; }
"""


def _next_version(book_dir: Path, slug: str) -> int:
    """{slug}-v*.pdf 중 최대 버전 +1 (없으면 1)."""
    nums = []
    for p in book_dir.glob(f"{slug}-v*.pdf"):
        m = re.match(rf"{re.escape(slug)}-v(\d+)\.pdf$", p.name)
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def _chapter_files(book_dir: Path) -> list[Path]:
    """chapter-NN[-슬러그].md 를 번호 순으로."""
    files = list(book_dir.glob("chapter-*.md"))
    def key(p: Path) -> int:
        m = re.match(r"chapter-(\d+)", p.name)
        return int(m.group(1)) if m else 0
    return sorted(files, key=key)


def build_pdf(book_dir: Path, slug: str, title: str) -> Path | None:
    """책 폴더의 챕터들을 합쳐 다음 버전 PDF를 생성. 챕터가 없으면 None."""
    chapters = _chapter_files(book_dir)
    if not chapters:
        print("  [PDF] 챕터 md가 없어 건너뜀")
        return None

    md_parts = "\n\n".join(c.read_text(encoding="utf-8") for c in chapters)
    body_html = markdown.markdown(md_parts, extensions=["tables", "fenced_code"])
    full_html = (
        f'<div class="cover"><h1>{title}</h1></div>\n{body_html}'
    )

    version = _next_version(book_dir, slug)
    out_path = book_dir / f"{slug}-v{version}.pdf"
    HTML(string=full_html).write_pdf(str(out_path), stylesheets=[__css()])
    print(f"  [PDF] 생성: {out_path.name} (챕터 {len(chapters)}개)")
    return out_path


def __css():
    from weasyprint import CSS
    return CSS(string=_CSS)

"""
완성된 챕터 마크다운을 한 권으로 합쳐 '출판물 수준' PDF로 변환한다.
구성: 표지 → 판권지 → 목차(페이지번호) → 본문(러닝헤더·페이지번호·코드하이라이팅)
- 출력명: {slug}-v{N}.pdf  (기존 PDF를 보고 버전 자동 증가)
- markdown → HTML → weasyprint.
- language(ko/en 등)에 맞춰 라벨·폰트·<html lang>을 자동 전환. 모르는 언어는 en 폴백.
의존성: weasyprint, markdown, pygments
"""
import datetime as _dt
import re
import time
from pathlib import Path

import markdown
from markdown.extensions.toc import TocExtension
from pygments.formatters import HtmlFormatter
from weasyprint import HTML, CSS

# ── 언어별 글꼴 (시스템 설치 폰트). CJK는 Noto Serif CJK, 그 외는 라틴 serif. ──
_CJK_LANGS = {"ko", "ja", "zh", "zh-cn", "zh-tw", "zh-hans", "zh-hant"}
_FONTS_CJK = ('"Noto Serif CJK KR", serif',
              '"Noto Sans CJK KR", sans-serif',
              '"D2Coding", "Noto Sans Mono CJK KR", monospace')
_FONTS_LATIN = ('"Noto Serif", "DejaVu Serif", serif',
                '"Noto Sans", "DejaVu Sans", sans-serif',
                '"DejaVu Sans Mono", monospace')

# ── 언어별 라벨 (없는 언어는 en 폴백) ──
_LABELS = {
    "ko": {"eyebrow": "AI 생성 도서", "toc": "목차", "published": "발행일",
           "author": "지은이", "model": "생성 모델", "version": "버전",
           "outline": "목차 구성", "outline_ai": "AI 생성 목차", "outline_given": "지정 목차",
           "note": "본 문서는 자동 생성 파이프라인으로 작성·검수되었습니다.",
           "rights": "All rights reserved."},
    "en": {"eyebrow": "AI GENERATED BOOK", "toc": "Table of Contents", "published": "Published",
           "author": "Author", "model": "Model", "version": "Version",
           "outline": "Outline", "outline_ai": "AI-generated", "outline_given": "Provided",
           "note": "This document was written and reviewed by an automated generation pipeline.",
           "rights": "All rights reserved."},
}


def _lang_assets(language: str):
    """언어 코드 → (라벨 dict, (serif, sans, mono), is_cjk)."""
    lang = (language or "ko").lower()
    base = lang.split("-")[0]
    labels = _LABELS.get(lang) or _LABELS.get(base) or _LABELS["en"]
    is_cjk = lang in _CJK_LANGS or base in {"ko", "ja", "zh"}
    return labels, (_FONTS_CJK if is_cjk else _FONTS_LATIN), is_cjk


def _make_css(serif: str, sans: str, mono: str, is_cjk: bool) -> str:
    """폰트/언어에 맞춘 스타일시트. {BOOK_TITLE}은 caller가 치환."""
    # CJK는 단어 중간 줄바꿈 방지(keep-all), 라틴은 기본 줄바꿈.
    wrap = "word-break: keep-all; line-break: strict;" if is_cjk else ""
    return f"""
/* ===== 페이지 기본 (본문) : 러닝헤더 + 가운데 페이지번호 ===== */
@page {{
    size: A4;
    margin: 25mm 22mm 22mm 22mm;
    @top-center   {{ content: string(book-title); font: 8pt {sans}; color:#888; }}
    @top-right    {{ content: string(chapter);    font: 8pt {sans}; color:#888; }}
    @bottom-center{{ content: counter(page);       font: 9pt {sans}; color:#555; }}
}}
@page :first {{ @top-center{{content:none}} @top-right{{content:none}} @bottom-center{{content:none}} }}

/* 표지 / 판권지 : 머리말·꼬리말 없음 */
@page cover    {{ margin:0; @top-center{{content:none}} @top-right{{content:none}} @bottom-center{{content:none}} }}
@page colophon {{ @top-center{{content:none}} @top-right{{content:none}} @bottom-center{{content:none}} }}
@page toc      {{ @top-right{{content:none}} }}

html {{ string-set: book-title "{{BOOK_TITLE}}"; }}
body {{ font-family:{serif}; font-size:10.5pt; line-height:1.75; color:#1a1a1a;
        {wrap} text-align: justify; hanging-punctuation: allow-end; }}

/* ===== 표지 ===== */
.cover {{ page: cover; break-after: page; height:100vh; display:flex;
          flex-direction:column; justify-content:center; align-items:center;
          text-align:center; padding:0 25mm; background:#0f2540; color:#fff; }}
.cover .eyebrow {{ font:11pt {sans}; letter-spacing:.35em; opacity:.7; margin-bottom:1.5em; }}
.cover h1 {{ font:bold 32pt {sans}; line-height:1.3; margin:0; border:none; color:#fff; }}
.cover .subtitle {{ font:14pt {serif}; opacity:.85; margin-top:1em; }}
.cover .rule {{ width:60px; height:3px; background:#c9a14a; margin:2em 0; }}
.cover .meta {{ font:10pt {sans}; opacity:.75; margin-top:auto; padding-bottom:25mm; line-height:1.8; }}

/* ===== 판권지 ===== */
.colophon {{ page: colophon; break-after: page; font:9pt {sans}; color:#444;
             padding-top:45vh; line-height:1.9; }}
.colophon strong {{ color:#1a1a1a; }}
.colophon p {{ break-inside: avoid; }}

/* ===== 목차 ===== */
nav.toc {{ page: toc; break-after: page; }}
nav.toc > h2 {{ font:bold 18pt {sans}; color:#0f2540; border-bottom:2px solid #0f2540;
                padding-bottom:.3em; margin-bottom:1em; }}
nav.toc ul {{ list-style:none; padding-left:0; }}
nav.toc li {{ margin:.4em 0; display:flex; }}
nav.toc li li {{ padding-left:1.4em; font-size:9.5pt; color:#555; }}
nav.toc a {{ text-decoration:none; color:inherit; flex:1;
             display:flex; justify-content:space-between; }}
nav.toc a::after {{ content: target-counter(attr(href), page); color:#888; }}

/* ===== 본문 ===== */
h1 {{ string-set: chapter content(); break-before: page; break-after: avoid;
      font:bold 22pt {sans}; color:#0f2540; padding-top:1em;
      border-bottom:3px solid #c9a14a; padding-bottom:.4em; margin-bottom:1em; }}
h2 {{ font:bold 14pt {sans}; color:#0f2540; margin:1.6em 0 .5em; break-after: avoid; }}
h3 {{ font:bold 12pt {sans}; margin:1.2em 0 .4em; break-after: avoid; }}
p  {{ margin:.55em 0; orphans:2; widows:2; }}
strong {{ color:#0f2540; }}
a {{ color:#1a5276; }}

/* 표 */
table {{ border-collapse:collapse; width:100%; margin:1em 0; font-size:9.5pt;
         break-inside: avoid; }}
thead {{ background:#0f2540; color:#fff; }}
th,td {{ border:1px solid #d0d0d0; padding:6px 9px; text-align:left; }}
tbody tr:nth-child(even) {{ background:#f6f8fa; }}

/* 인용 / 노트 */
blockquote {{ border-left:4px solid #c9a14a; background:#faf7ef; margin:1em 0;
              padding:.6em 1em; color:#444; }}

/* 코드 */
code {{ font-family:{mono}; font-size:9pt; background:#f0f2f4;
        padding:1px 4px; border-radius:3px; }}
pre {{ font-family:{mono}; font-size:8.5pt; line-height:1.5; background:#f6f8fa;
       border:1px solid #e1e4e8; border-radius:6px; padding:.9em 1em;
       white-space:pre-wrap; break-inside: avoid; }}
pre code {{ background:none; padding:0; }}

img {{ max-width:100%; }}
figure {{ text-align:center; margin:1.2em 0; }}
figcaption {{ font:9pt {sans}; color:#777; margin-top:.4em; }}
"""


def _next_version(book_dir: Path, slug: str) -> int:
    nums = [int(m.group(1)) for p in book_dir.glob(f"{slug}-v*.pdf")
            if (m := re.match(rf"{re.escape(slug)}-v(\d+)\.pdf$", p.name))]
    return (max(nums) + 1) if nums else 1


def _chapter_files(book_dir: Path) -> list[Path]:
    files = list(book_dir.glob("chapter-*.md"))
    return sorted(files, key=lambda p: int(re.match(r"chapter-(\d+)", p.name).group(1))
                  if re.match(r"chapter-(\d+)", p.name) else 0)


def build_pdf(book_dir: Path, slug: str, title: str, *,
              language: str = "ko", subtitle: str = "", author: str = "AI Book Generator",
              model: str = "", date_str: str = "", version: int | None = None,
              auto_outline: bool | None = None) -> Path | None:
    """책 폴더의 챕터들을 합쳐 PDF 생성. language로 라벨·폰트 전환, version 미지정 시 자동 산정.
    auto_outline: True=AI 생성 목차, False=지정 목차, None=표기 안 함."""
    chapters = _chapter_files(book_dir)
    if not chapters:
        print("  [PDF] 챕터 md가 없어 건너뜀")
        return None

    t0 = time.perf_counter()
    if version is None:
        version = _next_version(book_dir, slug)
    date_str = date_str or _dt.date.today().isoformat()
    L, (serif, sans, mono), is_cjk = _lang_assets(language)
    lang_attr = (language or "ko").lower()
    raw_md = "\n\n".join(c.read_text(encoding="utf-8") for c in chapters)

    # 한 번에 변환해야 헤딩 id·TOC가 일관됨
    md = markdown.Markdown(extensions=[
        "extra", "sane_lists", "codehilite",
        TocExtension(toc_depth="1-2", permalink=False),
    ], extension_configs={"codehilite": {"guess_lang": False}})
    body_html = md.convert(raw_md)
    toc_html = md.toc                      # <div class="toc"><ul>…</ul></div>
    pyg_css = HtmlFormatter().get_style_defs(".codehilite")

    cover = f"""
    <section class="cover">
      <div class="eyebrow">{L['eyebrow']}</div>
      <h1>{title}</h1>
      {f'<div class="subtitle">{subtitle}</div>' if subtitle else ''}
      <div class="rule"></div>
      <div class="meta">{author} · {date_str}<br>
        {f'{model} · ' if model else ''}{L['version']} {version}</div>
    </section>"""

    colophon = f"""
    <section class="colophon">
      <p><strong>{title}</strong></p>
      {f'<p>{subtitle}</p>' if subtitle else ''}
      <p>{L['published']} {date_str}<br>
         {L['author']} {author}<br>
         {f"{L['model']} {model}<br>" if model else ''}
         {f"{L['outline']} {L['outline_ai'] if auto_outline else L['outline_given']}<br>" if auto_outline is not None else ''}
         {L['version']} v{version}<br>
         {L['note']}</p>
      <p>© {date_str[:4]} {author}. {L['rights']}</p>
    </section>"""

    toc = f'<nav class="toc"><h2>{L["toc"]}</h2>{toc_html}</nav>'

    full_html = (
        f'<!DOCTYPE html><html lang="{lang_attr}"><head><meta charset="utf-8">'
        f'<title>{title}</title>'
        f'<meta name="author" content="{author}">'
        f'<meta name="description" content="{subtitle or title}">'
        f'<meta name="generator" content="{model or "ai-books"}">'
        f'</head><body>{cover}{colophon}{toc}<main>{body_html}</main></body></html>'
    )

    css_text = _make_css(serif, sans, mono, is_cjk).replace("{BOOK_TITLE}", title)
    css = CSS(string=css_text + "\n" + pyg_css)
    out_path = book_dir / f"{slug}-v{version}.pdf"
    t_render = time.perf_counter()
    HTML(string=full_html).write_pdf(str(out_path), stylesheets=[css])
    render_s = time.perf_counter() - t_render
    total_s = time.perf_counter() - t0
    print(f"  [PDF] 생성: {out_path.name} (챕터 {len(chapters)}개, lang={lang_attr}) "
          f"— 렌더 {render_s:.1f}s / 전체 {total_s:.1f}s")
    # 빌드 시간 기록 (gitignore된 output/<slug>/logs 아래, 있으면 누적)
    log_dir = book_dir.parent / "output" / slug / "logs"
    if log_dir.exists():
        with (log_dir / "pdf_build.log").open("a", encoding="utf-8") as f:
            f.write(f"{_dt.datetime.now().isoformat(timespec='seconds')}\t"
                    f"{out_path.name}\tchapters={len(chapters)}\t"
                    f"render={render_s:.1f}s\ttotal={total_s:.1f}s\n")
    return out_path

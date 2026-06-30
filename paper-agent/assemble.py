"""
LaTeX 조립 — 섹션 본문 + 표/그림 float 을 main.tex 한 편으로 묶는다.

- abstract 섹션은 \\begin{abstract} 환경으로, 나머지는 \\section 으로.
- 각 섹션 본문 뒤에 그 섹션 소속(artifact.section_id) 표/그림 float 을 배치
  → 본문의 \\ref{id} 가 항상 같은 페이지 근처에서 해소된다.
- kotex 사용(한국어). 빌드: pdflatex → (bibtex) → pdflatex×2.
"""
from pathlib import Path

PREAMBLE = r"""\documentclass[10pt,twocolumn]{article}
\usepackage{kotex}
\usepackage[margin=2cm]{geometry}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{amsmath,amssymb}
\usepackage{hyperref}
\usepackage{cite}
\graphicspath{{figures/}}
"""


def _figure_float(m: dict) -> str:
    fname = Path(m["path"]).name
    return ("\n".join([
        r"\begin{figure}[t]", r"\centering",
        rf"\includegraphics[width=\linewidth]{{{fname}}}",
        rf"\caption{{{m.get('caption','')}}}", rf"\label{{{m['id']}}}",
        r"\end{figure}", ""]))


def _table_input(m: dict) -> str:
    rel = Path(m["path"]).relative_to(Path(m["path"]).parent.parent)  # tables/<file>.tex
    return rf"\input{{{rel.as_posix()}}}" + "\n"


def assemble(result: dict) -> Path:
    plan, sections, order = result["plan"], result["sections"], result["order"]
    out: Path = result["out"]
    manifest = {m["id"]: m for m in result.get("manifest", [])}

    # 섹션별 소속 자료 묶기
    arts_by_section: dict[str, list[str]] = {}
    for a in plan.get("artifacts", []):
        arts_by_section.setdefault(a.get("section_id", ""), []).append(a["id"])

    doc = [PREAMBLE,
           rf"\title{{{plan.get('title','')}}}",
           r"\author{paper-agent (자동 생성 초안)}",
           r"\date{}",
           r"\begin{document}",
           r"\maketitle", ""]

    for sid in order:
        body = sections[sid].strip()
        title = next((s["title"] for s in plan["sections"] if s["id"] == sid), sid)
        if sid == "abstract":
            doc += [r"\begin{abstract}", body, r"\end{abstract}", ""]
        else:
            doc += [rf"\section{{{title}}}", body, ""]
        # 이 섹션 소속 표/그림 float
        for aid in arts_by_section.get(sid, []):
            m = manifest.get(aid)
            if not m:
                continue
            if m["kind"] == "figure":
                doc.append(_figure_float(m))
            elif m["kind"] == "table":
                doc.append(_table_input(m))

    doc += [r"\end{document}", ""]
    path = out / "main.tex"
    path.write_text("\n".join(doc), encoding="utf-8")
    return path

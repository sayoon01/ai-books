"""
텍스트 유틸 (순수 함수). generator/book_writer.py 의 텍스트 처리부를 복사·독립화.
- 파일명 슬러그, 본문 제목 H1 제거
- LaTeX 기호/선형식 → 유니코드 평문 정규화 (구조적 수식은 보존)
- 자유 텍스트 응답에서 JSON 추출
"""
import json
import re


def slugify(text: str) -> str:
    """제목 → 파일명 슬러그. 한국어(\\w)는 보존하고 공백/언더스코어는 '-'로."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)          # 연속 하이픈 합치기
    return s.strip("-")


def chapter_filename(num: int, title: str) -> str:
    slug = slugify(title)
    return f"chapter-{num:02d}-{slug}.md" if slug else f"chapter-{num:02d}.md"


def strip_title_h1(text: str) -> str:
    """본문 맨 앞에 제목 H1(`# ...`)이 중복되면 제거. 소제목(`## ...`)은 보존."""
    s = text.lstrip()
    if s.startswith("# "):
        parts = s.split("\n", 1)
        return parts[1].lstrip("\n") if len(parts) > 1 else ""
    return text


# LaTeX 기호 → 유니코드 (선형식은 평문화, 구조적 수식만 보존)
_MATH_SYM = {
    r"\rightarrow": "→", r"\Rightarrow": "⇒", r"\to": "→", r"\leftarrow": "←",
    r"\times": "×", r"\div": "÷", r"\pm": "±", r"\cdot": "·", r"\ast": "*",
    r"\leq": "≤", r"\le": "≤", r"\geq": "≥", r"\ge": "≥",
    r"\neq": "≠", r"\approx": "≈", r"\sim": "~", r"\gg": "≫", r"\ll": "≪",
    r"\Delta": "Δ", r"\delta": "δ", r"\sigma": "σ", r"\mu": "μ", r"\Sigma": "Σ",
    r"\alpha": "α", r"\beta": "β", r"\theta": "θ", r"\lambda": "λ",
    r"\ldots": "…", r"\dots": "…", r"\cdots": "…",
    r"\uparrow": "↑", r"\downarrow": "↓", r"\supset": "⊃", r"\subset": "⊂",
}
# 이런 구조 명령이 든 구간은 선형 평문화가 불가 → 원본 보존(수식 렌더러용)
_MATH_STRUCT = re.compile(r"\\(frac|sqrt|int|prod|sum|begin|matrix|binom|partial|lim)\b")


def _conv_math(inner: str) -> str | None:
    """$...$ 한 덩어리를 평문/유니코드로. 구조적 수식이면 None(=보존)."""
    if _MATH_STRUCT.search(inner):
        return None
    s = inner
    s = s.replace(r"^\circ\text{C}", "°C").replace(r"\^\circ", "°").replace(r"^\circ", "°")
    s = re.sub(r"\\text\{([^{}]*)\}", r"\1", s)        # \text{Max} → Max
    s = s.replace(r"\circ", "°")
    for k, v in _MATH_SYM.items():
        s = s.replace(k, v)
    s = re.sub(r"_\{([^{}]*)\}", r"_\1", s)            # T_{End} → T_End
    s = re.sub(r"\^\{([^{}]*)\}", r"^\1", s)           # x^{2} → x^2
    s = s.replace(r"\_", "_").replace(r"\,", ",").replace(r"\ ", " ").replace(r"\\", " ")
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


def normalize_math(text: str) -> str:
    """LLM이 섞어 쓴 LaTeX 기호/선형식을 평문·유니코드로 정규화.
    코드펜스(```)는 건드리지 않고, 구조적 수식($$\\frac…$$ 등)만 원본 보존."""
    def _repl(m):
        conv = _conv_math(m.group(1))
        return m.group(0) if conv is None else conv

    parts = re.split(r"(```.*?```)", text, flags=re.DOTALL)
    for i in range(0, len(parts), 2):                  # 코드펜스 바깥(짝수)만
        parts[i] = re.sub(r"\$\$(.+?)\$\$", _repl, parts[i], flags=re.DOTALL)   # 블록
        parts[i] = re.sub(r"(?<!\$)\$([^$\n]+)\$(?!\$)", _repl, parts[i])       # 인라인
    return "".join(parts)


def parse_json(raw: str) -> dict:
    """자유 텍스트 응답에서 JSON 객체만 추출해 파싱."""
    text = raw.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group()
    return json.loads(text.strip())

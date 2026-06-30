"""
텍스트 유틸 (순수 함수).
- 파일명 슬러그, 본문 제목 H1 제거
- 자유 텍스트 응답에서 JSON 추출
(LaTeX 출력이라 normalize_math 는 책 엔진과 반대 — 평문화하지 않고 그대로 둔다.)
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


def strip_title_h1(text: str) -> str:
    """본문 맨 앞에 제목 H1(`# ...`)이 중복되면 제거."""
    s = text.lstrip()
    if s.startswith("# "):
        parts = s.split("\n", 1)
        return parts[1].lstrip("\n") if len(parts) > 1 else ""
    return text


def strip_code_fence(text: str) -> str:
    """LLM이 본문을 ```latex ... ``` 펜스로 감싸면 벗긴다(LaTeX 본문 보호)."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


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

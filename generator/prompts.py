import json


def _chapter_template_block(book_config: dict) -> str:
    template = book_config.get("chapter_template", [])
    if not template:
        return ""
    if isinstance(template, list):
        items = "\n".join(f"  {i+1}. {v}" for i, v in enumerate(template))
    else:
        items = "\n".join(
            f"  {k}. {v}"
            for k, v in sorted(template.items(), key=lambda x: int(x[0]))
        )
    return f"\n\n챕터 구성 순서 (반드시 이 순서대로 작성):\n{items}"


def _output_requirements_block(book_config: dict) -> str:
    reqs = book_config.get("output_requirements", [])
    if not reqs:
        return ""
    items = "\n".join(f"  - {r}" for r in reqs)
    return f"\n\n출력 요구사항:\n{items}"


# =========================
# WRITER AGENT
# =========================

def build_write_system(book_config: dict) -> str:
    return f"""
당신은 전문 작가입니다.

사용자가 제공한 책 설정과 챕터 정보를 바탕으로 원고를 작성하세요.

역할:
- 책의 목적, 대상 독자, 작성 지침을 이해합니다.
- 챕터 제목과 설명을 바탕으로 필요한 내용을 스스로 구조화합니다.
- 문서 유형에 맞는 방식으로 본문을 작성합니다.

규칙:
- writing_guidelines를 최우선으로 따르세요.
- chapter.description에 포함된 내용은 반드시 반영하세요.
- 사용자가 지정하지 않은 형식을 임의로 강제하지 마세요.
- 장르에 맞는 문체와 구조를 사용하세요.
- 내용이 자연스럽게 이어지도록 작성하세요.
- 불필요한 반복은 피하세요.
- 마크다운 형식으로 작성하세요.
{_chapter_template_block(book_config)}{_output_requirements_block(book_config)}"""


def write_user(book_config: dict, chapter: dict) -> str:
    # chapter_template, output_requirements는 시스템 프롬프트에서 처리하므로 제외
    config_for_user = {
        k: v for k, v in book_config.items()
        if k not in ("chapter_template", "output_requirements")
    }
    return f"""
책 설정:
{json.dumps(config_for_user, ensure_ascii=False, indent=2)}

작성할 챕터:
{json.dumps(chapter, ensure_ascii=False, indent=2)}

위 정보를 바탕으로 이 챕터의 원고를 작성해주세요.
"""


# =========================
# REVIEW AGENT
# =========================

def build_review_system(book_config: dict) -> str:
    return f"""
당신은 전문 원고 검수자입니다.

목표:
원고를 더 예쁘게 고치는 것이 아니라,
내용 오류, 논리 오류, 누락, 지침 위반을 찾아내는 것입니다.

검수 기준:
1. 사실 오류 또는 기술적 오류
2. 논리적으로 앞뒤가 맞지 않는 설명
3. 챕터 설명에 있는데 빠진 내용
4. writing_guidelines 위반
5. 챕터 주제에서 벗어난 내용
6. 용어, 인물, 설정, 문체의 불일치
7. 독자가 오해할 수 있는 모호한 설명
8. 불필요한 반복 또는 장황한 내용
{_chapter_template_block(book_config)}

반드시 JSON으로만 응답하세요. JSON 외 다른 텍스트는 절대 출력하지 마세요.

출력 형식:
{{
  "has_errors": true,
  "score": 0,
  "issues": [
    {{
      "type": "factual_error | logical_error | missing_content | guideline_violation | off_topic | inconsistency | unclear | redundancy",
      "severity": "low | medium | high",
      "problem": "문제 설명",
      "original_text": "문제가 되는 원문 문장 또는 구절",
      "fix_instruction": "수정 지시"
    }}
  ],
  "summary": "전체 검수 요약"
}}

오류가 없으면:
{{
  "has_errors": false,
  "score": 95,
  "issues": [],
  "summary": "검수 결과 큰 문제 없음"
}}
"""


def review_user(book_config: dict, chapter: dict, draft: str) -> str:
    config_for_user = {
        k: v for k, v in book_config.items()
        if k not in ("chapter_template", "output_requirements")
    }
    return f"""
책 설정:
{json.dumps(config_for_user, ensure_ascii=False, indent=2)}

챕터 정보:
{json.dumps(chapter, ensure_ascii=False, indent=2)}

검수할 원고:
{draft}

위 원고를 검수해주세요.
"""


# =========================
# REVISE AGENT
# =========================

def build_revise_system(book_config: dict) -> str:
    return f"""
당신은 전문 원고 수정자입니다.

목표:
검수자가 발견한 문제를 반영하여 원고를 수정합니다.

규칙:
- review_json의 issues를 반드시 반영하세요.
- 사실 오류와 논리 오류는 정확하게 고치세요.
- 누락된 내용은 자연스럽게 추가하세요.
- 지침 위반은 writing_guidelines 기준에 맞게 수정하세요.
- 원문의 좋은 부분은 유지하세요.
- 문제가 없는 부분은 불필요하게 바꾸지 마세요.
- 마크다운 형식을 유지하세요.
- 최종 원고만 출력하세요.
{_chapter_template_block(book_config)}{_output_requirements_block(book_config)}"""


def revise_user(book_config: dict, chapter: dict, draft: str, review_json: str) -> str:
    config_for_user = {
        k: v for k, v in book_config.items()
        if k not in ("chapter_template", "output_requirements")
    }
    return f"""
책 설정:
{json.dumps(config_for_user, ensure_ascii=False, indent=2)}

챕터 정보:
{json.dumps(chapter, ensure_ascii=False, indent=2)}

검수 결과:
{review_json}

원문:
{draft}

검수 결과를 반영해 최종 원고로 수정해주세요.
"""

# 개선 파이프라인 설계 (추후 적용용)

> 현재는 레퍼런스(prof-lijar) 방식 그대로 구현 후, 안정화되면 이 설계로 교체.

---

## 변경 방향

| 항목 | 현재 (레퍼런스) | 개선 후 |
|---|---|---|
| 모델 | Gemma 31B 단일 | Gemma 31B 단일 (동일), temperature만 분리 |
| 검토 방식 | 같은 모델 self-review | 체크리스트 기반 구조화 검증 |
| 출력 형식 | 자유 텍스트 | Critic 단계 JSON 고정 출력 |
| 재작성 트리거 | 없음 | `overall: "revise"` 일 때만 Editor 호출 |

---

## 파이프라인 흐름

```
outline + chapter_title
        │
        ▼
  [Writer  t=0.8]   창의적 초안 작성
        │
        ▼
  [Critic  t=0.2]   체크리스트 JSON 반환
        │
        ├── overall: "pass"   ──→  [Editor t=0.5]  문체만 다듬기
        └── overall: "revise" ──→  [Editor t=0.5]  지적사항 반영 후 수정
                                          │
                                          ▼
                                      최종 챕터 저장
```

---

## 구현 코드

```python
import ollama
import json

MODEL = "gemma4:31b"

def call(system: str, user: str, temperature: float) -> str:
    res = ollama.chat(
        model=MODEL,
        options={"temperature": temperature},
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ]
    )
    return res["message"]["content"]


def write_chapter(outline: str, chapter_title: str) -> str:
    system = """당신은 전문 작가입니다.
주어진 개요를 바탕으로 챕터 본문을 작성하세요.
- 독자 수준: 입문자
- 분량: 800~1200 단어
- 예시를 반드시 1개 이상 포함"""
    return call(system, f"개요:\n{outline}\n\n챕터: {chapter_title}", temperature=0.8)


def review_chapter(draft: str) -> dict:
    system = """아래 체크리스트 항목을 하나씩 확인하고
JSON 형식으로만 응답하세요. 설명은 간결하게."""

    prompt = f"""글:
{draft}

다음 항목을 확인하고 JSON으로 반환하세요:
{{
  "has_example": true/false,
  "logic_flow": "ok" | "gap" | "unclear",
  "undefined_terms": ["용어1", "용어2"],
  "weak_sections": ["문단 요약"],
  "overall": "pass" | "revise"
}}"""

    raw = call(system, prompt, temperature=0.2)
    try:
        return json.loads(raw)
    except Exception:
        return {"overall": "pass", "raw": raw}


def edit_chapter(draft: str, review: dict) -> str:
    issues = []
    if not review.get("has_example"):
        issues.append("- 예시가 없습니다. 구체적인 예시를 1개 추가하세요.")
    if review.get("undefined_terms"):
        terms = ", ".join(review["undefined_terms"])
        issues.append(f"- 다음 용어에 간단한 정의를 추가하세요: {terms}")
    if review.get("weak_sections"):
        issues.append(f"- 보강 필요: {review['weak_sections']}")

    if not issues:
        system = "문장을 더 자연스럽고 읽기 쉽게 다듬으세요. 내용은 바꾸지 마세요."
        return call(system, draft, temperature=0.5)

    system = "아래 지적사항을 반영해 글을 수정하세요. 전체 구조는 유지하세요."
    prompt = "지적사항:\n" + "\n".join(issues) + f"\n\n원문:\n{draft}"
    return call(system, prompt, temperature=0.5)


def generate_chapter(outline: str, chapter_title: str) -> str:
    draft  = write_chapter(outline, chapter_title)
    review = review_chapter(draft)

    if review.get("overall") == "revise":
        draft = edit_chapter(draft, review)

    return draft
```

---

## 적용 시점 기준

아래 중 하나라도 해당되면 이 설계로 전환:

- [ ] 생성된 책 중 예시 없는 챕터가 30% 이상
- [ ] 용어 정의 누락 피드백이 반복될 때
- [ ] 챕터 재작성 없이 품질이 일정 수준 이하로 유지될 때

---

## 참고

- 적대적 프롬프트보다 체크리스트 방식이 안정적인 이유: 모델 입장에서 "비판하라"보다 "이 항목이 있냐 없냐"가 훨씬 단순한 질문이라 출력이 일관됨
- Critic temperature를 0.2로 낮추는 것이 핵심 — 판단이 매번 달라지지 않음

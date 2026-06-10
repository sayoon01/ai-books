# 챕터 생성 파이프라인 상세 설명

## 파이프라인이란

책 한 챕터를 완성하기까지 거치는 **Writer → Review → Revise → Re-review** 4단계 흐름입니다.  
모든 단계는 같은 모델(gemma4:31b)을 쓰지만, 시스템 프롬프트와 temperature가 달라 역할이 분리됩니다.

---

## 두 파일의 역할 분리

```
prompts.py        →  "LLM에게 무슨 말을 할지" 정의
book_writer.py    →  "언제, 어떤 순서로 말을 걸지" 제어
```

### prompts.py 구조

```
WRITE_SYSTEM    ─┐
REVIEW_SYSTEM   ─┼─ 시스템 프롬프트 (엔진 규칙, 고정)
REVISE_SYSTEM   ─┘   책이 바뀌어도 변하지 않음

write_user()    ─┐
review_user()   ─┼─ 유저 메시지 빌더 (책 의도, 호출마다 생성)
revise_user()   ─┘   book_config + chapter + draft 등을 받아 문자열 조립
```

### book_writer.py 구조

```
_call()                         Ollama 실제 호출 (model / temperature / num_ctx)

write_chapter()                 WRITE_SYSTEM + write_user() → _call() → draft 반환
review_chapter()                REVIEW_SYSTEM + review_user() → _call() → JSON 파싱
revise_chapter()                REVISE_SYSTEM + revise_user() → _call() → 수정 원고 반환

generate_book()                 챕터 루프 전체 제어
                                  - 분기 판단 (revise 여부)
                                  - previous_summaries 누적
                                  - 품질 로그 저장
                                  - GitHub 푸시 호출
```

---

## 챕터 하나의 데이터 흐름

```
[입력]
  book_config           = TOC에서 추출 (title / goal / book_style / writing_guidelines 등)
  chapter               = 현재 챕터 (number / title / description)
  previous_summaries    = 이전 챕터 누적 목록 (챕터 1은 빈 리스트)

      │
      ▼
┌─────────────────────────────────────────────────────┐
│  [1/4] write_chapter()                              │
│                                                     │
│  시스템: WRITE_SYSTEM (분량·형식·구성 흐름 정책)       │
│  유저:   write_user(book_config, chapter,           │
│                     previous_summaries)             │
│                                                     │
│  temperature = 0.8  (창의적 초안)                    │
│       ↓                                             │
│  → draft (마크다운 원고)                              │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  [2/4] review_chapter()                             │
│                                                     │
│  시스템: REVIEW_SYSTEM (검수 기준 8항목               │
│                         + JSON 출력 강제)            │
│  유저:   review_user(book_config, chapter, draft)   │
│                                                     │
│  temperature = 0.2  (일관된 판단)                    │
│       ↓                                             │
│  → review_data {"has_errors": bool,                 │
│                  "score": 0~100,                    │
│                  "issues": [...]}                   │
└─────────────────────────────────────────────────────┘
      │
      ├── score ≥ 90 & has_errors=False  →  final = draft (수정 없이 저장)
      │
      └── score < 90 or has_errors=True
              │
              ▼
      ┌─────────────────────────────────────────────────┐
      │  [3/4] revise_chapter()                         │
      │                                                 │
      │  시스템: REVISE_SYSTEM (issues 반영 규칙)         │
      │  유저:   revise_user(book_config, chapter,      │
      │                      draft, review_json)        │
      │                                                 │
      │  temperature = 0.5  (교정·균형)                  │
      │       ↓                                         │
      │  → revised (수정된 원고)                          │
      └─────────────────────────────────────────────────┘
              │
              ▼
      ┌─────────────────────────────────────────────────┐
      │  [4/4] review_chapter() 재검수                  │
      │                                                 │
      │  revised 원고를 같은 방식으로 재검수               │
      │  결과와 무관하게 final = revised 로 저장           │
      │  (무한루프 방지 — 1회만)                          │
      └─────────────────────────────────────────────────┘
              │
              ▼

[출력]
  chapter-NN.md         로컬 저장 + GitHub 커밋
  chapter-NN-review.json  품질 로그 (initial_review / revised / re_review)
  chapter_summaries     += "{N}장 {제목}: {description}"  (다음 챕터에 전달)
```

---

## score는 누가 정하는가

**Gemma(LLM)가 스스로 판단합니다.**

`REVIEW_SYSTEM`에 검수 기준 8항목과 JSON 출력 형식을 명시하면, Gemma가 원고를 읽고 직접 점수를 내놓습니다.

```
검수 기준 (REVIEW_SYSTEM에 명시):
  1. 사실 오류 또는 기술적 오류
  2. 논리적으로 앞뒤가 맞지 않는 설명
  3. 챕터 설명에 있는데 빠진 내용
  4. writing_guidelines 위반
  5. 챕터 주제에서 벗어난 내용
  6. 용어·인물·설정·문체의 불일치
  7. 독자가 오해할 수 있는 모호한 설명
  8. 불필요한 반복 또는 장황한 내용
```

| 주체 | 역할 |
|------|------|
| Gemma | score 0~100 판단 (주관적, LLM 자체 평가) |
| 코드 (generate_book) | `score < 90` 임계값으로 revise 여부 결정 |

```python
# book_writer.py — generate_book()
if review_data.get("has_errors") or review_data.get("score", 100) < 90:
    revised = revise_chapter(...)   # 임계값 90은 사람이 설정
```

temperature=0.2라 매 호출마다 점수가 크게 흔들리지는 않지만, 동일 원고도 호출마다 소폭 달라질 수 있습니다.

---

## 챕터 간 연결 — previous_summaries

Writer는 각 챕터를 독립적으로 쓰면 책 전체가 따로 놀 수 있습니다.  
이를 방지하기 위해 완성된 챕터의 요약을 리스트로 누적해 다음 챕터 Writer에게 전달합니다.

```python
# generate_book() 루프
chapter_summaries = []

for chapter in chapters:
    draft = write_chapter(config, chapter, chapter_summaries[:])  # 현재: 전체 전달
    ...
    chapter_summaries.append(f"{num}장 {ctitle}: {chapter.get('description', '')}")
    # 나중에 챕터가 많아지면 → chapter_summaries[-8:]  한 줄만 수정
```

Writer가 받는 유저 메시지에 다음 섹션이 추가됩니다:

```
이전 챕터 요약:
1장 머신러닝이란 무엇인가: 머신러닝의 개념과 종류를 소개하고...
2장 파이썬 개발 환경 구축: Anaconda 설치부터 가상환경 설정까지...
```

---

## JSON 파싱 안전장치

Gemma가 JSON 대신 자연어를 섞어 출력하는 경우를 `_parse_review()`에서 3단계로 처리합니다.

```python
# 1단계: ```json ... ``` 블록 추출
if "```" in text:
    text = text.split("```")[1]
    if text.startswith("json"):
        text = text[4:]

# 2단계: 앞뒤 자연어 제거 — {} 사이만 추출
match = re.search(r'\{.*\}', text, re.DOTALL)
if match:
    text = match.group()

# 3단계: 파싱 실패 → 강제 Revise
try:
    return json.loads(text.strip())
except Exception:
    return {"has_errors": True, "score": 0, ...}  # 검수 실패 = 이슈 있음으로 처리
```

파싱 실패를 `has_errors=False`로 처리하면 망한 검수가 통과처리되므로, 반드시 `has_errors=True`로 강제합니다.

---

## GitHub 자동 푸시 시퀀스

챕터 완료마다 `github_push.py`를 통해 2번의 커밋이 발생합니다.

```
챕터 완료
  ├── push_chapter()     → chapter-NN.md 커밋+푸시
  │                        "feat(slug): chapter-NN 제목"
  │
  └── update_meta()      → meta.json 갱신+커밋+푸시
                           "chore(slug): meta.json 업데이트 (N/전체)"

마지막 챕터 완료
  └── update_readme()    → README.md 책 목록 테이블 갱신+커밋+푸시
                           "docs: README 책 목록 업데이트"
```

GitHub에 푸시되면 Vercel이 GitHub REST API로 파일을 읽어 60초 캐시 만료 후 웹에 자동 반영됩니다. 재배포 없이 새 챕터가 보입니다.

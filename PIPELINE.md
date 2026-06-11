# 챕터 생성 파이프라인 상세 설명
<img width="1057" height="612" alt="image" src="https://github.com/user-attachments/assets/6ad5062d-2bee-49a1-9bc4-5bbe3e76c7e5" />



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
      └─────────────────────────────────────────────────┘      <img width="464" height="312" alt="image" src="https://github.com/user-attachments/assets/90263fd2-91f4-4cc5-a3a0-47792e293baa" />

              │
              ▼

[출력]
  chapter-NN.md         로컬 저장 + GitHub 커밋
  chapter-NN-review.json  품질 로그 (initial_review / revised / re_review)
  chapter_summaries     += "{N}장 {제목}: {description}"  (다음 챕터에 전달)
```

---

## 에이전트별 역할 상세

### 1. Writer (t=0.8) — 창의적 초안

| 항목 | 내용 |
| --- | --- |
| 시스템 | `WRITE_SYSTEM` — 분량(3000~5000단어), 마크다운 형식, `writing_guidelines` 최우선, 구성 흐름(개념→설명→예시→요약) |
| 유저 | `write_user(book_config, chapter, previous_summaries)` — 책 설정 + 이전 챕터 요약 + 현재 챕터 정보 |
| 출력 | 완결된 마크다운 원고 (`draft`) |

### 2. Review (t=0.2) — 일관된 검수

| 항목 | 내용 |
| --- | --- |
| 시스템 | `REVIEW_SYSTEM` — 검수 기준 8항목 + JSON 출력 형식 강제 |
| 유저 | `review_user(book_config, chapter, draft)` — 책 설정 + 챕터 정보 + 검수 대상 원고 |
| 출력 | JSON (아래 형식) |

```json
{
  "has_errors": true,
  "score": 85,
  "issues": [
    {
      "type": "factual_error",
      "severity": "high",
      "problem": "문제 설명",
      "original_text": "원문 발췌",
      "fix_instruction": "수정 지시"
    }
  ],
  "summary": "전체 검수 요약"
}
```

`type` 예시: `factual_error` · `logical_error` · `missing_content` · …  
`severity`: `low` · `medium` · `high`

**score는 LLM이 스스로 매깁니다.** 코드는 `score < 90` 또는 `has_errors=True`일 때만 Revise로 보냅니다.

```python
# generator/book_writer.py — generate_book()
if review_data.get("has_errors") or review_data.get("score", 100) < 90:
    revised = revise_chapter(...)
```

### 3. Revise (t=0.5) — 이슈 반영 수정

| 항목 | 내용 |
| --- | --- |
| 시스템 | `REVISE_SYSTEM` — `issues` 반드시 반영, 좋은 부분 유지, 불필요한 변경 금지 |
| 유저 | `revise_user(book_config, chapter, draft, review_json)` — 검수 결과 JSON + 원문 |
| 출력 | 수정된 원고 (`revised`) |

### 4. Re-Review (t=0.2) — 재검수 (로그용)

- `review_chapter()`를 `revised`에 다시 호출
- 재검수 결과가 나빠도 `final = revised`로 저장 — Revise를 1회만 돌려 무한루프 방지
- 잔여 `high` severity 이슈는 콘솔에만 출력

```python
# generator/book_writer.py — generate_book()
re_review = review_chapter(config, chapter, revised, step="4/4")
final = revised  # 재검수 점수와 무관하게 revised 채택

remaining = [i for i in re_review.get("issues", []) if i.get("severity") == "high"]
print(f"  [4/4] 재검수 후 잔여 이슈 {len(remaining)}건 — 현재 버전으로 저장")
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

## 챕터 간 연결 - previous_summaries 
<img width="1075" height="716" alt="image" src="https://github.com/user-attachments/assets/6a262910-b04d-46ed-b359-3abdf5230f47" />

Writer는 각 챕터를 독립적으로 쓰면 책 전체가 따로 놀 수 있습니다.  
이를 방지하기 위해 완성된 챕터 정보를 리스트로 누적해 다음 챕터 Writer에게 전달합니다.

### 코드 위치 (3곳)

**① 누적·전달 — `generate_book()`**

```python
# generator/book_writer.py
chapter_summaries = []  # 나중에 [-8:] 슬라이싱으로 교체 가능

for chapter in chapters:
    ...
    draft = write_chapter(config, chapter, chapter_summaries[:])
    ...
    chapter_summaries.append(f"{num}장 {ctitle}: {chapter.get('description', '')}")
```

**② Writer에 전달 — `write_chapter()`**

```python
# generator/book_writer.py
def write_chapter(book_config: dict, chapter: dict, previous_summaries: list = None) -> str:
    ...
    return _call(WRITE_SYSTEM, write_user(book_config, chapter, previous_summaries), temperature=0.8)
```

**③ 프롬프트에 삽입 — `write_user()`**

```python
# generator/prompts.py
def write_user(book_config: dict, chapter: dict, previous_summaries: list = None) -> str:
    prev_section = ""
    if previous_summaries:
        prev_text = "\n".join(previous_summaries)
        prev_section = f"\n이전 챕터 요약:\n{prev_text}\n"
    ...
```

### 무엇이 쌓이는가

실제 원고 요약이 아니라, **TOC의 `chapter.description`** 이 문자열로 누적됩니다.

```
1장 머신러닝이란 무엇인가: 머신러닝의 개념과 종류를 소개하고...
2장 파이썬 개발 환경 구축: Anaconda 설치부터 가상환경 설정까지...
```

챕터 N을 쓸 때는 **1 ~ N-1장 description만** 전달됩니다 (`chapter_summaries[:]`로 복사본 전달).

### 중복 방지·흐름 유지 메커니즘

| 레이어 | 역할 |
| --- | --- |
| `previous_summaries` | Writer에게 "이미 다룬 챕터 범위"를 알려줌 → 같은 주제를 처음부터 다시 설명하는 것을 억제 |
| `WRITE_SYSTEM` | "불필요한 반복은 피하세요", "내용이 자연스럽게 이어지도록" |
| `REVIEW_SYSTEM` | 검수 기준 8번 — "불필요한 반복 또는 장황한 내용" (`redundancy`) |
| `chapter.description` | 현재 챕터가 무엇을 새로 다뤄야 하는지 명시 → 이전 챕터와 겹치지 않게 범위 분리 |

즉, **Writer 단계에서 선제적으로 맥락을 주고, Review 단계에서 사후 검증**하는 2중 구조입니다.

### 확장 포인트

챕터가 많아지면 컨텍스트 초과를 막기 위해 **한 줄만** 바꾸면 됩니다.

```python
# 현재: 전체 전달
draft = write_chapter(config, chapter, chapter_summaries[:])

# 나중에: 최근 8장만
draft = write_chapter(config, chapter, chapter_summaries[-8:])
```

---

## 부가 안전장치 — JSON 파싱

Gemma가 JSON 대신 자연어를 섞어 출력하는 경우를 `_parse_review()`에서 3단계로 처리합니다.
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

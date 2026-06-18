# AI Book 생성 파이프라인 개선 검토 (2026.06.18)

<img width="1536" height="1024" alt="ChatGPT Image 2026년 6월 18일 오후 05_49_45" src="https://github.com/user-attachments/assets/80894e91-de6d-4284-a805-f6e11c43dbc8" />


## 개요

AI Book 생성기는 기본적으로 다음 구조로 동작합니다.

```text
Write → Review → Revise
```

챕터 제목이나 설명 없이 Grounding 문서만 제공되는 경우에는 Outline Agent가 먼저 Grounding을 분석하여 목차와 챕터 설명을 생성하도록 구성하였습니다.

---

## 실험 목적

본문 작성 전 설계 단계를 추가하는 것이 실제 생성 품질 향상에 도움이 되는지 검증하기 위해 Planner Agent를 추가한 구조를 실험하였습니다.

적용 문서

* 금형-사출-센서-데이터-자동-해석 가이드

---

## V1 구조

```text
Grounding
    ↓
Outline
    ↓
Write
    ↓
Review
    ↓
Revise
```

### 역할

* Grounding 기반 목차 생성
* 챕터별 본문 작성
* 품질 검토 및 수정

---

## V2 구조

```text
Grounding
    ↓
Outline
    ↓
Planner
    ↓
Write
    ↓
Review
    ↓
Revise
```

### Planner 역할

본문 작성 전에 챕터별 작성 방향을 설계

* 챕터 목표 정의
* 핵심 설명 흐름 설계
* 포함해야 할 내용 정리
* Grounding 활용 계획 수립

---

## 비교 항목

* 문장 자연스러움
* 내용 연결성
* 챕터 완성도
* 설명 일관성
* Grounding 반영 수준

---

## 검증 방법

생성된 결과물을 Google NotebookLM에 업로드하여 Podcast를 생성한 뒤 비교 평가를 수행하였습니다.

```text
V1 생성
   ↓
NotebookLM 업로드
   ↓
Podcast 생성

V2 생성
   ↓
NotebookLM 업로드
   ↓
Podcast 생성

결과 비교
```

---

## 결과

| 항목     | V1 | V2 |
| ------ | -- | -- |
| 문장 자연성 | 보통 | 우수 |
| 내용 흐름  | 보통 | 우수 |
| 챕터 완성도 | 보통 | 우수 |
| 설명 일관성 | 보통 | 우수 |

### 평가 결과

V2 구조가 전반적으로 더 자연스럽고 이해하기 쉬운 콘텐츠를 생성하였습니다.

특히 Planner 단계가 추가되면서

* 문단 간 연결성 향상
* 챕터 내 설명 흐름 개선
* 중복 설명 감소
* 내용 누락 감소

효과가 확인되었습니다.

---

## 확인된 이슈

### Grounding 문서 파싱

일부 문서에서 다음 문제가 확인되었습니다.

* 특수문자 일부 누락
* 수식 표현 손실
* 원문 구조 일부 훼손

### 개선 필요 사항

* 파서 로직 개선
* 수식 보존 처리
* 특수문자 처리 강화

---

## 검토 사항

### 선택지 A : 단순 구조 유지

```text
Outline → Write → Review → Revise
```

장점

* Agent 수 최소화
* 처리 속도 우수
* 구조 단순

단점

* 챕터 품질 편차 발생 가능

---

### 선택지 B : Planner 추가

```text
Outline → Planner → Write → Review → Revise
```

장점

* 생성 품질 향상
* 설명 흐름 개선
* 챕터 완성도 향상

단점

* 처리 시간 증가
* Agent 수 증가

---

## 현재 의견

NotebookLM Potcast 비교 결과를 기준으로 판단했을 때 Planner 단계가 생성 품질 향상에 긍정적인 영향을 주는 것으로 확인되었습니다.

따라서 기본 구조를

```text
Outline → Planner → Write → Review → Revise
```

형태로 운영하는 방안을 검토할 필요가 있습니다.

---

## 결론

* Planner Agent 추가 시 생성 품질 향상 확인
* V2 구조가 V1 대비 자연스러운 결과 생성
* Grounding 파서 개선 필요
* Planner 포함 구조를 기본 파이프라인으로 검토

# ADK 이관 정리 — 그래프 Workflow부터 멀티 에이전트·관측까지 (2026.06.19 ~ 06.22)

## 개요

기존 책 생성기(`generator/`)를 **Google ADK 기반 파이프라인(`ADK_AGENT/`)**으로 옮긴
작업의 정리입니다. 06.19에 ADK 그래프 Workflow로 신규 구현을 끝내고, 06.22에
**레거시 아카이브 · 멀티 에이전트 엔진 · 관측(Observability)**을 더해 ADK_AGENT를
메인 파이프라인으로 정돈했습니다.

> 핵심 원칙: **Write → Review → Revise 역할은 유지**한다. 앞에 **Design 단계**를 추가하고,
> 프롬프트·grounding을 **state 변수**로 다룬다. GitHub 자동 push·PDF는 그대로 둔다.

---

## 배경 — 왜 ADK로 옮겼나

* 레퍼런스(Gemini+ADK)는 "링크/파일만 instruction에 주면" 모델이 알아서 읽지만,
  우리 모델(ollama `gemma4:31b`)은 파일/URL을 **네이티브로 못 읽는다**.
  → "소스 읽는 코드"는 얇은 reader로 남기고, **역할만** ADK 에이전트로 바꾼다.
* 사람이 책마다 특화 프롬프트를 쓰는 대신, **Design이 집필 지시문(write_brief)을 자동 생성**한다.
* ADK 표준 API와 `adk web` 호환·역할 분리·관측을 얻기 위함.

---

## 전체 구조

```text
[파이썬] source 읽기(얇은 reader) ─────────▶ state["source_text"]
[파이썬] design.json 있으면 로드, 없으면 생성  ▶ {chapters, write_brief, grounding_digest}
         (웹 UI가 design.json 편집 → 본문만 재생성)
[파이썬] for ch in chapters:                  ← push / PDF 는 여기 (유지)
   └ 챕터 1개 = 엔진이 처리
        START → write → length_guard(가드①)
              → {rewrite: write, ok: review}
              → review → gate
              → {revise: revise, done: finalize}
              → revise → review (재검수 사이클)
[파이썬] build_pdf · push_pdf
```

* **ADK** = 챕터 1개의 LLM 파이프라인(작성·검수·수정·게이트).
* **파이썬** = design 1회 호출, 챕터 for문, 요약 누적, 파일 저장, push, PDF (전부 I/O라 유지).

---

## 1단계 (06.19) — ADK 그래프 Workflow 기반 신규 구현

`generator/` 무수정 원칙 하에 `ADK_AGENT/`에 독립 재구현(필요 함수만 복사).

### 현실 제약 3가지 (설계를 좌우)

1. 로컬 모델은 파일/URL 비네이티브 → 소스 추출(xlsx/API→텍스트)은 얇은 함수로 남긴다.
2. ADK `output_schema` LlmAgent는 tool 사용 불가 → 구조화 단계는 기존
   `call_structured`(ollama `format=` 제약 디코딩)를 쓴다.
3. ADK 2.3.0에서 `SequentialAgent`/`LoopAgent`/`ParallelAgent` 전부 deprecated
   → 챕터 파이프라인을 **그래프 `google.adk.workflow.Workflow`**(Node/Edge/route)로 구성.
   escalate 대신 `ctx.route`로 분기, 루프 상한은 state 카운터(`write_count`/`pass_count`)로 대체.

### 핵심 설계 결정

* **Design 단계 추가:** 입력(+source)을 읽고 `chapters` · `write_brief` · `grounding_digest`
  세 가지를 한 번에 생성. planner(UnitPlan)는 별도 노드 없이 Design에 흡수
  (챕터 의도=`ChapterSpec.description`, 구성 관례=`write_brief`).
* **편집 가능한 아티팩트:** Design 출력을 `design.json`으로 저장. "있으면 로드, 없으면 생성"
  규칙으로 웹/사람이 고친 값을 존중(`--redesign`으로 강제 재생성).
* **변수화 범위:** 책마다 바뀌는 `write_brief`만 생성형 변수, review/revise/design SYSTEM은
  검수 기준 일관성을 위해 **정적 유지**. 튜너블 숫자는 코드 상수.
* **하이브리드 JSON 신뢰성:** write/revise=자유 마크다운(LlmAgent), review/design=구조화
  (`call_structured` constrained decoding + 재시도).
* **길이 가드(MIN_CHARS=500):** 생성 실패(빈/잘린 챕터) 감지 전용 바닥선. 품질(3,000자)은
  reviewer 담당으로 분리. (배경: 금형 v1에서 chapter 7이 0자로 저장된 사건.)

### 안정화 (06.19 후속)

* **DesignPlan → `call_parsed` 전환:** 제약 디코딩 반복 루프를 회피.
* **keep-best 초안 보존:** review→revise 과정에서 최고 점수 초안을 보존.
* **trace 기록:** 단계별 history(`agent/trace.py`)를 남김.

---

## 2단계 (06.22) — 표준화 · 멀티 에이전트 · 관측

### 레거시 아카이브

* 루트 `generator/` · `toc/` · 책 산출물(unit·chapter·meta·PDF)을 **`5_AGENT/`로 이전**.
* `ADK_AGENT/`를 메인 파이프라인으로 확정.

### 멀티 에이전트 엔진 병행 (`--engine`)

* 결정(06.22): **코드 오케스트레이션 멀티 에이전트**로 간다. 하이브리드는 보류(기록만).
* write/review/revise/design을 각각 독립 역할 에이전트로 표현하고, 순서는 코드
  (ADK 표준 `SequentialAgent`/`LoopAgent`)가 결정. 품질 게이트·keep-best·grounding은 그대로.
* 현 그래프 엔진은 **지우지 않고** `--engine {graph|agent}`로 병행(기본 `graph`) → 검증 후 전환.

```text
SequentialAgent("chapter", [
    writer_agent,                         # 초안 1회
    LoopAgent("refine",
        [reviewer_agent, gate_agent, reviser_agent],
        max_iterations=PASS_MAX),         # 검수→(통과 시 escalate 탈출)→수정 반복
])
```

> 솔직한 평가: 이 단계는 "현 그래프를 ADK 표준 에이전트로 다시 표현"에 가깝다.
> 순이득은 **표준 API·역할 분리·`adk web` 호환**이고, 흐름·품질 보장은 그래프와 동등.

### 관측(Observability) — Phoenix + Langfuse

* ADK가 방출하는 **OpenTelemetry trace**를 대시보드로 본다(챕터별 단계 타임라인·프롬프트/응답·토큰).
* 두 백엔드를 독립적으로 켤 수 있고, 둘 다 켜면 같은 trace가 양쪽에 동시 전송(**fan-out**).

| 백엔드 | 성격 | 무게 | UI |
| --- | --- | --- | --- |
| Phoenix | LLM 전용 관측, 단계 디버깅에 최적 | 가벼움(단일 컨테이너) | http://localhost:6006 |
| Langfuse | 제품급(세션·비용·다중 실행 누적) | 무거움(6개 컨테이너) | http://localhost:3000 |

* **기본 자동:** env가 로드된 백엔드로 생성 시 자동 전송, 없으면 조용히 OFF. 끄려면 `--no-trace`.
* 알려진 이슈: docker 권한 문제.

### 구조 정리

* `core/source_reader.py` → **`core/grounding.py`**로 개명(grounding 관련을 한 곳에).
* 튜너블 상수를 **`core/config.py`**로 모음(아래 표).
* `agent/prompts.py` → **`agent/prompt_blocks.py`**: 단계별 SYSTEM 프롬프트가 각 단계 파일
  (design/write/review/revise)로 빠지고, 공유 블록 헬퍼(`block`/`prev_block`/`chapter_block`)만 남아
  실제 역할에 맞게 개명.

### 출력 정책 강화 (`write.py`의 `WRITE_OUTPUT_POLICY`)

특수문자 깨짐 대응으로 출력 정책을 명시적으로 보강:

* 특정 Markdown 렌더러·브라우저·확장 프로그램·LaTeX 엔진·HTML 렌더러·Mermaid 플러그인에
  의존하는 문법 **금지**(특수문자 깨짐·표시 누락 원인).
* 수식은 LaTeX 대신 일반 텍스트·기호로, 도식은 Mermaid 대신 글머리표·표·코드블록으로.

---

## 핵심 설정값 (`core/config.py`)

| 상수 | 값 | 의미 |
| --- | --- | --- |
| MODEL | gemma4:31b | 생성 모델(ollama) |
| LLM_NUM_CTX | 32768 | 컨텍스트 길이 |
| LLM_KEEP_ALIVE | 30m | 모델 언로드 방지(런너 레이스 차단) |
| QUALITY_GATE | 80 | 위반 0 + 이 점수 이상이면 통과 |
| TARGET_SCORE | 90 | 이 점수면 더 안 끌어올림 |
| MIN_CHARS | 500 | 본문 최소 길이(가드) |
| WRITE_MAX / PASS_MAX | 3 / 3 | 초안 재작성 / 재수정 상한 |

---

## 검증

* `spikes/`로 ADK 동작 사실 검증(06.19~06.22):
  * `LiteLlm(num_ctx, keep_alive, repeat_penalty)` → ollama 전달 확인(`ollama ps` CONTEXT).
  * `LlmAgent`가 그래프 노드로 동작, `output_key`→state. route 자기참조 사이클로 루프 구성·종료.
  * 엔진 비교(`verify_engines.py`/`compare_engines.py`), trace 방출(`verify_trace.py`).
* 1챕터 E2E 스모크 통과.

---

## 남은 일

* `--engine agent`(멀티 에이전트) 품질·동작을 그래프와 비교 검증 후 기본 엔진 전환 판단.
* 동기 `call_structured`를 노드 안에 둘지, `asyncio.to_thread`로 분리할지(현재 직렬이라 보류).
* 생성 견고성(호출 timeout+retry, 챕터 flagged+continue, `--resume`)은 별도 TODO로 보류 중.
* 관측 docker 권한 이슈 정리.

---

## 결론

* `generator/` → `ADK_AGENT/` 이관 완료, 레거시는 `5_AGENT/`로 아카이브.
* 그래프 Workflow + 멀티 에이전트 엔진을 `--engine`으로 병행, 관측까지 붙여 메인 파이프라인 확정.
* Write→Review→Revise 역할 유지 + Design 추가 + 품질 게이트/keep-best/grounding 보존이라는
  뼈대는 두 단계 내내 동일하게 유지.

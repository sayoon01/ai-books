# ADK_AGENT 코드 구조 & 엔진 비교 (agent vs graph)

> 갱신: 2026.06.22 — `generator/` → `ADK_AGENT/` 이관 이후 현재 코드 상태와,
> 챕터 엔진 두 갈래(`graph` / `agent`)의 차이·비교 산출물을 정리한다.

기존 책 생성기(`generator/`)를 **Google ADK 기반 파이프라인(`ADK_AGENT/`)**으로 옮겼다.
레거시는 `5_AGENT/`로 아카이브했고, `ADK_AGENT/`가 메인이다.

핵심 원칙은 그대로다: **Write → Review → Revise 역할 유지** + 앞에 **Design 단계** 추가,
프롬프트·grounding을 **state 변수**로 다루고, GitHub push·PDF는 파이썬 쪽에 둔다.

---

## 1. 전체 실행 흐름

```text
main.py  (CLI: --toc / --engine / --no-push / --no-pdf / --no-trace / --redesign)
  └─ pipeline.generate()                         ← "전체 처리" (순수 파이썬, I/O 담당)
       ├─ read_source()                          소스(xlsx/HTTP API) → 텍스트 (얇은 reader)
       ├─ run_or_load_design()                   design.json 있으면 로드, 없으면 1회 생성
       │     → {chapters, write_brief, grounding_digest}
       └─ for ch in chapters:                    챕터 for문 + 요약 누적 + 저장/push/PDF
             └─ 챕터 1개 = "엔진"이 처리          ← 여기만 ADK
                  write → length_guard → review → gate → revise (재검수 사이클)
```

* **ADK 몫** = 챕터 1개의 LLM 파이프라인(작성·검수·게이트·수정).
* **파이썬 몫** = Design 1회, 챕터 for문, 요약 누적, 파일 저장, GitHub push, PDF — **전부 I/O**.
  (그래서 "전체를 하나의 ADK 에이전트로 감싸지" 않는다. I/O는 파이썬 for문이 더 단순·견고.)

---

## 2. 디렉토리 구조 (현재)

```text
ADK_AGENT/
├─ main.py              CLI 진입점 (인자 파싱 → pipeline.generate)
├─ pipeline.py          전체 오케스트레이션(파이썬): design 로드·챕터 루프·저장·push·PDF
│
├─ agent/               ── 챕터 파이프라인 (ADK) ──
│   ├─ common.py        ★ 공유 자산: Pydantic 스키마(Issue/QualityScores/ReviewResult/
│   │                     ChapterSpec/DesignPlan) + 블록 헬퍼(block/prev_block/chapter_block)
│   │                     + trace 기록(record)  ← schemas.py·trace.py·prompt_blocks.py 통합
│   ├─ design.py        Design 단계: DESIGN_SYS·design_user·run_or_load_design (목차+write_brief+digest)
│   ├─ write.py         초안 작성 노드 + 길이 가드: build_write_node / length_decision /
│   │                     build_length_guard / WRITE_OUTPUT_POLICY(출력 정책)
│   ├─ review.py        구조화 검수 + 게이트 판정: do_review / gate_decision /
│   │                     build_review_node / build_gate_node / REVIEW_SYSTEM
│   ├─ revise.py        수정 노드: build_revise_node / REVISE_SYSTEM
│   │
│   ├─ graph.py         ▷ 엔진 A: 그래프 Workflow (build_chapter_graph)
│   └─ agents.py        ▷ 엔진 B: 멀티 에이전트 (build_chapter_agent)
│
├─ core/               ── 인프라 ──
│   ├─ config.py        튜너블 상수 한 곳에(.env 자동 로드)
│   ├─ llm.py           ollama 호출: _call / call_structured(format=) / call_parsed / make_gemma(LiteLlm)
│   ├─ grounding.py     소스 읽기·캐시 + 수치 환각 검증: read_source / unverified_numbers / ground_block
│   ├─ textutil.py      normalize_math / strip_title_h1 / chapter_filename / parse_json
│   └─ tracing.py       OpenTelemetry 트레이싱 setup(Phoenix/Langfuse fan-out)
│
├─ publish/             github_push.py · pdf_export.py
├─ spikes/              ADK 동작 검증 실험 + 엔진 비교 도구(compare_engines.py / compare_similarity.py)
├─ toc/                 책 사양 JSON (예: mold-dx-auto.json)
└─ output/<slug>/       산출물: chapter-*.md · design.json · logs/ · meta.json · PDF
```

> **죽은 파일(삭제 후보):** `agent/schemas.py`, `agent/trace.py`, `agent/prompt_blocks.py`
> — 셋 다 `agent/common.py`로 흡수되어 현재 어디서도 import하지 않는다. 파일만 남아있음.

### 단계 파일이 엔진과 분리된 이유
`write.py`/`review.py`/`revise.py`/`design.py`의 **판정 함수와 노드 빌더는 두 엔진이 공유**한다.
즉 두뇌(로직)는 한 곳에 두고, `graph.py`/`agents.py`는 그것을 **엮는 골격**만 다르게 표현한다.

---

## 3. 엔진 비교 — `graph` vs `agent`

`--engine {graph|agent}`로 고른다(기본 `graph`). **둘 다 같은 챕터 흐름**
(write → length guard → review → gate → revise)을 만들고, **같은 state 키**를 산출한다.
차이는 "어떻게 엮느냐"뿐이다.

### 3.1 역할 관점 (개념도)

```text
[파이썬] DesignAgent (책당 1회)  →  chapters · write_brief · grounding_digest
   │                                  ※ ADK 에이전트가 아님 = run_or_load_design()
   │                                    (ollama 직접 호출, 엔진 트리 바깥에서 실행)
   ▼  for ch in chapters  (파이썬 for문 — 엔진은 챕터 1개만 처리)
   Writer  →  (검수) Reviewer ⇄ Reviser  →  확정(keep-best)
```

위 "역할"을 두 엔진이 각각 다른 골격으로 구현한다(아래 트리). 흔히 그리는
`Design → Sequential[Writer, Loop[Reviewer, Reviser]]` 그림은 **개념도**이고,
실제 구현은 가드(LengthGate)·게이트(Gate)가 더 들어가고 Design은 트리 밖에 있다.

### 3.2 `agent` 엔진 실제 트리 (`agents.py` · `build_chapter_agent`)

```text
SequentialAgent("chapter")
├─ LoopAgent("draft",  max_iterations=WRITE_MAX)
│    ├─ "write"   LlmAgent (make_gemma 0.8, output_key="draft")   초안 생성(자유 MD)
│    └─ LengthGate(BaseAgent)   length_decision() 호출
│           · chars ≥ MIN_CHARS → escalate=True (draft 루프 탈출)
│           · 미달 & write_count<WRITE_MAX → 재작성 / 상한 도달 → flagged 후 통과
└─ LoopAgent("refine", max_iterations=PASS_MAX+2)
     ├─ Reviewer(BaseAgent)   do_review() 호출 — 구조화 검수 + keep-best (escalate 안 함)
     ├─ Gate(BaseAgent)       gate_decision() 호출
     │      · stop(완료/수용) → escalate=True (refine 탈출, reviser 건너뜀)
     │      · 아니면 통과 → reviser 로
     └─ "revise" LlmAgent (make_gemma 0.5, output_key="draft")    수정 → draft 덮어쓰고 재검수
```

* Writer 는 단독이 아니라 **draft 루프(write + LengthGate)** 로 감싸짐.
* refine 루프는 Reviewer→**Gate**→Reviser **3단계**(흔한 그림의 2단계와 다름).
* 종료는 `escalate=True` 이벤트, `max_iterations` 는 안전 백스톱(`PASS_MAX+2`).
* ⚠ 커스텀 BaseAgent 의 state 변경은 `EventActions(state_delta=...)` 로만 영속(직접 대입은 휘발).

### 3.3 `graph` 엔진 실제 그래프 (`graph.py` · `build_chapter_graph`)

```text
START → write → length_guard ─┬─(rewrite)→ write          길이 미달 재작성
                              └─(ok)──────→ review
review → gate ─┬─(revise)→ revise → review                재검수 사이클(revise는 review로 복귀)
              └─(done)───→ finalize (터미널, 종료)
루프 상한: write_count / pass_count 카운터 (escalate 안 씀)
```

* write/revise 는 `agent` 엔진과 **같은 LlmAgent**(`build_write_node`/`build_revise_node`).
* length_guard/review/gate 는 `FunctionNode`(`length_guard_fn`/`review_fn`/`gate_fn`)로,
  분기는 `escalate` 대신 **`ctx.route`** 로. 종료는 `finalize` 터미널 노드 도달.

### 3.4 공유 로직 — 두 엔진의 "두뇌"는 같다

골격(트리/그래프)만 다르고, **판정은 동일한 순수 함수**를 호출한다(단일 출처):

| 순수 함수 | 위치 | 하는 일 | graph 래퍼 | agent 래퍼 |
| --- | --- | --- | --- | --- |
| `length_decision` | write.py | 길이 OK/재작성/flagged 판정 | `length_guard_fn` | `LengthGate` |
| `do_review` | review.py | 구조화 검수(call_structured) + keep-best | `review_fn` | `Reviewer` |
| `gate_decision` | review.py | 종료/재수정 판정 | `gate_fn` | `Gate` |

**gate 판정 규칙**(`gate_decision`): `must_fix`(위반 issue 또는 미검증 수치) → 고침,
`want_lift`(품질 약한 축<QUALITY_GATE, 또는 score<TARGET_SCORE, 또는 needs_revision) → 끌어올림.
종료 = ① 둘 다 아님(완료) / ② must_fix 없고 점수 정체(score ≤ last_score, 천장 수용) /
③ `pass_count > PASS_MAX`(상한 수용). **keep-best**: review.score 가 best 갱신 시 best_draft 보존
(revise 가 본문을 망가뜨려도 최고본 유지).

### 3.5 한눈에 보는 차이

| | `graph` (engine=graph, 현재 기본) | `agent` (engine=agent) |
| --- | --- | --- |
| ADK API | `google.adk.workflow.Workflow` (그래프) | `SequentialAgent` / `LoopAgent` |
| 흐름 표현 | **엣지(간선)** 명시: `(length_guard, {"rewrite": write, "ok": review})` | **중첩 구조**: Loop(draft) → Loop(refine) |
| 반복 종료 | 라우팅 — `finalize` 터미널 노드 도달 시 종료 | `escalate=True` 이벤트로 루프 탈출 |
| 루프 상한 | state 카운터 `write_count` / `pass_count` | `max_iterations` 백스톱 |
| 커스텀 코드 | 노드 엮기만 (≈38줄) | `LengthGate`/`Reviewer`/`Gate` 커스텀 BaseAgent 직접 구현 (≈98줄) |
| 판정 로직 | `length_decision`·`do_review`·`gate_decision` **공유** | **동일하게 공유** |

핵심: **두뇌(판정 함수)는 공유, 골격(엮는 방식)만 다르다.** 결과물은 같고 둘 중 하나는 잉여다.

### 어느 걸 남길지 — 상충하는 두 근거
* **API 현행성:** ADK 2.3.0에서 `SequentialAgent`/`LoopAgent`/`ParallelAgent`는 **deprecated**.
  → 이 기준이면 `agents.py`가 구식, **graph 유지**가 맞다.
* **채택 방향(06.22):** "코드 오케스트레이션 멀티 에이전트로 간다"고 기록.
  → 이 기준이면 **agent 채택**, graph 폐기.

→ 그래서 어느 쪽도 아직 삭제하지 않았다. **비교 검증 후 한쪽으로 확정**한다.

### 3.6 오케스트레이션 관점 — 지금은 둘 다 "코드 오케스트레이션"

두 엔진의 **공통점**은 흐름(다음에 누가 실행될지·반복·분기)을 **코드가 결정**한다는 것이다.

* **graph:** `Workflow` 의 엣지/`ctx.route` 가 흐름을 코드로 명시.
* **agent:** ADK 표준 **멀티 에이전트** `SequentialAgent`/`LoopAgent` 가 순서·반복을 코드로 고정.
* 판정(`length_decision`/`gate_decision`)도 **결정론적 순수 함수**(LLM 아님).

→ 즉 **LLM 은 각 노드 "안에서 작업만"** 한다(write/review/revise). 흐름 권한은 코드에 있다.
장점: **재현성·디버깅 용이·저비용·예측 가능**. 현재 채택 방향은 이 "코드 오케스트레이션 +
멀티 에이전트" 조합이다.

---

## 4. 비교가 산출하는 것 (`spikes/compare_engines.py`)

같은 책·**같은 design.json을 양쪽에 주입**해 순수하게 "엔진 차이"만 비교한다.
공정성 장치: 동일 design 주입(목차·write_brief·grounding 동일), 같은 slug로 source 캐시 공유,
push/pdf/trace는 끔.

```text
output/_compare/<slug>/
├─ graph/  agent/                각 엔진의 chapter-*.md + logs/chapter-*.json
├─ gpu_usage_graph.csv  gpu_usage_agent.csv   5초 샘플 GPU 시계열(증분 저장)
├─ comparison_summary.json       엔진별 종합 수치
├─ comparison_report.md          표 + 차트 임베드 + 우열 요약
└─ charts/
    ├─ compare_elapsed.png       챕터별 소요 시간
    ├─ compare_score.png         챕터별 품질 점수
    └─ compare_gpu.png           GPU VRAM 시계열
```

**비교 지표** (대부분 `pipeline.py`가 이미 챕터 로그에 기록):
시간(총·챕터별), 품질(`best_score`), `flagged` 수, 초안 재작성/재검수 횟수, GPU VRAM·util.

> ⚠️ **품질 비교의 한계:** 두 엔진은 검수 함수 `do_review`를 **공유**한다. 따라서 `best_score`는
> "같은 채점자가 매긴 자기 점수"라 엔진 간 독립적 품질 신호가 못 된다. 시간·자원은 의미 있으나,
> 품질 우열은 아래 보강 분석이 필요하다.

### 보강 분석 (계획) — B → A → C
* **B. 산출물 유사도** (`spikes/compare_similarity.py`): 두 엔진이 같은 챕터를 얼마나 비슷하게
  썼는지(difflib + 토큰 Jaccard). 단계 로직을 공유하므로 결과가 거의 같을 수 있고, 그렇다면
  품질 논쟁 없이 **속도·코드 단순성·API 지원으로** 결정이 환원된다.
* **A. 블라인드 LLM 페어와이즈 심사:** 중립 심사자에게 같은 챕터 A/B(라벨 숨김)를 주고
  우열 판정 → 자기 점수가 아닌 독립적 품질 신호.
* **C. 결정 메모:** 시간·GPU·품질 + 정성 요인(코드량, API deprecation, 채택 방향, `adk web`/트레이싱
  호환)을 종합해 "무엇을 남기고 무엇을 지울지" 최종 권고.

---

## 5. 핵심 설정값 (`core/config.py`)

| 상수 | 값 | 의미 |
| --- | --- | --- |
| MODEL | gemma4:31b | 생성 모델(ollama) |
| LLM_NUM_CTX | 32768 | 컨텍스트 길이 |
| LLM_KEEP_ALIVE | 30m | 모델 언로드 방지(런너 레이스 차단) |
| QUALITY_GATE | 80 | 위반 0 + 이 점수 이상이면 통과 |
| TARGET_SCORE | 90 | 이 점수면 더 안 끌어올림 |
| MIN_CHARS | 500 | 본문 최소 길이 가드(빈/잘린 챕터 감지 전용, 품질은 reviewer 담당) |
| WRITE_MAX / PASS_MAX | 3 / 3 | 초안 재작성 / 재수정 상한 |

---

## 6. 남은 일

* **엔진 확정:** `agent` vs `graph` 비교(§4) 후 한쪽으로 통일 → 다른 엔진과 `--engine` 분기 삭제.
* **죽은 파일 정리:** `agent/schemas.py`·`trace.py`·`prompt_blocks.py` 삭제(common.py로 흡수됨).
* **자원 충돌 주의:** 같은 ollama·같은 모델을 동시에 두드리면 충돌 → 생성은 한 번에 하나만.
* 생성 견고성(호출 timeout+retry, 챕터 flagged+continue, `--resume`)은 별도 TODO.
* 관측 docker 권한 이슈 정리.

---

## 7. 확장 방향 — 코드 오케스트레이션 → LLM 오케스트레이션

지금은 흐름을 **코드**가 쥐고 있다(§3.6). 다음 실험은 **흐름의 일부를 LLM 에게 위임**해보는 것이다.
즉 "어떤 단계를 다음에 할지·몇 번 반복할지"를 코드가 아니라 **LLM 이 판단**하게 한다.

LLM 오케스트레이션으로 해볼 것 (간단히):

* **Coordinator/라우팅 위임:** 상위 `LlmAgent` 가 sub_agents 를 두고 `transfer_to_agent` 로
  다음 단계를 LLM 이 선택. 예: "이 초안은 사실오류 위주 → reviser 말고 fact-checker 로 보내".
* **에이전트를 도구로(AgentTool):** write/review/revise 를 도구로 노출하고, 상위 LlmAgent 가
  **호출 순서·반복 횟수를 스스로** 결정(고정 LoopAgent 대신).
* **LLM 게이트:** 결정론 `gate_decision` 대신(또는 병행) LLM judge 가 "재수정/수용"을 판단 →
  더 유연하지만 비결정적.
* **동적 플래너(plan-and-execute):** Design 을 정적 생성이 아니라, 챕터별로 LLM 이 전략을 세우고
  필요한 도구(grounding 조회·검색 등)를 호출하며 진행.
* **멀티 검수자 토론:** 여러 reviewer 에이전트가 서로 비평·합의(LLM 간 상호작용)로 품질 판정.

트레이드오프: **코드 오케스트레이션**(결정론·재현·저비용·디버깅 쉬움) ↔
**LLM 오케스트레이션**(유연·창발적·맥락 적응 / 비결정·비용↑·디버깅 난이도↑).
→ 현실적 다음 수는 **하이브리드**: 뼈대(챕터 루프·품질 게이트)는 코드로 두고,
**국소 판단만 LLM** 에게 맡기는 형태(예: 게이트·라우팅만 LLM judge). (하이브리드는 현재 보류·기록만)
</content>

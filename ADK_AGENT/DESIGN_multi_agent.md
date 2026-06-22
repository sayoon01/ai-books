# 멀티 에이전트 전환 설계 (ADK_AGENT)

> 결정(2026-06-22): **코드 오케스트레이션 멀티 에이전트(아래 §A)** 로 간다.
> **하이브리드(§C)** 는 지금 안 하지만 "다음에 해볼 수도" 있어 함께 기록해 둔다.
> 현재 그래프 엔진은 **지우지 않고** `--engine` 으로 병행 → 검증 후 전환.

---

## 0. Context — 왜 / 무엇을

현재는 신 그래프 `Workflow`(엣지/라우팅 직접)로 챕터 파이프라인을 돌린다:
`START → write → length_guard → {rewrite:write, ok:review} → gate → {revise, done}`.
잘 동작하지만 ① 커스텀 그래프라 ADK 표준 예제와 결이 다르고 ② 역할(작성/검수/수정)이
노드 함수로만 존재해 "에이전트 협업" 형태가 약하다.

목표: write/review/revise/design 을 **각각 독립 LLM 에이전트(역할)** 로 만들고,
순서는 **코드(ADK 표준 SequentialAgent/LoopAgent)** 가 결정한다. 품질 게이트·keep-best·
grounding 은 **그대로 보존**(형태만 그래프→표준 에이전트로 바뀜).

> ⚠️ 솔직한 평가: §A 는 사실상 **현재 그래프를 ADK 표준 에이전트로 다시 표현**하는 것에 가깝다.
> 순(純)이득은 "표준 API·역할 분리·`adk web` 호환"이고, 흐름·품질 보장은 지금과 동등하다.
> 그러니 "대단한 신기능"이 아니라 **구조 정돈 + 표준화**로 기대치를 잡는 게 맞다.

---

## A. 채택안 — 코드 오케스트레이션 멀티 에이전트

### A-1. 역할 에이전트 (4개)

| 에이전트 | 형태 | 하는 일 | 현재 코드 재사용 |
|----------|------|---------|------------------|
| `design_agent` | 1회·구조화 | DesignPlan(목차+write_brief+grounding_digest) 생성 | `agent/design.py`(call_parsed + DESIGN_SYS) |
| `writer_agent` | `LlmAgent` | 챕터 초안(자유 마크다운) 작성, `output_key="draft"` | `agent/write.py`(WRITE_OUTPUT_POLICY + write_brief) |
| `reviewer_agent` | 구조화 | `ReviewResult`(점수·issues·unverified) 생성 → state["review"] | `agent/review.py`(call_structured + REVIEW_SYSTEM) |
| `reviser_agent` | `LlmAgent` | review 반영해 draft 수정, `output_key="draft"` | `agent/revise.py`(REVISE_SYSTEM) |

- design 은 책당 1회·구조화 출력이라 **에이전트 객체로 만들 필요 없이 함수 호출 유지**가 깔끔하다
  (LlmAgent 로 감싸도 되지만 이득 적음). writer/reviser 는 자유 텍스트라 `LlmAgent` 가 자연스럽다.
- reviewer 는 구조화 출력 신뢰도 때문에 현재 `call_structured`(ollama format=)를 쓴다. 그대로 둔다.
  (LlmAgent(output_schema=ReviewResult) 로 바꿀 수도 있으나 로컬모델에서 깨질 위험 → 보류.)

### A-2. 오케스트레이션 (코드가 순서 결정)

전체 = **design 1회 → (파이썬) 챕터 for-루프 → 챕터마다 아래 합성 에이전트 실행**.

챕터 1개 처리 = ADK 표준 에이전트 합성:
```
SequentialAgent(name="chapter", sub_agents=[
    writer_agent,                       # 초안 1회
    LoopAgent(name="refine",
        sub_agents=[reviewer_agent, gate_agent, reviser_agent],
        max_iterations=PASS_MAX),       # 검수→(통과면 탈출)→수정 반복
])
```
- `gate_agent`: reviewer 결과를 읽어 **통과 판정 시 `EventActions(escalate=True)`** 를 내보내는
  작은 커스텀 BaseAgent(또는 reviewer 의 `after_agent_callback`).
  - 통과 = `score >= QUALITY_GATE` 且 위반 0. → escalate → LoopAgent 즉시 종료(=done).
  - 미통과 & 시도 < PASS_MAX → escalate 안 함 → reviser 실행 후 다음 루프.
  - PASS_MAX 소진 → escalate(수용) + state["flagged"]=True.
- writer 초안은 루프 밖 1회. 길이 가드(MIN_CHARS 미만 재작성)는 writer 의
  `after_agent_callback` 으로(현재 length_guard 로직 이식) 또는 writer 를 작은 LoopAgent 로.

> 핵심: "그만 고칠까/더 고칠까" 판단은 **gate_agent(코드)** 가 한다 = 결정적. (이게 §C와의 차이)

#### A-2.1 스파이크 검증됨 (2026-06-22, `spikes/spike_loop_escalate.py`, LLM 없이)
- ✅ 커스텀 `BaseAgent` 가 `EventActions(escalate=True)` → `LoopAgent` **조기 종료**(2회만에 멈춤, max 10 안 감).
- ✅ 조건 미달이면 **max_iterations 에서 안전 종료**.
- ✅ 자식 간 state 공유: 한 자식이 쓴 값을 다음 자식이 읽음.
- ✅ `SequentialAgent[LoopAgent[...]]` 합성 동작.
- ⚠️ **구현 필수 주의**: 커스텀 에이전트의 state 변경은 **`EventActions(state_delta={...})` 로 내보내야 영속**된다.
  `ctx.session.state[...]` **직접 대입은 실행 중엔 보이지만(다음 자식은 읽음) 최종 세션엔 안 남는다.**
  → gate_agent 의 score/passed/flagged, keep-best 의 best_draft/best_score 는 전부 state_delta 로 낼 것.
- 커스텀 BaseAgent 골격:
  ```python
  class Gate(BaseAgent):
      async def _run_async_impl(self, ctx):
          passed = ctx.session.state.get("review",{}).get("score",0) >= QUALITY_GATE
          yield Event(invocation_id=ctx.invocation_id, author=self.name,
                      actions=EventActions(escalate=passed, state_delta={"passed": passed}))
  ```

### A-3. keep-best (현 동작 보존)

현재는 패스마다 최고 점수 draft 를 `best_draft` 로 들고, 최종에 그걸 채택한다.
멀티 에이전트에서도 동일하게 **gate_agent 가 매 검수 후 best 갱신**(state["best_draft"], "best_score").
LoopAgent 종료 후 드라이버가 `best_draft or draft` 를 최종으로 저장.

### A-4. 드라이버(파이썬) — 얇게 유지

```
load toc → design_agent(1회, design.json 캐시)
for ch in chapters:
    run chapter SequentialAgent (세션 state 에 ch/grounding/write_brief 주입)
    final = state.best_draft or state.draft
    save md + logs   (현 pipeline 저장 로직 재사용)
finalize: PDF + meta.json + push   (현 publish/ 재사용)
```
- 트레이싱(Phoenix/Langfuse), config.py, output 구조는 **그대로** 붙는다(이미 분리돼 있음).

### A-5. 재사용 vs 재작성

| 재사용(거의 그대로) | 재작성/이동 |
|---------------------|-------------|
| schemas.py, core/llm.py, core/config.py | `agent/graph.py` → **제거 또는 --engine 으로 보존** |
| publish/*, core/tracing.py, 프롬프트들 | `length_guard`/`gate` FunctionNode → callback/gate_agent 로 이식 |
| design.py(설계 1회) | `pipeline.py` → design 호출 + 챕터 루프 + 합성 에이전트 실행으로 조정 |
| grounding(아래 §B) | write/review/revise 노드 빌더 → 역할 에이전트 정의로 재배치 |

### A-6. 이행 단계(안전)

1. **§B grounding 정리**(아래) — 독립·안전, 먼저.
2. **스파이크**: LoopAgent + escalate(gate_agent) 가 gemma 로 의도대로 도는지 1챕터 검증.
3. 역할 에이전트 + 합성 구성, **현 그래프는 `--engine graph|agent` 로 병행**.
4. 1권 생성해 현 그래프와 품질·시간·토큰 비교.
5. 만족 시 기본 엔진 전환(그래프는 한동안 보존).

---

## B. 준비 리팩터 — grounding 한 곳으로 (오케스트레이션 무관, 먼저 해도 됨)

grounding 은 design(생성)·write·review·revise(소비)·검증을 가로지른다. 지금 조각이 흩어져 있음:

| 함수 | 현재 위치 | → 목표 |
|------|-----------|--------|
| `read_source()` | core/source_reader.py | **core/grounding.py** |
| `unverified_numbers()` | core/source_reader.py | core/grounding.py |
| `ground_block()` | agent/prompts.py (← 따로 떨어짐) | core/grounding.py |

→ `core/source_reader.py` 를 **`core/grounding.py` 로 개명**하고 `ground_block` 을 그리로 이동.
(원래 generator의 `grounding.py` 에서 온 코드라 이름 족보도 맞다.)

> 이름 주의: **`book_tools.py`(ADK tool 의미)로 부르지 않는다** — 이 함수들은 LLM 이 호출하는
> 도구가 아니라 코드가 부르는 헬퍼다. 훗날 `fetch_source` 처럼 **LLM 이 직접 호출**하게 되면
> 그때 진짜 tool 로 승격해 tools 모듈로 옮긴다.

영향: import 경로 변경(design/write/review/revise/pipeline). 동작 변화 없음.

---

## C. 미래 옵션(보류) — 하이브리드: 챕터 안쪽 루프를 LLM 이 판단

§A 와 **딱 한 군데만 다르다**: "이 챕터 충분한가, 더 고칠까/그만할까"를 **누가 결정**하나.

```
            바깥(챕터 목록)     안쪽(write→review→revise 반복)
§A 코드결정:   코드               코드 gate_agent (score<게이트 & 시도<N 이면 revise)
§C 하이브리드:  코드               LLM 코디네이터 (review 읽고 "더 고쳐/그만" 스스로 판단)
```

- §C 는 챕터 안쪽 반복을 **LLM 코디네이터 에이전트**가 주도(`reviser`/`reviewer` 를 AgentTool 로
  두거나 sub_agents 위임). gate_agent(코드 if문) 자리를 LLM 판단이 대체.
- **장점**: 구조화 점수만으론 못 잡는 미묘한 품질을 LLM 이 종합 판단해 루프를 조절.
- **단점/리스크**:
  - 로컬 gemma 의 다단계 위임 신뢰도 → 무한 revise / 조기 종료 / 호출 누락 위험.
  - 토큰↑(코디네이터 추론), 예측가능성↓.
- **언제 다시 볼까**: ① 더 똑똑한(툴콜 강한) 오케스트레이터 모델을 쓸 수 있을 때,
  ② "80점 게이트로는 부족, 사람 같은 합본 판단이 필요"가 실제 문제로 드러날 때.
- **전환 비용**: §A 가 돼 있으면 작다 — gate_agent(코드)를 LLM 코디네이터로 교체하고
  inner 루프만 위임 구조로 바꾸면 됨. 바깥 루프·역할 에이전트·드라이버·품질 도구는 공유.

### 참고: ③ 멀티 에이전트의 두 갈래(개념 정리)
- **3a AgentTool**: lead LLM 이 design/writer/reviewer 를 *도구처럼* 호출(LLM 결정). = §C 계열.
- **3b 워크플로 에이전트**: SequentialAgent/LoopAgent 가 코드로 조립(코드 결정). = **§A 채택안**.

---

## 부록. 결정 요약
- 채택: **§A** (코드 오케스트레이션 멀티 에이전트, 3b).
- 먼저: **§B** grounding → `core/grounding.py`.
- 병행: 현 그래프 엔진 `--engine` 으로 유지하며 비교 후 전환.
- 보류: **§C** 하이브리드(LLM 안쪽 루프) — 위 조건 충족 시 재검토.
- 변하지 않음: 품질 게이트(80)·keep-best·grounding·트레이싱·config·output 구조.

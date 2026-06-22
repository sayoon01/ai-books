# Google ADK 이해하기 (Agent Development Kit)

> 이 문서는 ADK를 **처음 보는 사람도 큰 그림을 잡도록** 쓴 개념 + 패턴 설명서입니다.
> 특정 코드에 매이지 않고 ADK가 무엇이고, 어떤 빌딩블록이 있고, 순차·병렬·루프·커스텀 에이전트를
> 각각 어떻게 만드는지를 예시로 보여줍니다. (이 레포 `ADK_AGENT/`는 맨 끝에 "실제 사례"로만 언급)

---

## 1. ADK가 뭔가

**ADK (Agent Development Kit)** 는 구글이 만든 **LLM 에이전트 오케스트레이션 프레임워크**입니다.
"LLM 한 번 호출"이 아니라, **여러 에이전트·도구·제어 흐름을 엮어서 하나의 워크플로**로 돌리는 게 목적입니다.

- 패키지: `pip install google-adk` → 임포트는 `import google.adk`
- 모델: 기본은 **Gemini**(google.genai), 하지만 **LiteLlm** 어댑터로 OpenAI·Anthropic·**ollama(로컬)** 등 거의 모든 모델 연결 가능
- 언어: Python (자바 버전도 있으나 여기선 Python 기준)
- 함께 오는 것: 세션/상태 관리, 도구(tool) 시스템, 이벤트 스트림, 실행기(Runner), 개발용 웹 UI(`adk web`)

### 한 문장 요약
> "에이전트(LLM) + 도구(함수) + 제어흐름(순차/병렬/루프/그래프)을 조립해서, 상태를 공유하며 돌아가는 파이프라인을 만드는 키트."

### 언제 쓰나
- 단계가 여러 개인 작업: *조사 → 초안 → 검수 → 수정* 같은 파이프라인
- 역할 분담: "기획 에이전트", "작성 에이전트", "검수 에이전트"를 나눠 협업
- 도구 사용: 검색·DB조회·계산을 LLM이 스스로 호출
- 품질 루프: 점수가 기준 넘을 때까지 반복 개선

---

## 2. 핵심 빌딩블록

| 블록 | 역할 |
|------|------|
| **LlmAgent** (`Agent`) | LLM 한 명. instruction(지시문) + model + 선택적 tools. 가장 기본 단위 |
| **도구(Tool)** | 에이전트가 호출하는 파이썬 함수 / 다른 에이전트 / 내장 검색 등 |
| **워크플로 에이전트** | `SequentialAgent`, `ParallelAgent`, `LoopAgent` — 자식 에이전트들을 정해진 흐름으로 실행 |
| **세션 / State** | 에이전트들이 공유하는 메모리(`dict`). `output_key`로 쓰고 `{key}`로 읽음 |
| **Runner** | 에이전트를 실제로 돌리는 실행기 (`InMemoryRunner` 등) |
| **Event** | 실행 중 흘러나오는 단위(모델 응답, 도구 호출, 상태변경 등) |

### 2.1 가장 작은 에이전트
```python
from google.adk.agents import Agent   # Agent == LlmAgent 별칭

agent = Agent(
    name="greeter",
    model="gemini-2.0-flash",
    description="인사하는 에이전트",          # 다른 에이전트가 위임 판단할 때 씀
    instruction="너는 친절한 안내원이다. 사용자에게 한국어로 인사해라.",
)
```

### 2.2 실행하기 (Runner + 세션)
ADK 에이전트는 직접 부르지 않고 **Runner**로 돌립니다. 비동기 스트림(`run_async`)이 기본입니다.

```python
import asyncio
from google.adk.runners import InMemoryRunner
from google.genai import types

async def main():
    runner = InMemoryRunner(agent=agent, app_name="demo")
    session = await runner.session_service.create_session(
        app_name="demo", user_id="u1", state={})        # state = 공유 메모리 초기값

    msg = types.Content(role="user", parts=[types.Part(text="안녕")])
    async for event in runner.run_async(user_id="u1", session_id=session.id, new_message=msg):
        if event.content:                                # 모델/도구가 뱉는 이벤트들
            print(event.content)

asyncio.run(main())
```

### 2.3 State로 에이전트끼리 데이터 넘기기
이게 ADK 협업의 핵심입니다.
- `output_key="x"` → 그 에이전트의 최종 출력이 `state["x"]`에 저장됨
- 다음 에이전트 instruction에서 `{x}` 로 그 값을 꽂아 읽음

```python
writer  = Agent(name="writer",  model="gemini-2.0-flash",
                instruction="주제에 대한 초안을 써라.",
                output_key="draft")                       # 결과 → state["draft"]

editor  = Agent(name="editor",  model="gemini-2.0-flash",
                instruction="다음 초안을 더 매끄럽게 다듬어라:\n\n{draft}")  # state["draft"] 읽음
```

---

## 3. 도구(Tool) — 에이전트에게 능력 주기

LLM이 "검색해", "계산해", "DB 조회해"를 **스스로 호출**하게 하는 장치. 그냥 **파이썬 함수**를 넘기면 됩니다.
함수의 **독스트링과 타입힌트가 곧 LLM이 보는 사용설명서**이므로 잘 써야 합니다.

```python
def get_weather(city: str) -> dict:
    """도시의 현재 날씨를 반환한다.

    Args:
        city: 도시 이름 (예: "서울")
    Returns:
        status와 report를 담은 dict
    """
    return {"status": "ok", "report": f"{city}은 맑고 23도"}

agent = Agent(
    name="weather_bot",
    model="gemini-2.0-flash",
    instruction="사용자가 날씨를 물으면 get_weather 도구를 써서 답해라.",
    tools=[get_weather],          # ← 함수를 그냥 넘김
)
```

도구의 종류:
- **함수 도구**: 위처럼 일반 함수 (가장 흔함)
- **AgentTool**: 다른 에이전트를 도구처럼 호출 (전문가 에이전트 위임)
- **내장 도구**: `google_search`, 코드 실행기 등 ADK 제공
- **MCP / 외부 도구**: MCP 서버, LangChain 도구 등 연동

---

## 4. 제어 흐름: 순차 · 병렬 · 루프

핵심 질문 "**순차/병렬/루프 에이전트를 어떻게 하냐**"의 답입니다.
이들은 전부 **워크플로 에이전트** — 자식 에이전트(`sub_agents`)를 정해진 방식으로 굴립니다.
이건 LLM이 판단하는 게 아니라 **코드로 결정되는(deterministic) 흐름**입니다.

### 4.1 SequentialAgent — 순차 (A → B → C)
자식들을 **순서대로** 실행. 앞 단계 결과를 `output_key`로 넘겨 뒤가 받음.

```python
from google.adk.agents import SequentialAgent, Agent

step1 = Agent(name="outline", model="gemini-2.0-flash",
              instruction="주제의 개요를 잡아라.", output_key="outline")
step2 = Agent(name="draft",   model="gemini-2.0-flash",
              instruction="이 개요로 글을 써라:\n{outline}", output_key="draft")
step3 = Agent(name="polish",  model="gemini-2.0-flash",
              instruction="이 글을 다듬어라:\n{draft}", output_key="final")

pipeline = SequentialAgent(name="writer_pipeline",
                           sub_agents=[step1, step2, step3])
# 실행하면 outline → draft → polish 순으로, state를 이어받으며 진행
```
**용도:** 단계가 명확히 줄지어 있는 작업(개요→초안→교정).

### 4.2 ParallelAgent — 병렬 (A ∥ B ∥ C 동시)
자식들을 **동시에** 실행. 서로 독립적인 작업을 한꺼번에 돌려 시간을 줄임.
각자 다른 `output_key`에 결과를 쌓고, 보통 뒤에 **합치는(synthesize) 단계**를 둡니다.

```python
from google.adk.agents import ParallelAgent, SequentialAgent, Agent

# 세 가지를 동시에 조사
research_a = Agent(name="r_tech",   model="gemini-2.0-flash",
                   instruction="기술 동향을 조사해라.", output_key="tech")
research_b = Agent(name="r_market", model="gemini-2.0-flash",
                   instruction="시장 동향을 조사해라.", output_key="market")
research_c = Agent(name="r_risk",   model="gemini-2.0-flash",
                   instruction="리스크를 조사해라.",   output_key="risk")

gather = ParallelAgent(name="research",
                       sub_agents=[research_a, research_b, research_c])

# 동시에 모은 뒤 합치기
synth = Agent(name="synth", model="gemini-2.0-flash",
              instruction="세 조사 결과를 종합 보고서로 합쳐라:\n"
                          "기술:{tech}\n시장:{market}\n리스크:{risk}",
              output_key="report")

flow = SequentialAgent(name="parallel_then_merge",
                       sub_agents=[gather, synth])   # (병렬) → (합치기)
```
**주의:** 병렬 자식들은 서로의 결과를 못 봅니다(동시에 도니까). 합치기는 별도 단계에서.
**용도:** 독립적인 여러 갈래를 동시에 — 다관점 조사, 여러 후보 동시 생성.

### 4.3 LoopAgent — 루프 (조건/횟수까지 반복)
자식(들)을 **반복** 실행. 멈추는 방법 두 가지:
1. `max_iterations=N` — 최대 N번 돌고 종료
2. 자식이 **escalate 신호**를 보내면 즉시 종료 (예: 검수자가 "합격" 판정)

```python
from google.adk.agents import LoopAgent, Agent

improver = Agent(name="improver", model="gemini-2.0-flash",
                 instruction="이전 초안을 더 좋게 고쳐라:\n{draft}",
                 output_key="draft")            # 같은 키를 덮어쓰며 점점 개선

# escalate(조기종료)는 보통 도구나 콜백에서 EventActions(escalate=True)로 신호
reviewer = Agent(name="reviewer", model="gemini-2.0-flash",
                 instruction="초안이 충분히 좋으면 합격 처리해라:\n{draft}")

refine_loop = LoopAgent(
    name="refine",
    sub_agents=[improver, reviewer],
    max_iterations=5,        # 5번 안에 합격 못하면 그냥 종료
)
```
조기 종료 신호는 보통 콜백/도구에서:
```python
from google.adk.events import EventActions
# 도구나 after_model_callback 안에서:
#   return EventActions(escalate=True)   → 루프 즉시 탈출
```
**용도:** 품질이 기준에 닿을 때까지 반복 개선, 수렴할 때까지 재시도.

### 4.4 조합 — 워크플로는 중첩된다
워크플로 에이전트도 결국 에이전트라, **서로 자식으로 품을 수 있습니다.**
```
SequentialAgent(
  ├─ ParallelAgent(조사A, 조사B, 조사C)   # 동시에 조사
  ├─ Agent(합치기)
  └─ LoopAgent(작성 → 검수, 합격까지)      # 반복 개선
)
```
즉 "병렬로 조사 → 종합 → 루프로 다듬기" 같은 복합 파이프라인이 자연스럽게 나옵니다.

---

## 5. 멀티 에이전트 위임 (LLM이 흐름을 정하는 방식)

위 4번은 **코드가 흐름을 정함**(deterministic). 반대로 **LLM이 판단해서** 다른 에이전트에게
넘기게 할 수도 있습니다 — `sub_agents`로 묶어두면 부모가 상황에 맞는 자식에게 **transfer**합니다.

```python
billing = Agent(name="billing", description="결제·환불 문의 처리", ...)
tech    = Agent(name="tech",    description="기술 지원 문의 처리", ...)

coordinator = Agent(
    name="coordinator",
    model="gemini-2.0-flash",
    instruction="사용자 문의를 보고 적절한 담당 에이전트에게 넘겨라.",
    sub_agents=[billing, tech],     # description을 보고 LLM이 알아서 위임
)
```
- **워크플로 에이전트(4번)** = 흐름이 고정적·예측가능해야 할 때
- **LLM 위임(5번)** = 분기를 모델 판단에 맡기고 싶을 때 (유연하지만 덜 예측가능)

---

## 6. 모델 연결 (Gemini 말고 다른 것 쓰기)

기본은 Gemini지만, **LiteLlm**으로 다른 공급자/로컬 모델을 붙입니다.

```python
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# 로컬 ollama 모델
local = Agent(name="local", model=LiteLlm(model="ollama_chat/llama3"),
              instruction="...")

# OpenAI / Anthropic 등도 LiteLlm로 (해당 API 키 환경변수 필요)
# LiteLlm(model="openai/gpt-4o")
# LiteLlm(model="anthropic/claude-3-5-sonnet")
```

---

## 7. 실행·디버깅 도구 (CLI / Web UI)

ADK는 개발 편의 도구를 제공합니다 (에이전트를 `agent.py`에 정의해두면 됨):

| 명령 | 용도 |
|------|------|
| `adk web` | 브라우저 채팅 UI로 에이전트 테스트 + 실행 단계 시각화 |
| `adk run <앱>` | 터미널에서 대화형 실행 |
| `adk api_server` | REST API 서버로 띄우기 |

State·이벤트·도구호출을 눈으로 보며 디버깅할 수 있어 처음 배울 때 특히 유용합니다.

---

## 8. 두 가지 API 세대 (중요)

ADK에는 흐름을 짜는 방식이 **두 갈래**가 있습니다. 버전에 따라 가용성이 다릅니다.

### (A) 클래식 워크플로 에이전트 — 4번에서 설명한 것
`SequentialAgent / ParallelAgent / LoopAgent`. 직관적이고 문서·예제가 가장 많음.
**대부분의 경우 이걸로 충분합니다.**

### (B) 신 그래프 Workflow API (`google.adk.workflow`)
`Workflow / FunctionNode / JoinNode / START` 로 **노드와 엣지(분기)를 직접 그리는** 방식.
순차·병렬·루프를 *그래프의 라우팅으로* 표현 → 조건 분기, 되돌아가는 루프, 복잡한 흐름에 강함.

```python
from google.adk.workflow import Workflow, FunctionNode, START

def guard_fn(ctx):
    # ctx.state로 상태 접근, ctx.route로 다음 분기 결정
    ctx.route = "ok" if len(ctx.state.get("draft", "")) > 500 else "rewrite"

graph = Workflow(name="chapter", edges=[
    (START, write_node),
    (write_node, guard_node),
    (guard_node, {"rewrite": write_node, "ok": review_node}),  # dict = 조건 분기
    (review_node, gate_node),
    (gate_node, {"revise": revise_node, "done": finalize_node}),
    (revise_node, review_node),                                 # 되돌아가는 루프
])
```
- `FunctionNode` = 파이썬 함수 노드(가드/판정/라우팅)
- `JoinNode` = 병렬 분기들이 다시 합류하는 지점(fan-in)
- 분기는 엣지를 `{경로이름: 다음노드}` dict로 주고, 노드에서 `ctx.route`로 경로 선택

**언제 (B)?** 단순 직선/병렬/루프를 넘어 *조건부 재작성 루프, 동적 라우팅*이 필요할 때.
**언제 (A)?** 흐름이 단순하고 빨리 만들고 싶을 때.

---

## 9. 전체 그림 (정리)

```
        ┌─────────────────────────────────────────────┐
        │                   Runner                      │  ← 실행기
        │   ┌───────────── Session / State ──────────┐ │  ← 공유 메모리(dict)
        │   │                                          │ │
        │   │   워크플로(순차/병렬/루프/그래프)         │ │
        │   │     └─ LlmAgent ── tools(함수/검색/...) │ │  ← LLM + 능력
        │   │     └─ LlmAgent ── sub_agents(위임)     │ │
        │   └──────────────────────────────────────────┘ │
        └─────────────────────────────────────────────┘
                          │ run_async
                          ▼
                  Event 스트림(응답/도구호출/상태변경)
```

**배우는 순서 추천:**
1. `Agent` 하나 + Runner로 돌려보기 (2번)
2. 함수 도구 붙여보기 (3번)
3. `output_key`/`{key}`로 두 에이전트 연결 (2.3)
4. `SequentialAgent` → `ParallelAgent` → `LoopAgent` 순으로 흐름 만들기 (4번)
5. 필요해지면 그래프 `Workflow`로 (8-B)

---

## 부록. 이 레포(`ADK_AGENT/`)의 실제 사례

이 프로젝트는 **책 자동 생성기**로, 위 개념을 실제로 씁니다:
- 모델: `LiteLlm("ollama_chat/gemma4:31b")` (로컬 ollama) — 6번 방식
- 흐름: **신 그래프 Workflow API**(8-B)로 챕터 1개를 다음처럼 처리
  ```
  START → write → length_guard → {rewrite: write, ok: review}
  review → gate → {revise: revise, done: finalize}
  revise → review
  ```
  즉 *작성 → 길이 가드(짧으면 재작성 루프) → 검수 → 점수 게이트(미달이면 수정 루프) → 확정*.
- 책 전체 챕터 for문·파일 저장·PDF·푸시 같은 I/O는 ADK 밖(파이썬 드라이버 `pipeline.py`)에서 처리.

> 참고: 구식 `LoopAgent(max_iterations=N)`이 하던 "반복 상한"을, 이 레포는 그래프에서
> `write_count`/`pass_count` 카운터 + 조건 분기로 대체했습니다 (8-B가 더 세밀한 제어를 주기 때문).

참고 코드: `agent/graph.py`(그래프 조립), `agent/write.py`(LlmAgent 노드 + 가드), `core/llm.py`(모델 연결).

### 관측(트레이싱) 켜는 법
ADK는 LLM 호출·그래프 노드·도구 호출을 **OpenTelemetry span으로 자동 방출**합니다. 이 레포는 그걸
**Phoenix / Langfuse** 대시보드로 보내 챕터별 단계 타임라인·프롬프트/응답·토큰을 볼 수 있게 했습니다.
기본 자동 — env 에 설정된 백엔드로 알아서 전송(둘 다 설정 시 동시 전송). 끄려면 `--no-trace`.
```bash
docker-compose -f observability/docker-compose.yml up -d         # Phoenix (http://localhost:6006)
cp observability/.env.example observability/.env                 # 백엔드 엔드포인트/키 (자동 로드됨)
.venv/bin/python main.py --toc toc/mold-dx-auto.json --no-push   # 트레이싱 자동
```
구현: `core/tracing.py`(env 보고 TracerProvider+익스포터 fan-out 설치), `pipeline.py`(runner에
`AutoTracingPlugin` 부착 + 챕터 span + 종료 flush). 자세한 건 `observability/README.md`.
</content>
</invoke>

# ADK 기반 AI Book 생성기 재설계

작성일: 2026-06-19
대상: `generator/` (현 `book_writer.py`/`prompts.py`/`schemas.py`/`grounding.py`)를
Google ADK 기반 멀티 에이전트 구조로 옮기는 설계.

> 원칙: **Write → Review → Revise 역할은 유지**한다. 앞에 **DesignAgent**를 추가하고,
> 프롬프트·grounding을 **state 변수**로 다룬다. GitHub 자동 push·PDF는 그대로 유지한다.

---

## 0. 배경 — 왜 바꾸나

- 레퍼런스(Gemini+ADK)는 "링크/파일만 instruction에 주면" 모델이 알아서 읽는다.
  하지만 우리 모델은 **ollama gemma4:31b** → 파일/URL을 네이티브로 못 읽는다.
  따라서 "소스 읽는 코드"를 0으로는 못 만들고, **역할만 바꾼다**:
  파이프라인 전처리(grounding.py) → DesignAgent가 쓰는 **얇은 reader + 변수**.
- 사람이 책마다 특화 instruction을 쓰는 대신, **DesignAgent가 집필 프롬프트(write_brief)를
  자동 생성**해 변수로 넘긴다.

### 현실 제약 3가지 (설계를 좌우함)
1. **로컬 모델은 파일/URL 비네이티브** → 소스 추출(xlsx→텍스트)은 얇은 함수로 남긴다.
2. **ADK `output_schema` 사용 LlmAgent는 tool 사용 불가** → 구조화 단계는 ADK output_schema
   대신 기존 `call_structured`(ollama `format=` constrained decoding)를 쓴다(③).
3. **ADK 2.3.0에서 `SequentialAgent`/`LoopAgent`/`ParallelAgent` 전부 deprecated**
   ("use Workflow instead") → 챕터 파이프라인은 **그래프 기반 `google.adk.workflow.Workflow`**
   (Node/Edge/route)로 짠다. escalate 대신 `ctx.route`로 분기, 루프 상한은 state 카운터로 직접(⑤).
   ※ 아래 사실은 `spikes/s1·s2` + 추가 테스트로 검증됨(2026-06-19):
   - `LiteLlm(num_ctx=32768, keep_alive, repeat_penalty)` → ollama까지 전달(`ollama ps` CONTEXT 확인).
   - `LlmAgent`를 그래프 노드로 직접 사용 가능, `output_key`가 state에 기록.
   - route 자기참조 사이클로 루프 구성·종료 가능(조건부 엣지 1개 이상 필요).

---

## 1. 전체 구조

```
[파이썬] source 읽기(얇은 reader) ───────────────▶ state["source_text"]
[파이썬] design.json 있으면 로드, 없으면 생성       ▶ {chapters, write_brief, grounding_digest}
         design = call_structured(DesignPlan) → design.json 저장 (1회)
         └─ ◀───── 웹 UI가 design.json 읽기/수정 (목차·write 프롬프트 편집)
[파이썬] for ch in chapters:                       ← push / PDF 는 여기 (유지)
   └ chapter_graph = Workflow(edges=[              # google.adk.workflow.Workflow
        START → write(LlmAgent)
        write → length_guard(FunctionNode)         # 가드① (state 카운터)
        length_guard → {rewrite: write, ok: review}
        review(FunctionNode/call_structured) → gate(FunctionNode)
        gate → {revise: revise, done: finalize}    # escalate 대체 = route
        revise(LlmAgent) → review                   # 재검수 사이클
        finalize(FunctionNode, terminal)
     ])
   → 세션 state["draft"] 읽어 저장 · push_chapter · update_meta
[파이썬] build_pdf · push_pdf
```

핵심 분담:
- **ADK** = 챕터 1개의 LLM 파이프라인(그래프 Workflow: Node/Edge/route/state).
- **파이썬** = design 1회 호출, 챕터 for문, summaries 누적, 파일 저장, push, PDF (전부 I/O이므로 유지).
- design은 챕터당 반복이 아닌 **책당 1회**라 그래프로 감싸지 않고 파이썬에서 `call_structured` 직접 호출.

---

## 2. grounding.py의 분해

| 지금 grounding.py 안 | 재설계 후 |
|---|---|
| `_resolve_file/_url/_text` (소스→텍스트) | **얇은 reader 유지** — design 앞에서 1회 → `state["source_text"]` |
| 캐싱(`_cache_path`) | 유지(오프라인 재생성) |
| `unverified_numbers` (출력 수치 검증) | **유지, 위치 이동** → GateCheck 안에서 호출 (전처리 아님, 출력 검증) |
| `Grounding` payload 주입 ceremony | **제거** → state 변수 + DesignAgent가 digest로 정리 |

"읽기(dumb)"만 코드에 남고 "해석·요약·목차화(smart)"는 DesignAgent로 올린다.

### 입력 JSON 단순화
```jsonc
// before
"grounding": { "kind": "file", "path": "data/금형필드.xlsx" }
// after  (kind 추론, 없으면 모델 지식)
"source": "data/금형필드.xlsx"          // 파일경로 또는 URL
```
`chapters`는 지금처럼 **있으면 그대로, 없으면 Design이 생성**(현 `auto_outline` 분기 유지).

---

## 3. Step ① — DesignAgent + DesignPlan

DesignAgent = 현 `plan_outline`(Outline)을 확장. **입력 json(+source)을 읽고 세 가지 생성.**

```python
class ChapterSpec(BaseModel):
    number: int = Field(default=0)
    title: str
    description: str = Field(default="", description="이 챕터가 다루는 내용 한두 문장")

class DesignPlan(BaseModel):
    chapters: list[ChapterSpec] = Field(min_length=1, max_length=20,
        description="config에 chapters 없으면 생성, 있으면 정제해 그대로.")
    write_brief: str = Field(
        description="이 책 전용 집필 지시문. 톤·독자·구성 관례·소스 활용법을 한 덩어리로. "
                    "= Write agent에 그대로 넘길 프롬프트.")
    grounding_digest: str = Field(default="",
        description="source_text에서 집필에 필요한 핵심만 추린 텍스트. "
                    "Write에 {grounding} 변수로 주입. source 없으면 빈 값.")
```

세 필드:
- `chapters` → 목차+설명 json 완성 (지금 outline이 하던 일)
- `write_brief` → **신규.** config(독자·문체·writing_guidelines)를 읽고 집필 지시문 자동 생성
- `grounding_digest` → 12000자 raw 대신 Design이 추린 핵심 (write 프롬프트 경량화·정확도↑)

소스(파일/링크) 교체 시: 입력 json의 `source`만 바꾸면 reader→Design→digest가 다시 흘러
**write 코드는 한 줄도 안 바뀐다** = "변수 처리해서 링크/파일 바껴도 동작".

> **planner(UnitPlan) 흡수 결정:** 챕터별 본문 설계(thesis/steps)를 위한 별도 planner 노드는
> 두지 않는다. 챕터 단위 의도는 `ChapterSpec.description`이, 구성 관례(소제목 흐름·분량 배분 등)는
> `write_brief`가 담당한다. → 그래프에 planner 노드 없음, 챕터당 LLM 호출 1개 절약, 디버깅 단순.
> (필요해지면 ChapterSpec에 `outline` 필드를 더해 Design이 챕터별 steps까지 생성하도록 확장 가능.)

### 3-1. Design 산출물 = 편집 가능한 아티팩트 (웹 수정 대비)

Design 출력은 **메모리 state로만 흘리지 않고 `design.json` 파일로 떨군다.** 이유:
추후 **웹 UI에서 목차·집필 프롬프트를 직접 수정**한 뒤 그 값으로 본문을 생성하게 하기 위함.

```jsonc
// output/<slug>/design.json  — 웹이 읽고/쓰는 단일 편집 대상
{
  "chapters": [ { "number": 1, "title": "...", "description": "..." }, ... ],
  "write_brief": "이 책 전용 집필 지시문 ...",   // 웹에서 자유 편집(프롬프트)
  "grounding_digest": "소스 핵심 요약 ..."         // 보통 자동, 필요시 편집
}
```

**핵심 규칙 — "있으면 로드, 없으면 생성"** (현 `auto_outline` 분기와 동일 패턴):
```python
design_path = output_dir / "design.json"
if design_path.exists() and not force_redesign:
    design = json.loads(design_path.read_text())     # 웹/사람이 고친 값 존중 → 재생성 안 함
else:
    design = call_structured(DESIGN_SYS, design_user(state), DesignPlan, 0.3).model_dump()
    design_path.write_text(json.dumps(design, ensure_ascii=False, indent=2))
# 이후 chapters / write_brief / grounding_digest 를 state에 주입 → Write→Review→Revise
```

효과:
- **파이프라인 분리:** Design(생성) ↔ Write(소비)가 `design.json`을 경계로 끊겨, 웹은 이 파일 하나만
  읽고/쓰면 된다. 그래프·노드 코드는 **한 줄도 안 바뀐다**(변수 흐름: 파일→state→노드 그대로).
- **재실행 흐름:** `design.json` 수정 후 재생성 → 본문만 새로 씀(Design 스킵). `--redesign`으로 강제 재생성.
- **검증:** 로드한 `design.json`도 `DesignPlan(**data)`로 Pydantic 재검증해 웹 편집 실수(필드 누락 등)를 막는다.
- 향후 챕터 본문(`draft`)도 같은 패턴으로 파일↔웹 편집 대상이 될 수 있다(동일 "있으면 로드" 규칙).

---

## 4. 프롬프트 변수처리 (3층)

### Level 1 — ADK 네이티브 `{var}` 치환 (state에서)
```python
write = LlmAgent(name="write", model=GEMMA,
    instruction="{write_brief}\n\n[참고]\n{grounding}\n\n[챕터]\n{chapter}",
    output_key="draft")
```
`{grounding?}` 처럼 `?` 붙이면 없을 때 빈칸.

### Level 2 — 조건부 블록은 InstructionProvider 함수
현 `_ground()/_prev()`처럼 "있으면 블록"은 함수로:
```python
def write_instruction(ctx) -> str:
    s = ctx.state
    return "\n".join(filter(None, [
        s["write_brief"],
        _block("[참고 자료]", s.get("grounding")),
        _block("[이전 요약]", s.get("prev_summaries")),
        f"[이번 챕터]\n{s['chapter']}",
    ]))
write = LlmAgent(..., instruction=write_instruction, output_key="draft")
```
→ 현 조립 함수가 ADK provider로 옷만 갈아입음. (planner 흡수로 `[작성 설계]` 블록은 제거)

### Level 3 — 외부화 범위 (결정: write_brief만 변수화)
**결정:** review/revise/design의 SYSTEM 프롬프트는 **검수 기준 일관성을 위해 `prompts.py`에
정적 유지**한다. 책마다 바뀌는 집필 지시문(`write_brief`)만 Design이 **생성형 변수**로 만든다.
`prompts.yaml` 전면 외부화는 **하지 않는다**(필요해지면 나중에 분리).
튜너블 숫자(`quality_gate=80`, `target_score=90`, `min_chars=500`)는 코드 상수/설정으로 관리.

### 변수 카탈로그 (state)
| 변수 | 채우는 주체 | 쓰는 agent |
|---|---|---|
| `config` | 입력 json | design |
| `source_text` | reader 함수 | design |
| `write_brief` | **design 생성** | write |
| `grounding` | design(digest) | write, review, revise |
| `chapter` | for문(현재 챕터) | write, review, revise |
| `prev_summaries` | for문 누적 | write |
| `draft` | write→revise 덮어씀 | review, revise |
| `review` | review 생성 | revise |
| `write_count`/`pass_count` | 노드(루프 카운터) | length_guard, gate |
| `quality_gate`/`target_score`/`min_chars` | 설정 | review, 게이트 |

**결정: write_brief만 생성형(변수), review/revise SYSTEM은 정적 템플릿 유지**(검수 기준 일관성),
튜너블 숫자만 변수. (`plan` 변수는 planner 흡수로 제거)

---

## 5. Step ② — 챕터 파이프라인 (ADK 그래프 Workflow)

> ADK 2.3.0에서 Sequential/Loop가 deprecated → **그래프 `Workflow`로 재설계.**
> 노드 = 작업 단위, 엣지 = 흐름, `ctx.route` = 분기, 사이클 = 루프(상한은 state 카운터).
> escalate는 없다 → "끝"은 **터미널 노드(`finalize`)로 라우팅**해서 표현한다.

### 챕터 1개 = Workflow 그래프
```python
from google.adk.workflow import Workflow, FunctionNode, START
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

GEMMA = LiteLlm(model="ollama_chat/gemma4:31b",
                num_ctx=32768, repeat_penalty=1.2, keep_alive="30m")  # ← S1로 전달 검증됨

write  = LlmAgent(name="write",  model=GEMMA, instruction=write_instruction,  output_key="draft")
revise = LlmAgent(name="revise", model=GEMMA, instruction=revise_instruction, output_key="draft")
length_guard = FunctionNode(func=length_guard_fn, name="length_guard")
review       = FunctionNode(func=review_fn,       name="review")
gate         = FunctionNode(func=gate_fn,         name="gate")
finalize     = FunctionNode(func=finalize_fn,     name="finalize")   # 터미널(나가는 엣지 없음)

chapter_graph = Workflow(name="chapter", edges=[
    (START, write),
    (write, length_guard),
    (length_guard, {"rewrite": write, "ok": review}),   # 가드① 사이클
    (review, gate),
    (gate, {"revise": revise, "done": finalize}),        # 게이트 분기
    (revise, review),                                     # 재검수 사이클
])
```
두 사이클(`write↔length_guard`, `review→gate→revise→review`)은 각각 조건부 엣지를
1개 이상 포함하므로 그래프 규칙상 허용된다.

### 노드 함수 — state 읽고/쓰고 `ctx.route`로 분기

`FunctionNode`는 `ctx`를 주입받고, 나머지 파라미터는 state 키 이름으로 바인딩된다.
여기서는 단순하게 전부 `ctx.state`로 접근한다.

#### length_guard — 가드①(MIN_CHARS=500), max_iterations 대체(카운터)
```python
WRITE_MAX = 3
def length_guard_fn(ctx):
    s = ctx.state
    body = _strip_title_h1(s.get("draft", "")).strip()
    s["write_count"] = s.get("write_count", 0) + 1
    if len(body) >= s["min_chars"]:                # 500 이상 → 통과
        ctx.route = "ok"
    elif s["write_count"] < WRITE_MAX:             # 짧음 + 여유 → 재작성
        ctx.route = "rewrite"
    else:                                           # 끝까지 짧음 → 플래그하고 진행
        s["flagged"] = True
        ctx.route = "ok"
```
> `MIN_CHARS=500`은 **생성 실패(빈/잘린 챕터) 감지 전용 바닥선**.
> 3,000자(품질 목표)는 **reviewer가 담당** — 가드와 분리.
> 근거: 정상 챕터 최소 957자·대부분 3000~6000자, 실패는 0자 → 500이 깔끔히 분리.
> (배경: 금형 자동해석 v1에서 chapter 7이 본문 0자로 저장된 사건.)
> ADK LoopAgent의 `max_iterations`가 사라졌으므로 **`write_count` 카운터로 직접 상한**을 건다.

#### review — 구조화 출력(call_structured 래핑)
```python
def review_fn(ctx):
    s = ctx.state
    s["review"] = call_structured(
        REVIEW_SYS, review_user(s), ReviewResult, temperature=0.2).model_dump()
```

#### gate — 현 while 루프 판단 로직 이식 (escalate → route)
```python
PASS_MAX = 3
def gate_fn(ctx):
    s = ctx.state
    review = ReviewResult(**s["review"])
    bad = unverified_numbers(s["draft"], s.get("grounding","")) if s.get("grounding") else []
    if bad:
        review.unverified_numbers = sorted(set(review.unverified_numbers) | set(bad))
        s["review"] = review.model_dump()

    violations = [i for i in review.issues if i.type in VIOLATION_TYPES]
    weak = {k:v for k,v in review.quality.model_dump().items() if v < s["quality_gate"]}
    must_fix  = bool(violations or bad)
    want_lift = bool(weak) or review.score < s["target_score"] or review.needs_revision

    s["pass_count"] = s.get("pass_count", 0) + 1
    stop = False
    if not must_fix and not want_lift:
        stop = True                                   # 완료
    elif not must_fix and review.score <= s.get("last_score", -1):
        stop = True                                   # 천장(점수 정체) → 수용
    elif s["pass_count"] >= PASS_MAX:
        stop = True                                   # 재수정 상한 (구 max_iterations 대체)
    s["last_score"] = review.score

    ctx.route = "done" if stop else "revise"
```
"위반은 0까지 고치고, 품질은 오르는 한 끌어올리고, 천장/상한이면 수용" 정책 그대로 보존.
- 깨끗/천장/상한 → `route="done"` → finalize(종료, revise 안 거침)
- 문제 → `route="revise"` → revise → 다시 review

#### finalize — 터미널 노드(결과 확정)
```python
def finalize_fn(ctx):
    # 필요한 정리만. 실제 draft는 세션 state에서 파이썬이 읽어 저장한다.
    return ctx.state.get("draft", "")
```

### write/revise instruction — InstructionProvider(state→프롬프트)
`§4 Level 2`의 조건부 블록 조립 함수를 그대로 ADK instruction provider로 쓴다(LlmAgent가
노드로 동작하고 `output_key="draft"`로 state에 기록되는 것은 검증됨).

### 파이썬 드라이버 (for문 + I/O 유지)
```python
from google.adk.runners import InMemoryRunner
from google.genai import types

runner = InMemoryRunner(agent=chapter_graph, app_name="book")
base = {"config": config, "write_brief": design["write_brief"],
        "grounding": design["grounding_digest"], "min_chars": 500,
        "quality_gate": 80, "target_score": 90}
GO = types.Content(role="user", parts=[types.Part(text="go")])

summaries = []
for i, ch in enumerate(chapters, 1):
    sess = await runner.session_service.create_session(
        app_name="book", user_id="u",
        state={**base, "chapter": ch, "prev_summaries": summaries[:],
               "last_score": -1, "write_count": 0, "pass_count": 0})
    async for _ in runner.run_async(user_id="u", session_id=sess.id, new_message=GO):
        pass
    st = (await runner.session_service.get_session(
            app_name="book", user_id="u", session_id=sess.id)).state
    final = st["draft"]
    if st.get("flagged"): ...   # 끝까지 짧았던 챕터 로깅

    content = f"# {num}. {ctitle}\n\n{_normalize_math(_strip_title_h1(final))}"
    (output_dir / fname).write_text(content)          # 유지
    push_chapter(...); update_meta(...)               # 유지
    summaries.append(f"{num}. {ctitle}: {ch.get('description','')}")

build_pdf(...); push_pdf(...)                         # 유지
```
> 그래프는 비동기(`run_async`)라 드라이버 for문은 `async def`로 감싼다(`asyncio.run`).
> 동기 ollama 호출(`call_structured`/`_call`)이 노드 안에서 이벤트 루프를 잠깐 블록하지만,
> 단일 챕터 직렬 생성이라 실용상 문제 없음(필요시 `asyncio.to_thread`로 분리 가능).

---

## 6. Step ③ — 구조화 출력(JSON) 신뢰성

### 문제
현 코드의 JSON 안정성은 `call_structured`의 **constrained decoding**:
```python
ollama.chat(format=schema.model_json_schema(), ...)
```
ADK `output_schema`를 LiteLlm+ollama로 쓰면 이 `format=` 전달이 **보장되지 않음**
(JSON 모드로만 떨어지면 스키마 위반 가능). → 검증 전엔 못 믿는다.

### 해결: 하이브리드
| 단계 | 출력 | 노드 종류 | 이유 |
|---|---|---|---|
| **write / revise** | 자유 마크다운 | ADK `LlmAgent`(그래프 노드) + LiteLlm | JSON 아님 → 깨질 게 없음 |
| **review** | 엄격 JSON | `FunctionNode`(call_structured 래핑) | constrained decoding+재시도 보존 |
| **design** | 엄격 JSON | 파이썬에서 `call_structured` 직접(책당 1회) | 그래프 불필요 |

구 설계의 `StructuredAgent`(BaseAgent 서브클래스)는 **더 이상 필요 없다** — 그래프에서는
일반 함수를 `FunctionNode`로 감싸면 끝(BaseAgent 보일러플레이트 제거).

```python
def make_structured_fn(system, user_fn, schema, key, temperature):
    """call_structured 호출 결과를 state[key]에 쓰는 노드 함수 팩토리."""
    def _fn(ctx):
        s = ctx.state
        s[key] = call_structured(system, user_fn(s), schema, temperature).model_dump()
    return _fn

review = FunctionNode(func=make_structured_fn(REVIEW_SYS, review_user, ReviewResult,
                                              "review", 0.2), name="review")

# design은 챕터 루프 밖, 책당 1회 → 그냥 파이썬에서 직접 호출
design = call_structured(DESIGN_SYS, design_user(state), DesignPlan, 0.3).model_dump()
```

부수 효과: ②의 "output_schema는 tool 못 씀" 제약이 **자동 해소**(ADK output_schema를 안 쓰므로).
source_text를 그냥 프롬프트 변수로 넣으면 끝.

### 안전벨트 (유지)
1. `format=schema` constrained decoding
2. ValidationError → 에러 되먹여 재시도(retries=2)
3. 끝까지 실패 → `ConvergenceError` → 챕터 flagged 후 진행

---

## 7. 함께 반영할 reviewer 개선 (별도 합의 사항)

ADK 이관과 무관하게 이미 합의된 schemas/prompts 개선:
- IssueType 신규 2개: `redundancy`(중복·장황), `surface_error`(오타·맞춤법·깨진 표·잔존 LaTeX)
- 게이트 숫자 통일: 프롬프트 "85" ↔ 코드 `QUALITY_GATE=80` → 80으로

---

## 8. 변경 요약

| 새로 생김 | 유지(거의 그대로) | 제거/축소 |
|---|---|---|
| DesignPlan, `write_brief` 변수 | `call_structured`, `_call` | grounding.py 파이프라인 |
| length_guard·gate·finalize (FunctionNode) | `unverified_numbers`(검증) | Grounding payload 주입 |
| 그래프 `Workflow`(Node/Edge/route/state) | push/PDF/meta 전부 | 소스 해석(→Design으로) |
| write_count·pass_count 카운터(루프 상한) | review/revise 로직 | `StructuredAgent`/BaseAgent 보일러플레이트 |
| | | Sequential/Loop/escalate (deprecated) |

Write → Review → Revise 역할 유지, 앞에 Design 추가, 루프·게이트는 **ADK 그래프 Workflow**,
JSON 신뢰성은 기존 `call_structured`로 방어, I/O(push/PDF)는 파이썬에 그대로.

---

## 9. 미해결/검증 필요

**검증 완료 (2026-06-19, `spikes/`):**
- ✅ `LiteLlm(num_ctx=32768, keep_alive, repeat_penalty)` → ollama 전달 (`ollama ps` CONTEXT=32768). `spikes/s1_options.py`
- ✅ route 자기참조 사이클로 루프 구성·종료 (escalate 불필요). `spikes/s2_escalate.py` + 추가 테스트
- ✅ `LlmAgent`가 그래프 노드로 동작, `output_key`→state. `FunctionNode`가 `ctx` 주입받아 state r/w.

**결정 완료:**
- ✅ planner(UnitPlan) → **Design에 흡수**(별도 노드 없음). 챕터 의도=`ChapterSpec.description`, 구성 관례=`write_brief`.
- ✅ 외부화 범위 → **write_brief만 변수화**. review/revise/design SYSTEM은 `prompts.py` 정적 유지.

**남은 결정:**
- 동기 `call_structured`를 노드 안에서 그대로 둘지, `asyncio.to_thread`로 분리할지(현재는 직렬이라 보류).
- `google-adk` 버전: 신 Workflow API 사용이므로 `google-adk>=2.3.0` 명시(requirements).


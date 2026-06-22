"""
write 단계 — 초안 생성(LlmAgent) + 가드①(길이 체크).

- write 노드: write_brief(Design 생성) + 참고/이전요약/챕터 + 정적 출력정책을 instruction으로
  조립해 자유 마크다운 초안을 만든다. output_key="draft".
- length_guard: MIN_CHARS 미만이면 재작성(상한 WRITE_MAX), 끝까지 짧으면 flagged 후 통과.
  (구 LoopAgent max_iterations 대체 = write_count 카운터)
"""
from google.adk.agents import LlmAgent
from google.adk.workflow import FunctionNode

from core.llm import make_gemma
from core.textutil import strip_title_h1
from core.config import WRITE_MAX        # 초안 재작성 상한
from core.grounding import ground_block
from agent.prompts import prev_block, chapter_block
from agent.trace import record


# 출력 정책(정적). 책별 집필 지시는 write_brief(Design 생성)가 담당.
WRITE_OUTPUT_POLICY = """
[집필·출력 정책 (공통)]
- 위의 집필 지시문(write_brief)을 이 책의 최우선 기준으로 따르세요.
- 챕터의 제목·설명을 빠짐없이 반영하고, 이전 요약이 있으면 자연스럽게 이어가되 반복하지 마세요.
- 참고 자료가 있으면 그 핵심·용어·수치를 우선 반영하고, 자료에 없는 구체 수치·고유 사실은 단정하지 마세요.
- 출력은 표준 Markdown. 특정 렌더러/LaTeX 엔진/HTML/Mermaid 의존 문법은 쓰지 마세요.
- 챕터 제목(H1, #)은 시스템이 자동으로 붙입니다. 본문은 소제목(##)부터 시작하세요.
- 설명·잡담 없이 완결된 본문만 출력하세요.
"""


def write_instruction(ctx) -> str:
    s = ctx.state
    return "\n".join(filter(None, [
        s["write_brief"],                              # Design 생성 집필 지시문(책별)
        ground_block(s.get("grounding", "")),
        prev_block(s.get("prev_summaries")),
        chapter_block(s["chapter"]),
        WRITE_OUTPUT_POLICY,                           # 정적 출력 정책
    ]))


def length_decision(state: dict) -> tuple[str, dict, int]:
    """길이 가드 판정(순수). 반환: (route 'ok'|'rewrite', state 변경분 updates, 본문 글자수).

    그래프 FunctionNode 와 멀티에이전트 LengthGate 가 공유한다(단일 출처).
    """
    chars = len(strip_title_h1(state.get("draft", "")).strip())
    write_count = state.get("write_count", 0) + 1
    updates = {"write_count": write_count}
    if chars >= state["min_chars"]:
        route = "ok"
    elif write_count < WRITE_MAX:
        route = "rewrite"
    else:
        updates["flagged"] = True
        route = "ok"
    return route, updates, chars


def length_guard_fn(ctx):
    s = ctx.state
    route, updates, chars = length_decision(s)
    s.update(updates)
    ctx.route = route
    if route == "rewrite":
        print(f"    [가드] 본문 {chars}자 < {s['min_chars']} → 재작성({s['write_count']}/{WRITE_MAX})")
    elif updates.get("flagged"):
        print(f"    [가드] 끝까지 {chars}자 — flagged 후 진행")

    record(ctx, stage="write", attempt=s["write_count"], chars=chars,
           route=ctx.route, draft=s.get("draft", ""))


def build_write_node() -> LlmAgent:
    return LlmAgent(name="write", model=make_gemma(0.8),
                    instruction=write_instruction, output_key="draft")


def build_length_guard() -> FunctionNode:
    return FunctionNode(func=length_guard_fn, name="length_guard")

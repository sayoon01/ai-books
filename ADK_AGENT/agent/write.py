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
from agent.prompts import WRITE_OUTPUT_POLICY, ground_block, prev_block, chapter_block

WRITE_MAX = 3        # 초안 재작성 상한


def write_instruction(ctx) -> str:
    s = ctx.state
    return "\n".join(filter(None, [
        s["write_brief"],                              # Design 생성 집필 지시문(책별)
        ground_block(s.get("grounding", "")),
        prev_block(s.get("prev_summaries")),
        chapter_block(s["chapter"]),
        WRITE_OUTPUT_POLICY,                           # 정적 출력 정책
    ]))


def length_guard_fn(ctx):
    s = ctx.state
    body = strip_title_h1(s.get("draft", "")).strip()
    s["write_count"] = s.get("write_count", 0) + 1
    if len(body) >= s["min_chars"]:
        ctx.route = "ok"
    elif s["write_count"] < WRITE_MAX:
        print(f"    [가드] 본문 {len(body)}자 < {s['min_chars']} → 재작성({s['write_count']}/{WRITE_MAX})")
        ctx.route = "rewrite"
    else:
        s["flagged"] = True
        print(f"    [가드] 끝까지 {len(body)}자 — flagged 후 진행")
        ctx.route = "ok"


def build_write_node() -> LlmAgent:
    return LlmAgent(name="write", model=make_gemma(0.8),
                    instruction=write_instruction, output_key="draft")


def build_length_guard() -> FunctionNode:
    return FunctionNode(func=length_guard_fn, name="length_guard")

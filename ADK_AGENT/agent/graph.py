"""
챕터 파이프라인 그래프 조립 (ADK 2.3.0 google.adk.workflow.Workflow).

    START → write → length_guard → {rewrite: write, ok: review}
    review → gate → {revise: revise, done: finalize}
    revise → review

단계 로직은 write.py / review.py / revise.py 에 있고, 여기서는 노드를 엮기만 한다.
escalate 없음 → 종료는 finalize(터미널)로 라우팅. 루프 상한은 write_count/pass_count 카운터.
"""
from google.adk.workflow import Workflow, FunctionNode, START

from agent.write import build_write_node, build_length_guard
from agent.review import build_review_node, build_gate_node
from agent.revise import build_revise_node


def finalize_fn(ctx):
    """터미널 — 최종 draft 확정(실제 저장은 파이썬 드라이버가 세션 state에서 읽어 처리)."""
    return ctx.state.get("draft", "")


def build_chapter_graph() -> Workflow:
    write = build_write_node()
    length_guard = build_length_guard()
    review = build_review_node()
    gate = build_gate_node()
    revise = build_revise_node()
    finalize = FunctionNode(func=finalize_fn, name="finalize")

    return Workflow(name="chapter", edges=[
        (START, write),
        (write, length_guard),
        (length_guard, {"rewrite": write, "ok": review}),
        (review, gate),
        (gate, {"revise": revise, "done": finalize}),
        (revise, review),
    ])

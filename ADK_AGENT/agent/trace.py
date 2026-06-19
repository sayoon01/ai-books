"""
챕터 진행 히스토리 기록 헬퍼.

각 노드(write/review/gate)가 자기 단계 결과를 state["history"]에 한 항목씩 남긴다.
드라이버(pipeline)가 이 history 를 logs/chapter-NN.json 에 통째로 저장 → 사후에
"design 반환 → write → review → revise" 전 과정을 확인할 수 있다.

주의: 리스트 in-place append 는 ADK state delta 로 안 잡힐 수 있어 '재할당'으로 추가한다.
history 는 어떤 instruction 에도 주입되지 않으므로 LLM 프롬프트를 키우지 않는다.
"""


def record(ctx, **entry) -> None:
    ctx.state["history"] = ctx.state.get("history", []) + [entry]

# orchestrators/ — 핵심 기여물

세 가지 오케스트레이터. 모두 `base.py`의 동일 인터페이스를 구현하며,
`../../ADK_AGENT`의 에이전트·판단 로직을 공유한다.

- `base.py`        — 공통 인터페이스 (`run(chapter, state) -> Result`)
- `code_orch.py`   — Code: `ADK_AGENT/agent/graph.py` 래핑 (이미 존재)
- `llm_orch.py`    — ★ LLM: 판단 함수를 tool로 노출, LLM이 다음 노드 선택
- `hybrid_orch.py` — ★ Hybrid: 큰 흐름=코드, 세부 판단=LLM

상세 설계: [`../docs/design-notes.md`](../docs/design-notes.md)

# orchestrators/ — 핵심 기여물

세 가지 오케스트레이터. 모두 `base.py`의 동일 인터페이스를 구현하며,
`../testbed`(복사된 ADK 엔진)의 에이전트·판단 로직을 공유한다.
`_bootstrap.py`가 testbed를 sys.path에 추가한다.

- `base.py`        — 공통 인터페이스 (`run(chapter, base_state) -> Result`)
- `code_orch.py`   — Code: `testbed/agent/graph.py` 래핑 **(구현 완료)**
- `llm_orch.py`    — ★ LLM: 판단 함수를 tool로 노출, LLM이 다음 노드 선택 (stub)
- `hybrid_orch.py` — ★ Hybrid: 큰 흐름=코드, 세부 판단=LLM (stub)

상세 설계: [`../docs/design-notes.md`](../docs/design-notes.md)

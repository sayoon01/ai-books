# 설계 메모

## 왜 ADK_AGENT를 testbed/로 복사(vendoring)하는가

세 오케스트레이션을 공정하게 비교하려면 에이전트·LLM·판단 로직이
**한 소스**여야 한다. 외부의 `../ADK_AGENT`를 직접 import하면 원본이
바뀔 때 실험 결과가 흔들려 재현성이 깨진다. 그래서 엔진 코드를
`testbed/`에 **고정된 스냅샷으로 복사**해 두고, 그 스냅샷만 사용한다.

복사한 코드는 `from agent...`, `from core...` (최상위) 형태로 import하므로,
`orchestrators/_bootstrap.py`가 `testbed/`를 `sys.path`에 추가하면 코드
수정 없이 그대로 동작한다(검증 완료).

## 오케스트레이터 인터페이스 (구현 예정)

`orchestrators/base.py`에 공통 인터페이스를 둔다. 세 구현은 같은 입력을
받아 같은 형태의 결과(산출물 + 지표)를 반환해야 한다.

```python
# 의사코드
class Orchestrator(Protocol):
    name: str
    def run(self, chapter, state) -> Result:
        """draft + metrics(time, tokens, retries, score) 반환"""
```

- `code_orch.py`  — `testbed/agent/graph.py` (Workflow) 래핑. **(구현 완료)**
- `llm_orch.py`   — 판단 함수들을 **tool로 LLM에 노출**, LLM이 다음
  노드를 고르게 한다. (write/review/revise/finish 중 선택)
- `hybrid_orch.py`— 큰 흐름(write→review→finish)은 코드 고정, 게이트
  통과 여부 등 세부 판단만 LLM에 위임.

## 기존 자산 재사용 지도

| 필요 | 위치 (복사된 testbed 기준) |
|------|------|
| 코드 오케스트레이션 | `testbed/agent/graph.py`, `agents.py` |
| 판단 순수 함수 | `testbed/agent/write.py`, `review.py` |
| LLM 호출/설정 | `testbed/core/llm.py`, `core/config.py` |
| 비교 하니스 템플릿 | `testbed/spikes/compare_engines.py` |
| 챕터 실행 패턴 | `testbed/pipeline.py` (InMemoryRunner 사용부) |

## 메모리 연계

- 프로젝트 방향: `adk-multi-agent-direction` — 코드 오케스트레이션(3b) 채택,
  하이브리드 보류 → 본 논문에서 LLM/Hybrid를 **실험용으로** 신규 구현.
- 데이터 소스: `mold-dx-data-source` (정형 작업 입력 후보).

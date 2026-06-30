# datasets/ — 입력 작업

작업 특성별 입력 3종 (ADK_AGENT toc json 형식). discussion의 가이드라인
표를 실험으로 뒷받침하려면 입력도 특성별로 나뉘어야 한다.

| 캐노니컬 이름 | 특성 | 원본 | 구조 |
|---------------|------|------|------|
| `structured.json` | 정형 반복형 (기술 보고서) | mold-machine-report | 챕터 8개 고정 |
| `creative.json`   | 창의형 (소설 재해석) | war_and_peace_modern | 목차 자동 생성 |
| `mixed.json`      | 혼합형 (데이터+서술 가이드) | mold-dx-auto | 목차 자동 생성, source 有 |

실험은 캐노니컬 이름을 쓴다. 예:
```bash
$PY -m experiments.run_experiment --orch all --task datasets/structured.json
```

> 참고: `source` 파일(예: `data/...`)이 testbed에 없으면 grounding 없이
> 진행된다(세 구조 동일 조건이라 비교는 유효). 실제 데이터로 grounding을
> 넣으려면 해당 파일을 `testbed/data/`에 두면 된다.

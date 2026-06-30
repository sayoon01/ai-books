# experiments/ — 실행 드라이버

`../../ADK_AGENT`를 import하여 3구조 × 3작업 × 20회 실험을 돌린다.

- `run_experiment.py` — 실험 루프, `results/`에 원시 출력 저장
- `metrics.py`        — 시간·토큰·retry 수집 (★ 토큰 계측 추가 필요)
- `judge.py`          — LLM-as-Judge 품질 채점 (0–100)

절차: [`../docs/experiment-protocol.md`](../docs/experiment-protocol.md)

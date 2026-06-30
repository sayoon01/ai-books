# 실험 프로토콜

오케스트레이션 구조 비교 실험의 절차와 변인 통제 규칙을 정의한다.

## 1. 변인 통제 (가장 중요)

세 구조 비교의 정당성은 **오케스트레이션 외 모든 변인을 고정**하는 데서
나온다. 다음을 동일하게 유지한다.

- 동일한 LLM (모델·온도·context 길이) — `../ADK_AGENT/core/config.py`
- 동일한 에이전트 프롬프트 (Planner/Writer/Reviewer/Reviser)
- 동일한 판단 로직 — `length_decision`, `do_review`, `gate_decision`
  (`../ADK_AGENT/agent/write.py`, `review.py`의 순수 함수 재사용)
- 동일한 입력 (design.json 캐시) 및 동일한 grounding 소스

→ **유일하게 달라지는 것은 "다음에 무엇을 할지 누가 정하는가"** 뿐이다.

## 2. 작업(Task) 3종

| 유형 | 설명 | 입력(toc) |
|------|------|-----------|
| 정형 반복 | 정형화된 기술 보고서 | `datasets/structured.json` |
| 창의 | 자유 서술 | `datasets/creative.json` |
| 혼합 | 정형 구조 + 비정형 서술 | `datasets/mixed.json` |

## 3. 반복 및 측정

- 각 (구조 × 작업) 조합을 **20회** 반복.
- 매 실행마다 수집:
  - `execution_time_sec`
  - `token_usage` (prompt + completion) ← **계측 추가 필요**
  - `quality` (LLM-as-Judge, 0–100)
  - `retry_count` (write_count + pass_count)
  - 산출물 길이 (chars)
- 일관성(Consistency) = 20회 점수/길이의 표준편차.

## 4. 토큰 계측 추가 (현재 미구현)

`../ADK_AGENT`의 비교 하니스(`spikes/compare_engines.py`)는 시간·점수·GPU는
재지만 **토큰은 안 잰다.** 다음 중 한 방법으로 추가:

- (권장) `core/llm.py` 호출 레이어에서 ollama 응답의
  `prompt_eval_count` / `eval_count`를 누적 → 챕터 로그에 기록.
- 또는 OpenTelemetry 트레이스(`core/tracing.py`)의 토큰 span 속성 집계.

## 5. LLM-as-Judge 채점

- 평가 프롬프트는 세 구조에 **동일**하게 적용.
- 가능하면 채점 모델을 생성 모델과 분리(self-preference 편향 완화).
- 동일 산출물 3회 채점 후 평균(채점 자체의 분산 완화).

## 6. 통계 처리

- 구조 간 차이는 평균 ± 표준편차로 보고.
- 표본이 충분하면 유의성 검정(예: Welch t-test, Mann–Whitney U) 수행.
- 결과는 `results/`에 원시 json/csv로, 집계는 `benchmark/`에서.

## 7. 산출물 → 논문 반영

1. `results/*.csv` → `scripts/`로 그림 생성 → `figures/result_bar.pdf`
2. 집계 수치 → `paper/sections/04-results.tex` 표 채우기
3. 해석 문장 템플릿의 밑줄 자리 → 실제 값으로 교체

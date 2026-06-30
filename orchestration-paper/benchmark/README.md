# benchmark/ — 평가·집계

`results/`의 원시 출력을 읽어 구조별 지표를 집계하고 통계 처리한다.

- 평균 ± 표준편차 산출 (일관성 = std)
- 구조 간 유의성 검정 (Welch t-test / Mann–Whitney U)
- 집계 결과 → `scripts/`가 그림 생성에 사용

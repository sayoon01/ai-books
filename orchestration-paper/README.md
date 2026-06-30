# Orchestration Paper

LLM 기반 멀티 에이전트 시스템에서 **오케스트레이션 구조(Code / LLM / Hybrid)**에
따른 성능을 비교하고 설계 가이드라인을 제안하는 연구 프로젝트.

테스트베드(Testbed)는 상위 디렉토리의 **`../ADK_AGENT`** (Google ADK 기반
멀티 에이전트 문서 생성 시스템)를 그대로 재사용한다. 이 프로젝트는 그 위에
**실험 레이어만** 얹는다. ADK_AGENT 코드는 수정하지 않는 것을 원칙으로 한다.

## 핵심 아이디어

| 구조 | 흐름 제어 주체 | 현황 |
|------|---------------|------|
| **Code** | 코드(고정 엣지·if문) | `../ADK_AGENT/agent/graph.py` 에 이미 존재 → 어댑터만 |
| **LLM** | LLM이 다음 동작 결정 | ★ 신규 구현 필요 |
| **Hybrid** | 큰 흐름=코드, 세부=LLM | ★ 신규 구현 필요 |

세 구조는 동일한 에이전트·LLM·판단 로직을 공유하고 **흐름 제어 주체만**
다르게 하여 변인을 통제한다.

## 디렉토리 구조

```
orchestration-paper/
├── paper/          # 논문 원고 (LaTeX, IEIE/IEEE 스타일)
│   ├── main.tex
│   ├── refs.bib
│   └── sections/   # 서론·구조·실험·결과·discussion·결론
├── orchestrators/  # ★ 핵심 기여물: Code/LLM/Hybrid 오케스트레이터
├── experiments/    # 실행 드라이버 (ADK_AGENT import)
├── datasets/       # 입력 작업: 정형/창의/혼합 (toc json)
├── benchmark/      # 지표 집계·통계·유의성 검정
├── results/        # 원시 실험 출력 (json/csv) — 커밋
├── figures/        # 논문용 그림 (results에서 생성)
├── scripts/        # 그림/표 생성 스크립트
└── docs/           # 실험 프로토콜, 설계 메모
```

## 논문 빌드

LaTeX 도구체인 필요 (현재 이 머신엔 미설치):

```bash
# 설치 (Ubuntu 예시)
sudo apt-get install texlive-full   # 또는 texlive-xetex texlive-lang-korean

cd paper
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

필요 패키지: `IEEEtran`, `kotex`(한글), `tikz`, `booktabs`.

> ⚠️ **연구윤리**: `paper/sections/04-results.tex`의 표·그림·해석 문장은
> 실험 수행 후 채울 자리이다. 수치를 임의로 채우지 말 것.

## 다음 작업 (TODO)

1. `orchestrators/` — `base.py` 인터페이스 + 3개 오케스트레이터 구현
2. `experiments/metrics.py` — **토큰 사용량 계측 추가** (현재 ADK 하니스엔 없음)
3. `datasets/` — 정형/창의/혼합 작업 toc 3종 확정
4. `experiments/run_experiment.py` — 3구조 × 3작업 × 20회 실행
5. 결과 → `figures/` 그림 생성 → 논문 표/그림 채우기

자세한 절차는 [`docs/experiment-protocol.md`](docs/experiment-protocol.md) 참고.

# Orchestration Paper

LLM 기반 멀티 에이전트 시스템에서 **오케스트레이션 구조(Code / LLM / Hybrid)**에
따른 성능을 비교하고 설계 가이드라인을 제안하는 연구 프로젝트.

테스트베드(Testbed)는 `../ADK_AGENT`(Google ADK 기반 멀티 에이전트 문서
생성 시스템)의 엔진 코드를 **`testbed/`에 복사(vendoring)**하여 사용한다.
외부 디렉토리를 import하지 않고 프로젝트 안에 고정된 스냅샷을 두어,
원본이 바뀌어도 실험 재현성이 유지된다. 이 프로젝트는 그 위에 **실험
레이어(orchestrators/, experiments/)만** 얹는다.

## 핵심 아이디어

| 구조 | 흐름 제어 주체 | 현황 |
|------|---------------|------|
| **Code** | 코드(고정 엣지·if문) | `testbed/agent/graph.py` 사용 → 어댑터 완료 |
| **LLM** | LLM이 다음 동작 결정 | ★ 신규 구현 필요 (stub) |
| **Hybrid** | 큰 흐름=코드, 세부=LLM | ★ 신규 구현 필요 (stub) |

세 구조는 동일한 에이전트·LLM·판단 로직을 공유하고 **흐름 제어 주체만**
다르게 하여 변인을 통제한다.

## 디렉토리 구조

```
orchestration-paper/
├── paper/          # 논문 원고 (LaTeX, IEIE/IEEE 스타일)
│   ├── main.tex
│   ├── refs.bib
│   └── sections/   # 서론·구조·실험·결과·discussion·결론
├── testbed/        # ★ ADK_AGENT 엔진 복사본 (agent/ core/ ...) — vendored
├── orchestrators/  # ★ 핵심 기여물: Code/LLM/Hybrid 오케스트레이터
├── experiments/    # 실행 드라이버 (testbed 사용)
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
# 설치 (Ubuntu) — 한 줄로 붙여넣을 것 (줄바꿈 주의!)
sudo apt-get install -y texlive-full
# (5GB 부담되면 최소 세트)
# sudo apt-get install -y texlive-latex-recommended texlive-latex-extra \
#   texlive-fonts-recommended texlive-pictures texlive-publishers texlive-lang-korean

cd paper
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

필요 패키지: `IEEEtran`(texlive-publishers), `kotex`(texlive-lang-korean),
`tikz`(texlive-pictures), `booktabs`.

> ⚠️ **연구윤리**: `paper/sections/04-results.tex`의 표·그림·해석 문장은
> 실험 수행 후 채울 자리이다. 수치를 임의로 채우지 말 것.

## 파이썬 실행 환경

testbed는 `google-adk`, `litellm`, `ollama` 등이 필요하다. 별도 venv를
만들거나, 우선은 검증된 `../ADK_AGENT/.venv`를 그대로 써도 된다.

```bash
# 임시: ADK_AGENT venv 재사용
/home/keti/yune/ai-books/ADK_AGENT/.venv/bin/python -c "from orchestrators import REGISTRY; print(list(REGISTRY))"
# 또는 전용 venv
python3 -m venv .venv && ./.venv/bin/pip install -r testbed/requirements.txt
```

## 실험 실행

ollama 서버(gemma4:31b)가 떠 있어야 한다.

```bash
PY=/home/keti/yune/ai-books/ADK_AGENT/.venv/bin/python
# 스모크: code 구조 1챕터 1회
$PY -m experiments.run_experiment --orch code --limit 1 --repeat 1

# 본 실험: 세 구조, 첫 2챕터, 각 5회
$PY -m experiments.run_experiment --orch all --limit 2 --repeat 5 \
    --task datasets/mold-machine-report.json
```

결과: `results/<slug>/runs.jsonl`(원시) + `summary.json`(구조별 평균·표준편차).

## 진행 현황 / 다음 작업 (TODO)

- [x] 디렉토리 골격 + LaTeX 논문 초안
- [x] `testbed/` 엔진 복사(vendoring) + import 검증
- [x] `orchestrators/base.py` 인터페이스 + `code_orch.py` (Code) 구현 — **실행 검증**
- [x] **토큰 사용량 계측** — `testbed/core/usage.py` + `llm.py` 래퍼 + 이벤트 합산 — **실행 검증**
- [x] `orchestrators/llm_orch.py` (라우터 LLM) 구현
- [x] `orchestrators/hybrid_orch.py` (코드 골격 + LLM 게이트) 구현
- [x] `experiments/run_experiment.py` — 구조 × 작업 × 반복 × 챕터 실행/집계
- [x] `experiments/judge.py` — LLM-as-Judge 품질 채점(`--judge`, 기본 gemma3:27b)
- [x] `datasets/` — structured/creative/mixed 3종 확정
- [x] `scripts/plot_results.py` — runs.jsonl → `figures/result_bar.pdf`
- [ ] **본 실험 수행** — 3구조 × 3작업 × 20회 + `--judge`
- [ ] 결과 수치/그림 → 논문 표(04-results) 채우기
- [ ] (선택) LaTeX 설치 후 PDF 빌드

### 그림 생성
```bash
$PY scripts/plot_results.py --runs results/<slug>/runs.jsonl
# → figures/result_bar.pdf (+ .png)
```

자세한 절차는 [`docs/experiment-protocol.md`](docs/experiment-protocol.md) 참고.

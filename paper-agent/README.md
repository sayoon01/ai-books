# paper-agent

논문 한 편을 **설계 → 집필 → 검수 → 수정 → 조립(LaTeX/PDF)** 까지 자동화하는
멀티 에이전트 시스템. 책 생성기(ADK_AGENT/testbed)와 독립이며, 논문 도메인 전용이다.

## 4개 에이전트

| 에이전트 | 파일 | 역할 | 모델 |
|---|---|---|---|
| ① Plan | `agents/plan.py` | 설계·실험·작성·자료(표/그림/통계) 계획을 `plan.json` 한 객체로 | gemma4:31b |
| ② Write | `agents/write.py` | 섹션 단위 LaTeX 본문 집필 (+길이 가드) | gemma4:31b |
| ③ Review | `agents/review.py` | **학회 리뷰어** 구조화 검수 + 게이트 | **qwen3-coder:30b** |
| ④ Revise | `agents/revise.py` | 검수 issue 반영 수정 (keep-best) | gemma4:31b |

> **핵심 설계 1 — 교차 모델 검수**: 생성은 gemma, 검수는 **다른 계열(Qwen)**.
> 같은 모델로 검수하면 자기 실수를 못 잡는다(self-consistency bias).
> `PAPER_REVIEW_MODEL` env 로 교체 가능.
>
> **핵심 설계 2 — 수치 환각 차단**: 표/그림/통계의 **수치는 LLM이 만들지 않는다**.
> Plan은 "무엇을 만들지"만 정하고(`artifacts/`), 실제 값은 `artifacts/build.py`가
> 데이터(`results/summary.json` 등)에서 뽑는다. 본문은 `\ref{id}`로 참조만 하며,
> `core.grounding.unverified_numbers`가 자료에 없는 수치를 결정적으로 검출한다.

## 흐름 (orchestrator.py)

```
[Plan] → plan.json
  → [Artifacts.build]  데이터 → figures/*.png, tables/*.tex, 실제값 digest
  → for section in plan.sections:
        [Write] → 초안(LaTeX)
        loop(PASS_MAX): [Review](qwen) → gate → [Revise](gemma)   # keep-best
        sections/<id>.tex 저장
  → [assemble] main.tex (kotex 2단) → xelatex → main.pdf
```

## 사용법

```bash
PY=/home/keti/yune/ai-books/ADK_AGENT/.venv/bin/python   # ollama 만 있으면 됨(ADK 불필요)

# 설계만 (빠름, 사람이 plan.json 검토·편집)
$PY run.py --input inputs/orchestration.json --plan-only

# 앞 N개 섹션만 (스모크)
$PY run.py --input inputs/orchestration.json --limit 2

# 전체
$PY run.py --input inputs/orchestration.json

# PDF 빌드 (한글 → xelatex 권장)
cd output/<slug> && xelatex main && xelatex main
```

입력 spec(`inputs/*.json`): `{slug, topic, venue?, source?}`.
`source`는 실측 자료 파일/URL(없어도 됨 — 그러면 계획 수준으로만).

## 산출물 (`output/<slug>/`)

```
plan.json            # 설계(편집 가능 — 재실행 시 로드)
sections/<id>.tex    # 섹션별 best 초안
tables/  figures/    # 데이터에서 생성된 표/그림
main.tex  main.pdf   # 조립 결과
logs/run.json        # 점수·토큰(모델별 분리) 트레이스
```

## 알려진 한계 / 다음 작업

- **GPU 모델 스왑 느림**: gemma(19GB)+qwen(22GB)가 한 GPU에 동시에 안 올라가
  생성↔검수 전환마다 재로딩 → 섹션당 수 분. 대안: 작은 교차모델(`qwen2.5-coder:7b`)을
  `PAPER_REVIEW_MODEL`로, 또는 GPU 증설.
- **리뷰어가 박함**: 섹션 성격상 해당 없는 축(초록의 novelty 등)도 감점하는 경향 →
  `agents/review.py`의 축 가이드 프롬프트 튜닝 여지.
- 미구현: 인용/related work 자동 수집, 전체 일관성(global review) 패스,
  IEEEtran 등 학회 템플릿 선택.
```

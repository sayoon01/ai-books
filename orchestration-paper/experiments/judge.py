"""LLM-as-Judge 품질 채점.

생성 모델(gemma4:31b)과 분리된 별도 모델로 산출물을 0~100점 채점한다
(self-preference 편향 완화). 채점 자체의 분산을 줄이려 N회 평균을 쓴다.

리뷰어 점수(best_score)는 '생성에 쓰인 같은 모델'의 자기평가라 논문의 품질
지표로는 약하다. 본 모듈의 judge_score 를 품질 지표로 권장한다.

사용:
    from experiments.judge import judge
    res = judge(draft, chapter, config)     # {"score": .., "axes": {..}, "n": 3}
"""
from __future__ import annotations

import json
import os
import statistics

import ollama
from pydantic import BaseModel, Field

# 생성 모델과 다른 모델을 기본값으로(편향 완화). 환경변수로 교체 가능.
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gemma3:27b")
JUDGE_SAMPLES = int(os.getenv("JUDGE_SAMPLES", "3"))


class JudgeAxes(BaseModel):
    accuracy: int = Field(ge=0, le=100)
    completeness: int = Field(ge=0, le=100)
    clarity: int = Field(ge=0, le=100)
    depth: int = Field(ge=0, le=100)
    structure: int = Field(ge=0, le=100)


class JudgeResult(BaseModel):
    score: int = Field(ge=0, le=100)        # 종합
    axes: JudgeAxes


JUDGE_SYSTEM = """
당신은 엄정한 원고 평가자입니다. 주어진 챕터 원고의 품질을 0~100점으로 평가하세요.
- accuracy(정확성)/completeness(완결성)/clarity(명료성)/depth(깊이)/structure(구성)
  각 축을 0~100으로 매기고, 이를 종합해 score(0~100)를 정하세요.
- 칭찬도 트집도 아닌 객관적 기준으로 평가하세요. 문서 유형(설명/보고/창작)에 맞게 보세요.
- 설명 없이 제공된 JSON 스키마(score, axes)만 출력하세요.
"""


def _judge_user(draft: str, chapter: dict, config: dict) -> str:
    return f"""
[문서 설정]
{json.dumps(config, ensure_ascii=False, indent=2)}

[챕터]
{json.dumps(chapter, ensure_ascii=False, indent=2)}

[평가할 원고]
{draft}

위 원고를 평가하세요.
"""


def judge_once(draft: str, chapter: dict, config: dict, model: str = JUDGE_MODEL) -> JudgeResult:
    raw = ollama.chat(
        model=model,
        format=JudgeResult.model_json_schema(),
        options={"temperature": 0.0},
        messages=[{"role": "system", "content": JUDGE_SYSTEM},
                  {"role": "user", "content": _judge_user(draft, chapter, config)}],
    )["message"]["content"]
    return JudgeResult.model_validate_json(raw)


def judge(draft: str, chapter: dict, config: dict,
          model: str = JUDGE_MODEL, samples: int = JUDGE_SAMPLES) -> dict:
    """N회 채점 후 평균. 반환: {"score","axes","n","model","raw_scores"}."""
    if not draft.strip():
        return {"score": 0, "axes": {}, "n": 0, "model": model, "raw_scores": []}
    results = [judge_once(draft, chapter, config, model) for _ in range(samples)]
    axes_keys = JudgeAxes.model_fields.keys()
    return {
        "score": round(statistics.mean(r.score for r in results), 1),
        "axes": {k: round(statistics.mean(getattr(r.axes, k) for r in results), 1)
                 for k in axes_keys},
        "n": len(results),
        "model": model,
        "raw_scores": [r.score for r in results],
    }

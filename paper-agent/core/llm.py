"""
LLM 호출 계층 (ollama). 책 엔진의 llm.py 를 복사하되 두 가지를 바꿨다:
  1) ADK(LiteLlm/make_gemma) 의존성 제거 — paper-agent 는 순수 파이썬 오케스트레이터다.
  2) 호출마다 model 을 바꿀 수 있게 인자화 — 생성=MODEL, 검수=REVIEW_MODEL.

세 경로:
  - `call_text`       : 자유 텍스트 (write/revise 등 긴 본문 생성).
  - `call_structured` : Pydantic 스키마 강제(format=) + 검증 재시도. 작고 안정적인 스키마(Review)용.
  - `call_parsed`     : 자유 텍스트 → JSON 추출·검증 + 재시도. 크고 리스트 많은 스키마(PaperPlan)용.
"""
import json
from typing import Callable, TypeVar

import ollama
from pydantic import BaseModel, ValidationError

from core.textutil import parse_json
from core.config import (MODEL, LLM_TEMPERATURE, LLM_NUM_CTX,
                         LLM_REPEAT_PENALTY, LLM_KEEP_ALIVE)
from core.usage import METER

_OPTIONS = {"temperature": LLM_TEMPERATURE, "num_ctx": LLM_NUM_CTX,
            "repeat_penalty": LLM_REPEAT_PENALTY}
_KEEP_ALIVE = LLM_KEEP_ALIVE

T = TypeVar("T", bound=BaseModel)


def _chat(**kwargs):
    """ollama.chat 래퍼 — 응답의 토큰 수를 METER에 누적(모델명 태그 포함)."""
    res = ollama.chat(**kwargs)
    try:
        p = res.get("prompt_eval_count")
        c = res.get("eval_count")
    except AttributeError:                       # 신버전 ChatResponse(객체)
        p = getattr(res, "prompt_eval_count", None)
        c = getattr(res, "eval_count", None)
    METER.add(p, c, model=kwargs.get("model"))
    return res


class ConvergenceError(Exception):
    """재시도 한도까지 스키마 검증을 통과하지 못함. 해당 섹션은 플래그 후 진행."""


def call_text(system: str, user: str, temperature: float = 0.7,
              model: str | None = None) -> str:
    """자유 텍스트 생성 (동기). write/revise 등 긴 본문용."""
    res = _chat(
        model=model or MODEL,
        options={**_OPTIONS, "temperature": temperature},
        keep_alive=_KEEP_ALIVE,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    return res["message"]["content"]


def call_structured(system: str, user: str, schema: type[T], temperature: float,
                    retries: int = 2, model: str | None = None,
                    post_validate: Callable[[T], T] | None = None) -> T:
    """Pydantic 스키마 강제(ollama format=) + 실패 시 에러를 모델에 되먹여 재시도."""
    msg = [{"role": "system", "content": system},
           {"role": "user", "content": user}]
    last_err: Exception | None = None

    for _ in range(retries + 1):
        raw = _chat(
            model=model or MODEL,
            format=schema.model_json_schema(),          # ★ 구조화 출력 강제
            options={**_OPTIONS, "temperature": temperature},
            keep_alive=_KEEP_ALIVE,
            messages=msg,
        )["message"]["content"]
        try:
            obj = schema.model_validate_json(raw)
            return post_validate(obj) if post_validate else obj
        except (ValidationError, ValueError) as e:
            last_err = e
            msg.append({"role": "assistant", "content": raw})
            msg.append({"role": "user",
                        "content": f"검증 실패:\n{e}\n같은 JSON 스키마를 정확히 지켜 다시 작성하세요."})

    raise ConvergenceError(f"{schema.__name__} 미수렴 ({retries + 1}회 시도): {last_err}")


def call_parsed(system: str, user: str, schema: type[T], temperature: float,
                retries: int = 2, model: str | None = None) -> T:
    """자유 텍스트 → JSON 추출(parse_json) → 스키마 검증 + 실패 시 에러 되먹여 재시도.

    제약 디코딩(format=)이 대형/리스트 스키마에서 반복 루프로 깨지거나 느린 문제를 피한다.
    """
    msg = [{"role": "system", "content": system},
           {"role": "user", "content": user}]
    last_err: Exception | None = None

    for _ in range(retries + 1):
        raw = _chat(
            model=model or MODEL,
            options={**_OPTIONS, "temperature": temperature},
            keep_alive=_KEEP_ALIVE,
            messages=msg,
        )["message"]["content"]
        try:
            return schema.model_validate(parse_json(raw))
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            last_err = e
            msg.append({"role": "assistant", "content": raw})
            msg.append({"role": "user",
                        "content": f"형식 오류:\n{e}\nJSON 객체만 출력하세요. 스키마를 정확히 지키고, "
                                   f"같은 단어를 반복하지 말고 간결히 작성하세요."})

    raise ConvergenceError(f"{schema.__name__} 미수렴 ({retries + 1}회 시도): {last_err}")

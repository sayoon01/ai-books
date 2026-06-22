"""
LLM 호출 계층 (gemma4:31b 고정).

세 경로:
  - `_call`           : 자유 텍스트 (그래프 밖 보조 호출용).
  - `call_structured` : Pydantic 스키마 강제(format=) + 검증 재시도. 작고 안정적인 스키마(review)용.
  - `call_parsed`     : 자유 텍스트 생성 → JSON 추출·검증 + 재시도. 제약 디코딩이 느리거나
        반복 루프로 깨지는 대형/리스트 스키마(DesignPlan)용. (constrained decoding 회피)
  - `GEMMA` (LiteLlm) : ADK LlmAgent(write/revise) 노드가 쓰는 모델 핸들.
        · num_ctx/keep_alive/repeat_penalty 가 ollama 까지 전달됨(spikes/s1 검증).

generator/book_writer.py 의 LLM 부분을 복사·독립화한 것(원본 무수정 원칙).
"""
import json
from typing import Callable, TypeVar

import ollama
from pydantic import BaseModel, ValidationError

from core.textutil import parse_json
from core.config import (MODEL, LLM_TEMPERATURE, LLM_NUM_CTX,
                         LLM_REPEAT_PENALTY, LLM_KEEP_ALIVE)

_OPTIONS = {"temperature": LLM_TEMPERATURE, "num_ctx": LLM_NUM_CTX,
            "repeat_penalty": LLM_REPEAT_PENALTY}
# 멀티 요청 사이 모델 언로드로 멈추는 것 방지 (런너 유지).
_KEEP_ALIVE = LLM_KEEP_ALIVE

T = TypeVar("T", bound=BaseModel)


class ConvergenceError(Exception):
    """재시도 한도까지 스키마 검증을 통과하지 못함. 해당 챕터는 플래그 후 진행."""


def _call(system: str, user: str, temperature: float = 0.7) -> str:
    """자유 텍스트 생성 (동기). 그래프 밖 호출(예: design 보조)용."""
    res = ollama.chat(
        model=MODEL,
        options={**_OPTIONS, "temperature": temperature},
        keep_alive=_KEEP_ALIVE,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    return res["message"]["content"]


def call_structured(system: str, user: str, schema: type[T], temperature: float,
                    retries: int = 2, post_validate: Callable[[T], T] | None = None) -> T:
    """Pydantic 스키마 강제(ollama format=) + 실패 시 에러를 모델에 되먹여 재시도."""
    msg = [{"role": "system", "content": system},
           {"role": "user", "content": user}]
    last_err: Exception | None = None

    for _ in range(retries + 1):
        raw = ollama.chat(
            model=MODEL,
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
                retries: int = 2) -> T:
    """자유 텍스트 생성 → JSON 추출(parse_json) → 스키마 검증 + 실패 시 에러 되먹여 재시도.

    제약 디코딩(format=)이 대형/리스트 스키마에서 반복 루프로 깨지거나 느린 문제를 피한다.
    (배경: DesignPlan 을 format= 로 만들다 'cycle cycle...' 반복으로 JSON 미완성 → 미수렴.)
    """
    msg = [{"role": "system", "content": system},
           {"role": "user", "content": user}]
    last_err: Exception | None = None

    for _ in range(retries + 1):
        raw = ollama.chat(
            model=MODEL,
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


def make_gemma(temperature: float = 0.8):
    """write/revise LlmAgent 노드가 쓸 LiteLlm 핸들. (지연 import — adk 없는 환경 보호)
    num_ctx/keep_alive/repeat_penalty 가 ollama 까지 전달됨(spikes/s1 검증)."""
    from google.adk.models.lite_llm import LiteLlm
    return LiteLlm(
        model=f"ollama_chat/{MODEL}",
        num_ctx=_OPTIONS["num_ctx"],
        repeat_penalty=_OPTIONS["repeat_penalty"],
        keep_alive=_KEEP_ALIVE,
        temperature=temperature,          # write 0.8 / revise 0.5
    )

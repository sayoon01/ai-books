"""
LLM 호출 계층.

- `_call`        : 자유 텍스트 생성 (Writer/Reviser용). book_writer에서 이동.
- `call_structured` : Pydantic 스키마 강제 + self-heal 재시도 (Reviewer/Planner용).

긴 프롬프트 체인이 "수렴"한다는 것은, 단계 경계마다 출력을 스키마로 검증하고
실패 시 에러를 모델에 되먹여 재시도해 끝까지 깨지지 않고 흐른다는 뜻이다.
관련 설계: MOLD_DX_AGENT_DESIGN.md §6
"""
from typing import Callable, TypeVar

import ollama
from pydantic import BaseModel, ValidationError

MODEL = "gemma4:31b"

_OPTIONS = {
    "temperature": 0.7,       # 호출 시 덮어씀
    "num_ctx": 32768,
    "repeat_penalty": 1.2,
}

T = TypeVar("T", bound=BaseModel)


class ConvergenceError(Exception):
    """재시도 한도까지 스키마 검증을 통과하지 못함. 해당 단위는 플래그 후 진행."""


def _call(system: str, user: str, temperature: float) -> str:
    """자유 텍스트 생성. 기존 book_writer._call과 동일 동작."""
    res = ollama.chat(
        model=MODEL,
        options={**_OPTIONS, "temperature": temperature},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return res["message"]["content"]


def call_structured(
    system: str,
    user: str,
    schema: type[T],
    temperature: float,
    retries: int = 2,
    post_validate: Callable[[T], T] | None = None,
) -> T:
    """
    스키마를 강제(ollama format=)하고 검증한다. 실패하면 에러를 모델에 되먹여 재시도.

    post_validate: 스키마만으로 못 잡는 코드 검증 훅(예: Planner.data_refs를
                   digest.flatten_keys()와 대조). 실패 시 예외를 던지면 같은
                   루프에서 self-heal 재시도된다.
    """
    msg = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    last_err: Exception | None = None

    for attempt in range(retries + 1):
        raw = ollama.chat(
            model=MODEL,
            format=schema.model_json_schema(),     # ★ 구조화 출력 강제
            options={**_OPTIONS, "temperature": temperature},
            messages=msg,
        )["message"]["content"]

        try:
            obj = schema.model_validate_json(raw)              # ① 스키마 검증
            return post_validate(obj) if post_validate else obj  # ② 코드 검증(선택)
        except (ValidationError, ValueError) as e:
            last_err = e
            msg.append({"role": "assistant", "content": raw})
            msg.append({
                "role": "user",
                "content": f"검증 실패:\n{e}\n같은 JSON 스키마를 정확히 지켜 다시 작성하세요.",
            })

    raise ConvergenceError(f"{schema.__name__} 미수렴 ({retries + 1}회 시도): {last_err}")

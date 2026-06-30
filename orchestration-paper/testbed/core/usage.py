"""LLM 토큰 사용량 집계 (오케스트레이션 비교 실험 지표용).

토큰은 두 경로에서 발생한다:
  1) 직접 ollama.chat 호출 (design/review 등) → llm.py가 METER.add()로 기록
  2) ADK LlmAgent(write/revise, LiteLlm) → 오케스트레이터가 실행 중
     event.usage_metadata 를 합산

per-chapter 측정 방법:
    from core.usage import METER
    METER.reset()
    ... 챕터 실행(직접 호출은 자동 누적) ...
    direct = METER.snapshot()          # 직접 호출 토큰
    # + 오케스트레이터가 모은 event 토큰
"""
from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class Usage:
    prompt: int = 0
    completion: int = 0
    calls: int = 0

    @property
    def total(self) -> int:
        return self.prompt + self.completion

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(self.prompt + other.prompt,
                     self.completion + other.completion,
                     self.calls + other.calls)


class TokenMeter:
    """프로세스 전역 토큰 누적기 (thread-safe)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._u = Usage()

    def add(self, prompt, completion) -> None:
        with self._lock:
            self._u.prompt += int(prompt or 0)
            self._u.completion += int(completion or 0)
            self._u.calls += 1

    def reset(self) -> None:
        with self._lock:
            self._u = Usage()

    def snapshot(self) -> Usage:
        with self._lock:
            return Usage(self._u.prompt, self._u.completion, self._u.calls)


# 전역 싱글턴 — llm.py(직접 호출)가 여기에 기록한다.
METER = TokenMeter()

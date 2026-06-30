"""LLM 토큰 사용량 집계 (비용/지표용).

paper-agent 는 모델이 2개(생성/검수)라 모델별로도 나눠 집계한다.
    from core.usage import METER
    METER.reset()
    ... 실행 ...
    snap = METER.snapshot()        # 전체
    by   = METER.by_model()        # {모델명: Usage}
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field


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
    """프로세스 전역 토큰 누적기 (thread-safe). 모델별 분리 집계."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._u = Usage()
        self._by: dict[str, Usage] = {}

    def add(self, prompt, completion, model: str | None = None) -> None:
        with self._lock:
            p, c = int(prompt or 0), int(completion or 0)
            self._u.prompt += p
            self._u.completion += c
            self._u.calls += 1
            key = model or "?"
            u = self._by.setdefault(key, Usage())
            u.prompt += p
            u.completion += c
            u.calls += 1

    def reset(self) -> None:
        with self._lock:
            self._u = Usage()
            self._by = {}

    def snapshot(self) -> Usage:
        with self._lock:
            return Usage(self._u.prompt, self._u.completion, self._u.calls)

    def by_model(self) -> dict[str, Usage]:
        with self._lock:
            return {k: Usage(v.prompt, v.completion, v.calls) for k, v in self._by.items()}


# 전역 싱글턴 — llm.py(직접 호출)가 여기에 기록한다.
METER = TokenMeter()

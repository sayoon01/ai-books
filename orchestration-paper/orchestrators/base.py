"""오케스트레이터 공통 인터페이스.

세 구조(Code/LLM/Hybrid)는 모두 이 인터페이스를 구현하며, 같은 입력
(챕터 + base_state)을 받아 같은 형태의 Result(산출물 + 지표)를 반환한다.
오직 '흐름 제어 주체'만 다르게 하여 변인을 통제한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Result:
    """한 챕터 1회 실행 결과 + 지표."""
    orchestrator: str                 # "code" | "llm" | "hybrid"
    draft: str                        # 최종 산출물
    elapsed_sec: float                # 실행 시간
    write_count: int                  # 재작성 횟수
    pass_count: int                   # 재검토(패스) 횟수
    best_score: int | None = None     # 게이트 점수(있으면)
    tokens: int | None = None         # 총 토큰 사용량 (direct + event)
    token_detail: dict = field(default_factory=dict)  # {direct, event, prompt, completion}
    chars: int = 0                    # 산출물 길이
    history: list = field(default_factory=list)

    @property
    def retry_count(self) -> int:
        return (self.write_count or 0) + (self.pass_count or 0)


class Orchestrator:
    """모든 오케스트레이터의 베이스. run()만 구현하면 된다."""
    name: str = "base"

    async def run(self, chapter: dict[str, Any], base_state: dict[str, Any]) -> Result:
        """챕터 1개를 생성하고 Result를 반환한다.

        chapter:    design.json의 챕터 항목 ({"number","title","description",...})
        base_state: 공유 상태 (config, write_brief, grounding 등)
        """
        raise NotImplementedError


# 모든 구조가 동일한 초기 카운터로 시작하도록 하는 헬퍼.
def initial_state(base_state: dict, chapter: dict, prev_summaries: list[str] | None = None) -> dict:
    return {
        **base_state,
        "chapter": chapter,
        "prev_summaries": list(prev_summaries or []),
        "last_score": -1,
        "best_score": -1,
        "write_count": 0,
        "pass_count": 0,
        "history": [],
    }

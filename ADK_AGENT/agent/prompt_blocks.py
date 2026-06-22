"""
프롬프트 빌딩 블록 — 여러 단계가 '공유'하는 조각만 모은다.

각 단계의 SYSTEM 프롬프트·user 빌더는 해당 단계 파일로 옮겼다:
  - design  → agent/design.py  (DESIGN_SYS, design_user)
  - write   → agent/write.py   (WRITE_OUTPUT_POLICY)
  - review  → agent/review.py  (REVIEW_SYSTEM, review_user)
  - revise  → agent/revise.py  (REVISE_SYSTEM)

여기에는 write/review/revise 가 공통으로 쓰는 일반 블록 헬퍼만 남긴다(block/prev_block/chapter_block).
grounding 전용 ground_block 은 core/grounding.py 로 옮겼다(grounding 관련을 한 곳에).
조립(ctx.state → 최종 프롬프트)은 각 노드가 한다. 여기는 순수 문자열/함수만.
"""
import json


def block(label: str, content: str | None) -> str:
    """내용이 있으면 라벨 블록으로 감싼다. 없으면 빈 문자열."""
    if not content:
        return ""
    return f"\n[{label}]\n{content}\n"


def prev_block(previous_summaries) -> str:
    if not previous_summaries:
        return ""
    return "\n[이전 내용 요약]\n" + "\n".join(previous_summaries) + "\n"


def chapter_block(chapter: dict) -> str:
    """현재 챕터(JSON) 블록. write/revise instruction 공용."""
    return block("이번 챕터", json.dumps(chapter, ensure_ascii=False, indent=2))

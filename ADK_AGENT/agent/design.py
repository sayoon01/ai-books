"""
Design 단계 — 책 구조(chapters) + 집필 지시문(write_brief) + 소스 다이제스트.

산출물은 output/<slug>/design.json 에 저장되어 추후 웹 UI 가 편집할 수 있다(설계 §3-1).
규칙: "있으면 로드, 없으면 생성". 로드한 값도 DesignPlan 으로 재검증해 편집 실수를 막는다.
챕터당 반복이 아닌 책당 1회라 그래프 없이 파이썬에서 call_structured 직접 호출.
"""
import json
from pathlib import Path

from core.llm import call_structured
from agent.prompts import DESIGN_SYS, design_user
from agent.schemas import DesignPlan

DEFAULT_CHAPTER_COUNT = 10


def _fill_numbers(plan: DesignPlan) -> DesignPlan:
    for i, ch in enumerate(plan.chapters, 1):
        if not ch.number:
            ch.number = i
    return plan


def run_or_load_design(config: dict, source_text: str, output_dir: Path, *,
                       force: bool = False, n: int = DEFAULT_CHAPTER_COUNT) -> dict:
    """design.json 이 있으면 로드(재검증), 없으면 생성·저장. dict(DesignPlan dump) 반환."""
    output_dir.mkdir(parents=True, exist_ok=True)
    design_path = output_dir / "design.json"

    if design_path.exists() and not force:
        data = json.loads(design_path.read_text(encoding="utf-8"))
        plan = _fill_numbers(DesignPlan(**data))            # 웹 편집본 재검증
        print(f"  [design] 기존 design.json 로드 (챕터 {len(plan.chapters)}개)")
        return plan.model_dump()

    src = "소스 자료" if source_text else "책 설명(description)"
    print(f"  [design] {src} 기반 설계 생성 중...")
    plan = _fill_numbers(
        call_structured(DESIGN_SYS, design_user(config, source_text, n), DesignPlan, 0.3))
    design_path.write_text(
        json.dumps(plan.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [design] 생성 완료 → design.json (챕터 {len(plan.chapters)}개, "
          f"write_brief {len(plan.write_brief)}자, digest {len(plan.grounding_digest)}자)")
    return plan.model_dump()

"""
Design 단계 — 책 구조(chapters) + 집필 지시문(write_brief) + 소스 다이제스트.

산출물은 output/<slug>/design.json 에 저장되어 추후 웹 UI 가 편집할 수 있다(설계 §3-1).
규칙: "있으면 로드, 없으면 생성". 로드한 값도 DesignPlan 으로 재검증해 편집 실수를 막는다.
챕터당 반복이 아닌 책당 1회라 그래프 없이 파이썬에서 call_structured 직접 호출.
"""
import json
from pathlib import Path

from core.llm import call_parsed
from core.config import DEFAULT_CHAPTER_COUNT
from agent.common import DesignPlan


# =========================
# DESIGN 프롬프트 — 책 구조 + 집필 지시문 + 소스 다이제스트 생성
# =========================
DESIGN_SYS = """
당신은 책/문서의 설계자입니다. 주어진 책 설정(독자·문체·설명)과, 있다면 소스 자료를 읽고
이후 집필에 쓸 세 가지를 한 번에 설계하세요.

1) chapters: 이 책에 가장 적합한 챕터 목차.
   - 소스 자료가 있으면 그 핵심 주제·흐름을 우선 반영(충돌·이탈 금지). 없으면 description과 일반 지식으로.
   - 앞→뒤로 자연스럽게 누적되는 학습/논리 흐름. 각 챕터에 제목과 한두 문장 description.
   - 입력에 chapters가 이미 있으면 그것을 존중해 정제만 하세요(개수·핵심 유지).

2) write_brief: 이 책 '전용 집필 지시문'. 이후 집필자(Writer)에게 그대로 전달됩니다.
   - 이 책의 톤·목소리, 독자 수준, 구성 관례(소제목 흐름·분량 배분·예시 사용법),
     소스 자료 활용 방식을 한 덩어리의 지시문으로 작성하세요.
   - 추상적 원칙이 아니라 "이 책을 어떻게 쓸지"가 보이는 구체적 지시여야 합니다.

3) grounding_digest: 소스 자료가 있으면, 집필에 실제로 필요한 핵심(용어·수치·사례·관점)만
   추려 정리하세요. 원문을 그대로 복사하지 말고 집필용으로 압축하세요. 소스가 없으면 빈 문자열.

출력 형식 — 아래 JSON 객체 하나만 출력하세요(설명·잡담·코드펜스 없이 JSON만):
{
  "chapters": [{"number": 1, "title": "챕터 제목", "description": "한두 문장 설명"}],
  "write_brief": "집필 지시문 한 덩어리",
  "grounding_digest": "소스 핵심 요약(소스 없으면 빈 문자열)"
}
주의: 같은 단어·문장을 반복하지 말고 간결하게 쓰세요. 문자열 안에서 큰따옴표는 이스케이프하세요.
"""


def design_user(config: dict, source_text: str = "", n: int = 10) -> str:
    has_src = bool(source_text)
    src_note = (f"\n소스 자료(아래 내용을 해석·압축해 grounding_digest로):\n{source_text}\n"
                if has_src else "\n(소스 자료 없음 → grounding_digest는 빈 문자열)\n")
    chap_note = (f"챕터 목차를 정확히 {n}개 설계하세요."
                 if not config.get("chapters")
                 else "입력 chapters를 존중해 정제하세요(개수·핵심 유지).")
    return f"""
책 설정:
{json.dumps(config, ensure_ascii=False, indent=2)}
{src_note}
{chap_note}
위 설정(과 소스)에 맞춰 chapters / write_brief / grounding_digest 를 JSON으로 출력하세요.
"""


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
        call_parsed(DESIGN_SYS, design_user(config, source_text, n), DesignPlan, 0.3))
    design_path.write_text(
        json.dumps(plan.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [design] 생성 완료 → design.json (챕터 {len(plan.chapters)}개, "
          f"write_brief {len(plan.write_brief)}자, digest {len(plan.grounding_digest)}자)")
    return plan.model_dump()

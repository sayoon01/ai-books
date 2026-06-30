"""
① Plan agent — 논문 설계자.

입력(주제·연구내용·있으면 실측 자료) → PaperPlan(plan.json):
  설계 계획 + 실험 계획 + 섹션별 작성 계획 + 표/그림/통계 계획.
규칙: "있으면 로드, 없으면 생성". 로드본도 PaperPlan 으로 재검증(편집 실수 방지).
책당 1회라 그래프 없이 call_parsed 직접 호출(대형 리스트 스키마라 parsed 가 안정적).
"""
import json
from pathlib import Path

from core.llm import call_parsed
from core.config import T_PLAN
from agents.common import PaperPlan


PLAN_SYS = """
당신은 논문 설계자입니다. 주어진 연구 주제·내용과, 있다면 실측 자료를 읽고
논문 한 편의 설계를 한 번에 짜세요. 산출물은 이후 집필(Writer)의 청사진이 됩니다.

다섯 가지를 설계하세요.

1) title / contributions: 논문 제목과 핵심 기여(주장) 목록.
   - 기여는 막연한 포부가 아니라 "결과로 뒷받침 가능한" 구체적 주장이어야 합니다.

2) research_design: 연구 설계 — 무엇을, 무엇과, 어떻게 비교/검증하는가.
   가설·독립변인·통제변인·평가 관점을 한 덩어리로.

3) experiment_plan: 실험 계획 — 데이터셋/입력, 조건(비교 대상), 반복 횟수, 평가지표.
   실측 자료가 있으면 그 구조(어떤 값이 있는지)에 맞춰 현실적으로.

4) sections: 논문 섹션 목차. 각 섹션마다
   - id(영문 소문자), title, role(이 섹션의 역할), key_points, write_brief(섹션 전용 집필 지시).
   - 일반적 순서: abstract → introduction → related_work → method → experiment →
     results → discussion → conclusion. 주제에 맞게 가감하세요.
   - 섹션마다 성격이 다릅니다(초록=압축 요약, method=재현가능 기술, results=수치+해석).
     write_brief 에 그 성격을 구체적으로 적으세요.

5) artifacts: 만들 표/그림/통계 목록(자료 계획). 각 항목마다
   - id(예 fig:cost, tab:main, stat:ttest), kind(figure/table/stat), title, purpose(뒷받침할 주장),
     data_source(어느 데이터에서), method(만드는 법: 차트 종류/통계 검정), section_id(들어갈 섹션).
   - ★ 중요: 여기서는 "무엇을 만들지"만 정하고 수치는 절대 지어내지 마세요.
     실제 값은 별도 단계가 데이터에서 생성합니다.
   - 각 섹션의 artifact_ids 는 이 목록의 id 를 참조하게 일관되게 맞추세요.

출력 형식 — 아래 JSON 객체 하나만(설명·코드펜스 없이 JSON만):
{
  "title": "...", "venue": "...", "abstract_brief": "...",
  "contributions": ["..."],
  "research_design": "...", "experiment_plan": "...",
  "sections": [{"id":"intro","title":"Introduction","role":"...","key_points":["..."],
                "write_brief":"...","artifact_ids":["fig:cost"]}],
  "artifacts": [{"id":"fig:cost","kind":"figure","title":"...","purpose":"...",
                 "data_source":"...","method":"...","section_id":"results"}]
}
주의: 같은 문장을 반복하지 말고 간결하게. 문자열 안 큰따옴표는 이스케이프하세요.
"""


def plan_user(topic: str, source_text: str = "", venue: str = "") -> str:
    has_src = bool(source_text)
    src_note = (f"\n실측 자료(이 구조·값에 맞춰 실험계획과 artifacts 를 설계):\n{source_text}\n"
                if has_src
                else "\n(실측 자료 없음 → experiment_plan 은 계획 수준으로, artifacts 는 만들 목록만)\n")
    venue_note = f"대상 학회/저널: {venue} (이 기준으로 문체·분량·섹션 구성)\n" if venue else ""
    return f"""
연구 주제/내용:
{topic}
{venue_note}{src_note}
위 내용에 맞춰 논문 설계(PaperPlan)를 JSON 으로 출력하세요.
"""


def run_or_load_plan(topic: str, source_text: str, output_dir: Path, *,
                     venue: str = "", force: bool = False) -> dict:
    """plan.json 있으면 로드(재검증), 없으면 생성·저장. dict(PaperPlan dump) 반환."""
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "plan.json"

    if plan_path.exists() and not force:
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        plan = PaperPlan(**data)                       # 편집본 재검증
        print(f"  [plan] 기존 plan.json 로드 (섹션 {len(plan.sections)}개, "
              f"자료 {len(plan.artifacts)}개)")
        return plan.model_dump()

    src = "실측 자료" if source_text else "주제 설명"
    print(f"  [plan] {src} 기반 논문 설계 생성 중...")
    plan = call_parsed(PLAN_SYS, plan_user(topic, source_text, venue), PaperPlan, T_PLAN)
    plan_path.write_text(
        json.dumps(plan.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [plan] 생성 완료 → plan.json "
          f"(섹션 {len(plan.sections)}개, 자료 {len(plan.artifacts)}개, "
          f"기여 {len(plan.contributions)}개)")
    return plan.model_dump()

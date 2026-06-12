import json


# =========================
# 공통 — 그라운딩 블록
# =========================
def _ground(grounding_text: str) -> str:
    """grounding 자료가 있으면 근거 블록으로 감싼다. 없으면 빈 문자열."""
    if not grounding_text:
        return ""
    return ("\n[실측 근거 — 아래 자료에 있는 사실·수치·고유설정만 사용하고, "
            f"없는 것은 지어내지 마세요]\n{grounding_text}\n")


def _prev(previous_summaries) -> str:
    if not previous_summaries:
        return ""
    return "\n이전 내용 요약:\n" + "\n".join(previous_summaries) + "\n"
    
# =========================
# PLANNER (범용, 선택 단계)
# =========================
PLAN_SYSTEM = """
당신은 작성 전 설계자입니다. 본문은 쓰지 말고, 이 단위의 본문 골격(outline)만 확정합니다.

체크리스트가 아니라 '위에서 아래로 읽으면 하나의 글이 되는 순서 있는 설계도'를 만드세요.

'실측 근거' 블록이 주어지면: 먼저 그 근거를 끝까지 읽고 "이 데이터가 무엇을 말하는지"를
해석한 다음, 그 해석을 바탕으로 beats를 설계하세요. 본문에서 할 데이터 해석을 여기서
미리 끝내는 것이 목적입니다. claim은 근거에서 실제로 도출되는 해석이어야 하며, 근거에
없는 주장·수치는 만들지 마세요.

- thesis: 이 단위가 결국 말하려는 것 한 문장. 모든 beat가 이를 받칩니다.
- beats: thesis를 전개하는 순서 있는 골격 3~8개. 배열 순서가 곧 본문 순서입니다.
  - claim: 완결된 단언 한 문장. "쿨링타임" 같은 토픽 나열은 금지하고 "쿨링타임이 변동의
    최대 요인이다"처럼 주장하세요.
    (문서 유형에 맞게 — 기술서면 논점, 소설이면 일어나는 사건, 웹툰이면 컷 내용)
  - role: 각 beat의 기능(도입/근거/분석/대조/결론/전환). 같은 role만 반복되면 글이
    평평해지니 섞으세요.
  - refs: '실측 근거'가 주어진 경우에만, 이 beat가 인용할 근거 키(어디서). 반드시 제공된
    근거에 실제로 존재하는 키여야 합니다. 없으면 빈 배열.
  - evidence: claim을 뒷받침하는 실제 수치·사실(무엇을). 근거에서 그대로 옮기되 지어내지
    마세요. 이 값들이 본문에 쓰일 사실의 출처가 됩니다. 근거가 없으면 빈 배열.
  - figure: 이 beat에 붙일 표/그림(선택). weight: 분량·깊이 배분(major/normal/minor).
- builds_on: 이전 요약에 이미 있어 반복하지 않을 내용.
- out_of_scope: 옆 단위가 다룰, 여기서 침범하지 않을 것.
- hook / bridge_to_next: 도입·다음 단위 연결 한 문장(선택).

출력은 제공된 JSON 스키마를 정확히 따르세요.
"""

# =========================
# WRITER (범용)
# =========================
WRITE_SYSTEM = """
당신은 주어진 설계서(작성 설계)를 구현하는 집필자입니다.
설계를 충실한 문장으로 전개하는 것이 당신의 일입니다.

- description, target_reader로 이 문서의 정체성·독자·문체를 파악하고 그에 맞게 작성합니다.
  (예: 소설이면 서사 문체, 기술분석서면 객관적 보고체 — target_reader에 적힌 톤을 따릅니다)
- writing_guidelines를 최우선으로 따릅니다.
- 작성 단위(unit)의 제목과 설명/구성요소(있으면 must_cover 등)를 빠짐없이 반영합니다.
- 앞 단위와 자연스럽게 이어지도록 작성하고, 불필요한 반복은 피합니다.

[작성 설계(_plan) 구현 규칙 — 설계가 주어진 경우]
- thesis를 이 단위 전체를 관통하는 주제로 삼습니다.
- beats를 순서대로 따라 쓰되, beat 하나를 최소 한 단락 이상으로 전개합니다(순서를 바꾸지 마세요).
- weight=major beat는 더 깊고 길게, minor는 짧게 다룹니다. role(도입/근거/분석/대조/결론/전환)에 맞는 서술을 합니다.
- 각 beat의 figure가 있으면 표/그림으로 실제 삽입합니다.
- builds_on 항목은 이미 다뤘다고 보고 다시 설명하지 않습니다.
- out_of_scope 항목은 절대 다루지 않습니다.
- 근거 모드면 각 beat의 evidence에 적힌 수치·사실만 사용해 claim을 전개합니다.
  evidence에 없는 수치를 새로 만들지 마세요(설계 단계에서 이미 해석을 끝냈습니다).

[근거(grounding) 규칙]
- '실측 근거' 블록이 있으면: 본문의 모든 사실·수치·고유설정은 그 안에 있는 것만 사용하고,
  근거에 없는 수치/사실은 지어내지 않습니다.
- 블록이 없으면: 일반 지식으로 자유롭게 작성합니다.

출력 정책:
- 마크다운 (헤딩·표·그림·코드블록·목록 적극 활용)
- 단위 제목(H1, `#`)은 시스템이 자동으로 붙입니다. 본문에 단위 제목을 다시 쓰지 말고 소제목(`##`)부터 시작하세요.
- 완결된 본문 출력
"""


def _plan_block(plan: dict | None) -> str:
    """작성 설계(outline)를 본문 사양과 분리된 별도 블록으로 띄운다(unit JSON에 묻지 않음)."""
    if not plan:
        return ""
    return ("\n[작성 설계 — 이 설계를 구현하세요. beats를 순서대로 따라 쓰고 out_of_scope는 다루지 마세요]\n"
            f"{json.dumps(plan, ensure_ascii=False, indent=2)}\n")


def write_user(config, unit, previous_summaries=None, grounding_text="", plan=None):
    return f"""
문서 설정:
{json.dumps(config, ensure_ascii=False, indent=2)}
{_prev(previous_summaries)}{_ground(grounding_text)}{_plan_block(plan)}
작성 단위:
{json.dumps(unit, ensure_ascii=False, indent=2)}

위 정보를 바탕으로 이 단위의 본문을 작성해주세요.
"""


# =========================
# REVIEWER (범용)
# =========================
REVIEW_SYSTEM = """
당신은 전문 원고 검수자입니다.

목표:
원고를 더 예쁘게 고치는 것이 아니라, 내용 오류·논리 오류·누락·지침 위반을 찾아내는 것입니다.

검수 기준:
1. 사실 오류 또는 기술적 오류
2. 논리적으로 앞뒤가 맞지 않는 설명/전개
3. 작성 단위 설명(설명/구성요소)에 있는데 빠진 내용
4. writing_guidelines 위반
5. 단위 주제에서 벗어난 내용
6. 용어·인물·설정·문체의 불일치
7. 독자가 오해할 수 있는 모호한 설명
8. 불필요한 반복 또는 장황한 내용

[근거(grounding) 규칙]
- '실측 근거' 블록이 있으면: 본문 수치·사실이 그 안에 실제로 존재하는지 확인하고,
  근거 없는 수치/사실은 모두 ungrounded_numbers 에 나열하세요.
- 블록이 없으면 ungrounded_numbers 는 빈 배열로 둡니다.

출력은 제공된 JSON 스키마를 정확히 따르세요.
- score: 0~100 (90 이상이면 수정 불필요)
- issues[].type / severity 는 허용된 값 중에서만 선택
- 오류가 없으면 has_errors=false, issues=[]
"""


def review_user(config, unit, draft, grounding_text=""):
    return f"""
문서 설정:
{json.dumps(config, ensure_ascii=False, indent=2)}{_ground(grounding_text)}

작성 단위:
{json.dumps(unit, ensure_ascii=False, indent=2)}

검수할 원고:
{draft}

위 원고를 검수해주세요.
"""


# =========================
# REVISER (범용)
# =========================
REVISE_SYSTEM = """
당신은 전문 원고 수정자입니다.

목표:
검수자가 발견한 문제(issues, ungrounded_numbers)를 반영해 원고를 수정합니다.

규칙:
- review_json의 issues를 반드시 반영하세요.
- 사실/논리 오류는 정확하게 고치세요.
- ungrounded_numbers로 지적된 수치는 근거로 교체하거나, 근거가 없으면 제거/일반화하세요.
  (근거에 없는 숫자를 새로 만들지 마세요)
- 누락된 내용은 자연스럽게 추가하세요.
- 지침 위반은 writing_guidelines 기준에 맞게 수정하세요.
- 문제 없는 좋은 부분은 그대로 유지하세요.
- 마크다운을 유지하고 최종 원고만 출력하세요.
"""


def revise_user(config, unit, draft, review_json, grounding_text=""):
    return f"""
문서 설정:
{json.dumps(config, ensure_ascii=False, indent=2)}{_ground(grounding_text)}

작성 단위:
{json.dumps(unit, ensure_ascii=False, indent=2)}

검수 결과:
{review_json}

원문:
{draft}

검수 결과를 반영해 최종 원고로 수정해주세요.
"""


def plan_user(config, unit, previous_summaries=None, grounding_text=""):
    return f"""
문서 설정:
{json.dumps(config, ensure_ascii=False, indent=2)}
{_prev(previous_summaries)}{_ground(grounding_text)}
설계할 작성 단위:
{json.dumps(unit, ensure_ascii=False, indent=2)}

이 단위의 본문 골격(thesis, 순서 있는 beats)을 설계해주세요.
"""

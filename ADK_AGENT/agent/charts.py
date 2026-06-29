"""
차트 디자이너 — grounding_digest의 표를 보고 '어떤 차트를 어디에' 넣을지 제안한다.

하이브리드 자동화의 '제안' 부분:
  LLM은 차트의 구조(어느 표·어느 열·종류·대상 챕터·제목)만 정한다. 숫자는 만들지 않는다.
  → 제안된 각 스펙을 publish/charts.render_spec 으로 즉시 해소(렌더 시도)해 보고,
    표·열을 못 찾거나 비수치면 드롭한다. 살아남은 스펙만 design.json에 저장된다.
  소스에 표가 없으면 빈 리스트(소설 등 자동 제외).
"""
from __future__ import annotations

import json

from core.llm import call_parsed
from agent.common import FigurePlan
from publish.charts import render_spec, _iter_tables


DESIGNER_SYS = """
당신은 데이터 보고서의 '시각화 설계자'입니다. 주어진 참고자료(표 모음)와 챕터 목차를 보고,
독자의 이해를 돕는 차트들을 설계하세요. 당신은 '구조'만 정합니다 — 숫자는 절대 만들지 마세요.
숫자는 시스템이 표에서 직접 추출합니다.

규칙:
- 자료에 실제로 존재하는 표·열만 사용하세요(아래 '표 목록'의 헤더 이름을 그대로 쓰세요).
- 각 차트는 가장 관련 있는 챕터 번호에 배치하세요. 한 챕터에 1~2개가 적당합니다.
- 데이터 형태에 맞는 종류를 고르세요:
  · donut: 한 표의 전체 구성 비율(부분합/총계 표) — value_cols 1개(건수/비중)
  · barh : 항목별 한 지표 순위(많은 항목) — value_cols 1개
  · grouped_bar : 적은 범주의 2~3개 지표 비교 — value_cols 2~3개
  · stacked100 : 항목별 구성요소 비율(여러 유형 열) — value_cols 여러 개(각 유형)
  · line : 시간/연도 추이 — label_col이 시간축
  · scatter : 두 지표 상관 — value_cols=[x열, y열]
- label_col/value_cols 는 반드시 해당 표 헤더의 이름과 일치(또는 부분일치)해야 합니다.
- title/caption 은 자료의 언어로 간결하게.

출력 — JSON 객체 하나만(설명·코드펜스 없이):
{
  "figures": [
    {"chapter": 2, "type": "barh", "title": "...", "caption": "...",
     "table": "표를 찾을 키워드(표 제목 일부)", "label_col": "헤더명",
     "value_cols": ["헤더명"], "top_n": 0, "sort": true}
  ]
}
"""


def _table_catalog(digest: str, max_rows_preview: int = 3) -> str:
    """digest의 표들을 'LLM이 고르기 쉽게' 헤더+직전문맥+샘플행으로 요약."""
    out = []
    for idx, (header, rows, ctx) in enumerate(_iter_tables(digest), 1):
        sample = rows[:max_rows_preview]
        out.append(f"[표 {idx}] 문맥: {ctx or '(없음)'}")
        out.append("  헤더: " + " | ".join(header))
        for r in sample:
            out.append("  예시: " + " | ".join(r))
    return "\n".join(out)


def _designer_user(config: dict, chapters: list[dict], digest: str) -> str:
    lang = config.get("language", "ko")
    chap = "\n".join(f"- {c.get('number')}. {c.get('title')}: {c.get('description','')}"
                     for c in chapters)
    return f"""
문서 언어: {lang}

[챕터 목차]
{chap}

[참고자료 표 목록] — 아래 표·헤더 이름만 사용하세요. (숫자는 시스템이 추출)
{_table_catalog(digest)}

위 표들 중 각 챕터에 가장 적합한 것을 골라 차트를 설계해 JSON으로 출력하세요.
표가 적으면 차트도 적게(억지로 만들지 말 것). 표가 없으면 figures를 빈 배열로 두세요.
"""


def propose_figures(config: dict, chapters: list[dict], digest: str) -> list[dict]:
    """digest 표 기반 차트 스펙 리스트(dict) 반환. 해소 안 되는 스펙은 드롭."""
    if not digest or not list(_iter_tables(digest)):
        return []
    try:
        plan = call_parsed(DESIGNER_SYS, _designer_user(config, chapters, digest),
                           FigurePlan, 0.3)
    except Exception as e:
        print(f"  [charts] 디자이너 실패(차트 없이 진행): {e}")
        return []

    valid, dropped = [], 0
    chap_nums = {c.get("number") for c in chapters}
    for spec in plan.figures:
        d = spec.model_dump()
        if d["chapter"] not in chap_nums:
            dropped += 1
            continue
        if render_spec(d, digest) is None:        # 표/열 해소 검증(실제 렌더 시도)
            dropped += 1
            continue
        valid.append(d)
    print(f"  [charts] 차트 제안 {len(plan.figures)}개 → 유효 {len(valid)}개"
          + (f" (드롭 {dropped})" if dropped else ""))
    return valid

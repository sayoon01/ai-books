"""
금형 사출 통계 digest 빌더 — 대표 보고용 3장 문서의 grounding 소스 생성.

왜 필요한가:
  대시보드 루트(:33001/)를 source 로 직접 걸면 trafilatura 추출 결과에 라벨만 남고
  실제 수치는 전부 '—'(JS가 API로 채움)다. 게다가 generator 의 unverified_numbers 가
  자료에 없는 숫자를 전부 환각으로 차단한다. → 통계 보고서는 한 줄도 통과 못 한다.
  그래서 API JSON 을 직접 호출해 '인용 가능한 실측 숫자'만 담은 digest 를 만들어,
  toc 의 source 로 이 파일을 가리킨다.

원칙:
  - LLM 에 517k 원본을 넣지 않는다. 코드가 집계(digest)로 압축해 주입한다.
  - 두 종류의 '에러'를 분리한다: (A) 센서/데이터 품질 에러  (B) 생산 이상(anomaly).
  - 시간축은 stratified 샘플인 /api/cycles 가 아니라, 정확 집계인 /api/shift-stats 를 쓴다.
  - read_source 의 절단 한도(MAX_FILE_CHARS, 기본 12,000자) 안에 들어오게 압축한다.

실행:
  .venv/bin/python tools/build_mold_digest.py            # data/mold-stats-digest.md 생성
  .venv/bin/python tools/build_mold_digest.py --out X.md  # 출력 경로 지정
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

BASE = "http://keti-ev1.iptime.org:33001"
ADK_ROOT = Path(__file__).resolve().parent.parent              # ADK_AGENT/
REPO_ROOT = ADK_ROOT.parent                                    # ai-books/
DEFAULT_OUT = REPO_ROOT / "data" / "mold-stats-digest.md"
# 대표 보고 문서의 design.json (main.py 가 toc 제목으로 만든 슬러그)
DEFAULT_DESIGN = ADK_ROOT / "output" / "금형-사출-생산-데이터-분석-대표-보고" / "design.json"

# 사이클 분류: 무엇이 '센서/데이터 품질 에러'인가.
SENSOR_ERR_TYPES = ("SENSOR_NO_SIGNAL", "SENSOR_ERROR")


def fetch(path: str) -> dict | list:
    """평문 HTTP 로 API JSON 호출. (외부 fetch 도구는 HTTPS 강제 업그레이드라 :33001 차단됨)"""
    r = httpx.get(f"{BASE}{path}", timeout=30.0, follow_redirects=True)
    r.raise_for_status()
    return r.json()


def pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 2) if whole else 0.0


def fmt(n) -> str:
    """정수는 천단위 콤마, 실수는 그대로."""
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    return f"{n:,}" if isinstance(n, int) else f"{n}"


def build() -> str:
    summary = fetch("/api/summary")
    shift = fetch("/api/shift-stats")
    proc = fetch("/api/proc-stats")
    cihist = fetch("/api/ci-hist")
    trend = fetch("/api/sensor-trend")

    L: list[str] = []
    w = L.append

    total = summary["total_cycles"]
    dist = summary["cycle_type_dist"]
    anomaly_total = summary["anomaly_total"]
    ci_mean = summary["ci_overall_mean"]
    molds = summary["mold_models"]
    normal = dist.get("NORMAL", 0)

    # 기간(전 금형 dates 의 최소~최대) — YYMMDD → YYYY-MM-DD
    all_dates = sorted({d for m in molds.values() for d in m.get("dates", [])})
    def yymmdd(s: str) -> str:
        return f"20{s[:2]}-{s[2:4]}-{s[4:6]}" if len(s) == 6 else s
    period = f"{yymmdd(all_dates[0])} ~ {yymmdd(all_dates[-1])}" if all_dates else "미상"
    active_days = len(all_dates)

    sensor_err = sum(dist.get(t, 0) for t in SENSOR_ERR_TYPES)

    # ── 0. 메타 ──────────────────────────────────────────────────────
    w("# 금형 사출 데이터 통계 digest (대표 보고용)")
    w("")
    w(f"- 데이터 갱신 시각: {summary.get('updated_at', '미상')}")
    w(f"- 집계 출처: KETI 금형 사출 AI 분석 시스템 API ({BASE})")
    w("- 본 digest 의 모든 수치는 실측 집계값이다. 본문은 이 값만 인용한다.")
    w("")

    # ── 1. 총괄 KPI ──────────────────────────────────────────────────
    w("## 1. 생산 총괄 (전체 기간)")
    w("")
    w(f"- 총 수집 사이클: {fmt(total)} 회")
    w(f"- 집계 기간: {period} (가동 기록일수 {fmt(active_days)}일)")
    w(f"- 가동 금형: {len(molds)} 종")
    w(f"- 평균 사이클 타임(가동 간격): {ci_mean:.1f} 초")
    w("")
    w("사이클 유형 분포(전체 대비):")
    w("")
    w("| 유형 | 건수 | 비중 |")
    w("|---|---|---|")
    label = {
        "NORMAL": "NORMAL(분석대상 정상)",
        "SENSOR_NO_SIGNAL": "SENSOR_NO_SIGNAL(센서 미연결)",
        "SENSOR_ERROR": "SENSOR_ERROR(센서 오류)",
        "IDLE": "IDLE(비가동)",
        "WARMUP": "WARMUP(예열)",
    }
    for k, v in sorted(dist.items(), key=lambda x: -x[1]):
        w(f"| {label.get(k, k)} | {fmt(v)} | {pct(v, total)}% |")
    w("")

    # ── 2. 두 가지 '에러'의 분리 정의 ──────────────────────────────────
    w("## 2. 두 가지 '에러'의 정의와 수치 (혼동 금지)")
    w("")
    w("'에러율'은 성격이 전혀 다른 두 지표가 있다. 보고 시 반드시 구분한다.")
    w("")
    w("### (A) 센서/데이터 품질 에러 — 데이터 수집 안정성 지표")
    w(f"- 정의: SENSOR_NO_SIGNAL(센서 미연결) + SENSOR_ERROR(센서 오류).")
    w(f"- 건수: {fmt(sensor_err)} 회 = 전체 {fmt(total)} 중 {pct(sensor_err, total)}%")
    w(f"  - SENSOR_NO_SIGNAL: {fmt(dist.get('SENSOR_NO_SIGNAL', 0))} ({pct(dist.get('SENSOR_NO_SIGNAL', 0), total)}%)")
    w(f"  - SENSOR_ERROR: {fmt(dist.get('SENSOR_ERROR', 0))} ({pct(dist.get('SENSOR_ERROR', 0), total)}%)")
    w("- 해석: 제품 불량이 아니라 '센서 신호가 끊기거나 0으로 들어온' 데이터 품질 문제다.")
    w("  케이블·커넥터 점검, 센서 장착 상태 관리의 대상이다.")
    w("")
    w("### (B) 생산 이상(anomaly) — 양산 품질 지표")
    w(f"- 정의: NORMAL(분석대상) 사이클 중 AI(Isolation Forest)가 이상으로 판정한 사이클.")
    w(f"- 건수: {fmt(anomaly_total)} 회")
    w(f"- 이상률: 분석대상(NORMAL) {fmt(normal)} 중 {pct(anomaly_total, normal)}%")
    w("- 해석: 온도·압력·사이클타임 패턴이 정상 분포에서 벗어난 '양산 품질 경보'다.")
    w("  실제 점검·조치의 우선 대상이다.")
    w("")

    # ── 3. 금형별 생산량 & 이상 랭킹 ──────────────────────────────────
    anomaly_by_mold = summary.get("anomaly_by_mold", {})
    # 금형별: NORMAL 수 = cycle_types['NORMAL'], 이상수 = anomaly_by_mold
    rows = []
    for name, m in molds.items():
        ct = m.get("cycle_types", {})
        nrm = ct.get("NORMAL", 0)
        tot = m.get("total_cycles", 0)
        anom = anomaly_by_mold.get(name, m.get("anomaly_count", 0))
        rows.append({
            "name": name,
            "total": tot,
            "normal": nrm,
            "anom": anom,
            "anom_rate": pct(anom, nrm),
            "ci": m.get("ci_mean_sec", 0),
            "sensor_err": sum(ct.get(t, 0) for t in SENSOR_ERR_TYPES),
        })

    w("## 3. 금형별 생산량 & 이상 (29종)")
    w("")
    w("### 3-1. 생산량 Top 10 (총 사이클 기준)")
    w("")
    w("| 금형 | 총사이클 | NORMAL | 평균CT(초) |")
    w("|---|---|---|---|")
    for r in sorted(rows, key=lambda x: -x["total"])[:10]:
        w(f"| {r['name']} | {fmt(r['total'])} | {fmt(r['normal'])} | {r['ci']:.1f} |")
    w("")
    w("### 3-2. 이상(anomaly) 다발 금형 Top 10 — 우선 점검 대상")
    w("")
    w("이상 건수 기준 정렬. 이상률 = 이상수 / 해당 금형 NORMAL 사이클.")
    w("")
    w("| 금형 | 이상건수 | NORMAL | 이상률 |")
    w("|---|---|---|---|")
    for r in sorted(rows, key=lambda x: -x["anom"])[:10]:
        w(f"| {r['name']} | {fmt(r['anom'])} | {fmt(r['normal'])} | {r['anom_rate']}% |")
    w("")
    w("### 3-3. 이상률(%) 높은 금형 Top 10 — NORMAL 200건 이상만")
    w("")
    w("(표본이 적은 금형의 비율 왜곡을 막기 위해 NORMAL 200건 이상으로 한정)")
    w("")
    w("| 금형 | 이상률 | 이상건수 | NORMAL |")
    w("|---|---|---|---|")
    qualified = [r for r in rows if r["normal"] >= 200]
    for r in sorted(qualified, key=lambda x: -x["anom_rate"])[:10]:
        w(f"| {r['name']} | {r['anom_rate']}% | {fmt(r['anom'])} | {fmt(r['normal'])} |")
    w("")
    w("주의: 다수 금형의 이상률이 5.0% 부근으로 수렴하는 것은 이상탐지 모델(Isolation "
      "Forest)의 contamination 설정(약 0.05) 천장에 닿은 것으로 보인다. 이 구간 값들은 "
      "'모델이 정상 분포 대비 가장 이질적인 사이클을 약 5%까지 표시'한 결과이므로, 금형 간 "
      "미세한 순위 차이를 절대적 우열로 단정하지 말 것. 실질적 차이는 3-2(이상 건수)가 더 명확하다.")
    w("")

    # ── 4. 시간 패턴: 요일 / 시간대 / 주야간 ──────────────────────────
    w("## 4. 시간 패턴별 업무량 & 이상률 (분석대상 NORMAL 기준)")
    w(f"")
    w(f"(아래는 정확 집계값. 모집단 normal_total = {fmt(shift.get('normal_total', normal))} 사이클)")
    w("")
    w("### 4-1. 요일별")
    w("")
    w("| 요일 | 사이클(업무량) | 이상건수 | 이상률 |")
    w("|---|---|---|---|")
    for d in shift.get("daily", []):
        w(f"| {d['name']} | {fmt(d['total'])} | {fmt(d['anomaly'])} | {d['rate']}% |")
    w("")
    w("### 4-2. 주간 vs 야간")
    w("")
    w("| 근무 | 사이클 | 이상건수 | 이상률 | 평균CT |")
    w("|---|---|---|---|---|")
    for s in shift.get("shifts", []):
        w(f"| {s['label']} | {fmt(s['total'])} | {fmt(s['anomaly'])} | {s['rate']}% | {s.get('ci_mean', 0):.1f} |")
    w("")
    # 시간대: 24행은 길다 → 이상률 최고/최저 3개씩만 추려 인용 가능 숫자로
    hourly = shift.get("hourly", [])
    if hourly:
        hi = sorted(hourly, key=lambda x: -x["rate"])[:3]
        lo = sorted(hourly, key=lambda x: x["rate"])[:3]
        w("### 4-3. 시간대(0~23시) 이상률 극값")
        w("")
        w("- 이상률 최고 시간대: " + ", ".join(f"{h['hour']}시 {h['rate']}%({fmt(h['anomaly'])}/{fmt(h['total'])})" for h in hi))
        w("- 이상률 최저 시간대: " + ", ".join(f"{h['hour']}시 {h['rate']}%({fmt(h['anomaly'])}/{fmt(h['total'])})" for h in lo))
        w("")

    # ── 5. 시간 흐름(시계열) 활동 추이 ────────────────────────────────
    w("## 5. 시간 흐름에 따른 가동·문제 추이")
    w("")
    # 5-1. 월별 가동(금형,일) 활동 — 실제 dates 기반 (워크로드의 달력 추이)
    from collections import Counter
    month_active = Counter()
    for m in molds.values():
        for d in m.get("dates", []):
            if len(d) == 6:
                month_active[f"20{d[:2]}-{d[2:4]}"] += 1
    if month_active:
        w("### 5-1. 월별 가동 활동량 (금형×가동일 합계, 워크로드 달력 추이)")
        w("")
        w("| 월 | 가동(금형·일) 건수 |")
        w("|---|---|")
        for mo in sorted(month_active):
            w(f"| {mo} | {fmt(month_active[mo])} |")
        w("")
    # 5-2. 양산 시작일(주력 금형) — 언제부터 본격 가동했는가
    psd = summary.get("prod_start_dates", {})
    if psd:
        w("### 5-2. 주력 금형 양산 시작일")
        w("")
        for name, dt in sorted(psd.items(), key=lambda x: x[1]):
            cnt = molds.get(name, {}).get("total_cycles", "-")
            w(f"- {name}: {dt} 양산 시작 (총 {fmt(cnt) if isinstance(cnt, int) else cnt} 사이클)")
        w("")

    # ── 6. 생산성: 사이클타임 / 공정시간 분포 ─────────────────────────
    w("## 6. 생산성 지표 (사이클타임·공정시간)")
    w("")
    w(f"- 사이클타임(CI) 중앙값 {cihist.get('p50', '-')}초, p25 {cihist.get('p25', '-')}초, "
      f"p75 {cihist.get('p75', '-')}초 (n={fmt(cihist.get('n', 0))})")
    w("")
    w("공정 단계별 소요시간(초) 평균 / p25 / p75:")
    w("")
    w("| 단계 | 평균 | p25 | p75 |")
    w("|---|---|---|---|")
    stage_label = {
        "fill_sec": "충전(Fill)", "pack_sec": "보압(Pack)", "cool_sec": "냉각(Cool)",
        "opening_sec": "형개(Opening)", "ejecting_sec": "취출(Ejecting)", "closing_sec": "형폐(Closing)",
    }
    for key, lab in stage_label.items():
        s = proc.get(key)
        if s:
            w(f"| {lab} | {s.get('mean', '-')} | {s.get('p25', '-')} | {s.get('p75', '-')} |")
    w("")
    w("해석: 냉각(Cool) 단계가 사이클타임의 대부분을 차지한다 → 사이클 단축의 핵심 레버.")
    w("")

    return "\n".join(L)


def patch_design(design_path: Path, digest: str) -> None:
    """design.json 의 grounding_digest 를 전체 digest 로 덮어쓴다.

    왜: Design(LLM)이 소스를 요약하며 digest 를 과압축해 수치를 대부분 버린다.
    이 보고서는 digest 의 숫자가 grounding 에 그대로 있어야 본문에 인용·검증이 된다.
    그래서 design.json 생성 후 이 단계로 grounding_digest 를 원본 digest 로 교체한다.
    (design.json 은 '웹 UI 편집 가능' 설계라, 외부에서 고쳐도 generator 가 재검증해 받아들인다.)
    """
    import json
    if not design_path.exists():
        print(f"[패치 건너뜀] design.json 없음: {design_path}\n"
              f"  → main.py 를 한 번 먼저 실행해 design.json 을 만든 뒤 다시 --patch-design 하세요.",
              file=sys.stderr)
        return
    d = json.loads(design_path.read_text(encoding="utf-8"))
    old = len(d.get("grounding_digest", ""))
    d["grounding_digest"] = digest
    design_path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[패치] grounding_digest {old} → {len(digest)}자 교체: {design_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="금형 통계 digest 빌더")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="출력 경로(.md)")
    ap.add_argument("--patch-design", nargs="?", const=str(DEFAULT_DESIGN), default=None,
                    metavar="DESIGN_JSON",
                    help="digest 생성 후 design.json 의 grounding_digest 를 전체 digest 로 "
                         "교체한다. 경로 생략 시 대표보고 design.json 사용. "
                         "(Design 의 과압축으로 숫자가 소실되는 문제를 자동 해결)")
    args = ap.parse_args()

    try:
        text = build()
    except httpx.HTTPError as e:
        print(f"[오류] API 호출 실패: {e}", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")

    n = len(text)
    print(f"[완료] {out}  ({n:,}자)")
    if n > 12000:
        print(f"[경고] {n:,}자 > MAX_FILE_CHARS(12,000). read_source 가 절단한다 → 압축 필요.",
              file=sys.stderr)

    if args.patch_design is not None:
        patch_design(Path(args.patch_design), text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

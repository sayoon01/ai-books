"""
사출기 보고서 차트 생성·삽입기 (v3 시각화).

왜 필요한가:
  본문(LLM 생성)은 표 위주다. 표 외 시각 요소(도넛·막대·누적·산점도)를 더하려면
  코드가 결정적으로 차트를 그려 챕터에 끼워 넣어야 한다. LLM 은 base64 이미지를
  만들 수 없으므로, 집계 캐시(machine-agg.json)에서 직접 차트를 그린다.

방식:
  - matplotlib 로 차트 PNG → base64 data URI 로 인코딩(상대경로 불필요: PDF 렌더러가
    base_url 없이도 data URI 는 그대로 임베드한다).
  - 각 챕터 번호 → 관련 차트 매핑. 챕터 md 의 첫 표 블록 뒤(없으면 첫 H2 단락 뒤)에
    <figure><img><figcaption> 로 삽입.
  - 멱등: 이미 data:image 가 있는 챕터는 건너뛴다(중복 삽입 방지).

실행:
  .venv/bin/python tools/add_charts.py <챕터_md_디렉토리>
  (예: output/금형-사출-사출기-단위-가동품질-통계-분석-보고서)
"""
from __future__ import annotations

import base64
import io
import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager as fm
import matplotlib.pyplot as plt

ADK_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ADK_ROOT.parent
AGG = REPO_ROOT / "data" / "machine-agg.json"

# ── 한글 폰트 ─────────────────────────────────────────────────────────
_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
if Path(_FONT).exists():
    fm.fontManager.addfont(_FONT)
    plt.rcParams["font.family"] = fm.FontProperties(fname=_FONT).get_name()
plt.rcParams["axes.unicode_minus"] = False

# ── 팔레트 (책 표지 톤: 네이비/골드) ─────────────────────────────────
NAVY = "#0f2540"
GOLD = "#c9a14a"
GRAY = "#9aa5b1"
RED = "#c0392b"
TEAL = "#2a7f8e"
TYPE_COLORS = {
    "NORMAL": NAVY, "NO_SIGNAL": GRAY, "SENSOR_ERROR": RED,
    "WARMUP": GOLD, "IDLE": TEAL,
}
CYCLE_TYPES = ["NORMAL", "NO_SIGNAL", "SENSOR_ERROR", "WARMUP", "IDLE"]


def pct(part, whole):
    return 100.0 * part / whole if whole else 0.0


def b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _machines_sorted(agg, key, reverse=True):
    return sorted(agg["machines"].items(), key=key, reverse=reverse)


# ── 차트들 ────────────────────────────────────────────────────────────
def chart_overall_donut(agg) -> str:
    grand = {t: 0 for t in CYCLE_TYPES}
    for m in agg["machines"].values():
        for t in CYCLE_TYPES:
            grand[t] += m["dist"].get(t, 0)
    total = sum(grand.values())
    vals = [grand[t] for t in CYCLE_TYPES]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    wedges, _ = ax.pie(vals, colors=[TYPE_COLORS[t] for t in CYCLE_TYPES],
                       startangle=90, counterclock=False,
                       wedgeprops=dict(width=0.42, edgecolor="white", linewidth=1.5))
    ax.text(0, 0, f"총 {total:,}\n사이클", ha="center", va="center",
            fontsize=12, color=NAVY, fontweight="bold")
    labels = [f"{t}  {pct(grand[t], total):.1f}%  ({grand[t]:,})" for t in CYCLE_TYPES]
    ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5),
              frameon=False, fontsize=10)
    ax.set_title("전체 사이클 유형 분포", fontsize=13, color=NAVY, fontweight="bold")
    return b64(fig)


def chart_cycles_per_machine(agg) -> str:
    items = _machines_sorted(agg, lambda kv: kv[1]["total"])
    names = [k for k, _ in items]
    totals = [m["total"] for _, m in items]
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    bars = ax.barh(names[::-1], totals[::-1], color=NAVY)
    ax.set_xlabel("총 수집 사이클 수", fontsize=10)
    ax.set_title("사출기별 총 수집 사이클 규모", fontsize=13, color=NAVY, fontweight="bold")
    for b, v in zip(bars, totals[::-1]):
        ax.text(v, b.get_y() + b.get_height() / 2, f" {v:,}", va="center", fontsize=8)
    ax.margins(x=0.18)
    ax.grid(axis="x", alpha=0.25)
    return b64(fig)


def chart_normal_rate(agg) -> str:
    items = _machines_sorted(agg, lambda kv: pct(kv[1]["dist"].get("NORMAL", 0), kv[1]["total"]))
    names = [k for k, _ in items]
    rates = [pct(m["dist"].get("NORMAL", 0), m["total"]) for _, m in items]
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    bars = ax.barh(names[::-1], rates[::-1], color=GOLD)
    ax.set_xlabel("NORMAL(분석대상) 비율 (%)", fontsize=10)
    ax.set_title("사출기별 분석가능 데이터(NORMAL) 확보율", fontsize=13, color=NAVY, fontweight="bold")
    for b, v in zip(bars, rates[::-1]):
        ax.text(v, b.get_y() + b.get_height() / 2, f" {v:.1f}%", va="center", fontsize=8)
    ax.margins(x=0.15)
    ax.grid(axis="x", alpha=0.25)
    return b64(fig)


def _maker_groups(agg):
    g = {}
    for name, m in agg["machines"].items():
        g.setdefault(m.get("maker") or "(미상)", []).append(m)
    return g


def chart_maker_compare(agg) -> str:
    g = _maker_groups(agg)
    makers = sorted(g, key=lambda k: -sum(x["total"] for x in g[k]))
    nrm, nosig = [], []
    for mk in makers:
        tot = sum(x["total"] for x in g[mk])
        nrm.append(pct(sum(x["dist"].get("NORMAL", 0) for x in g[mk]), tot))
        nosig.append(pct(sum(x["dist"].get("NO_SIGNAL", 0) for x in g[mk]), tot))
    import numpy as np
    x = np.arange(len(makers))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    b1 = ax.bar(x - w / 2, nrm, w, label="NORMAL%", color=NAVY)
    b2 = ax.bar(x + w / 2, nosig, w, label="NO_SIGNAL%", color=GRAY)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{mk}\n({len(g[mk])}대)" for mk in makers], fontsize=10)
    ax.set_ylabel("비율 (%)", fontsize=10)
    ax.set_title("제조계열별 데이터 수집 안정성 비교", fontsize=13, color=NAVY, fontweight="bold")
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                    f"{b.get_height():.1f}", ha="center", va="bottom", fontsize=9)
    ax.legend(frameon=False, fontsize=10)
    ax.grid(axis="y", alpha=0.25)
    return b64(fig)


def chart_year_trend(agg) -> str:
    g = {}
    for m in agg["machines"].values():
        g.setdefault(m.get("year") or "(미상)", []).append(m)
    years = sorted(g)
    nrm = [pct(sum(x["dist"].get("NORMAL", 0) for x in g[y]),
               sum(x["total"] for x in g[y])) for y in years]
    cnt = [len(g[y]) for y in years]
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    bars = ax.bar(years, nrm, color=GOLD, width=0.55)
    ax.plot(years, nrm, color=NAVY, marker="o", linewidth=2)
    for b, v, c in zip(bars, nrm, cnt):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.1f}%\n({c}대)",
                ha="center", va="bottom", fontsize=9, color=NAVY)
    ax.set_ylabel("NORMAL 비율 (%)", fontsize=10)
    ax.set_title("도입연도별 분석가능 데이터(NORMAL) 비율", fontsize=13, color=NAVY, fontweight="bold")
    ax.margins(y=0.18)
    ax.grid(axis="y", alpha=0.25)
    return b64(fig)


def chart_stacked_cycletype(agg) -> str:
    items = _machines_sorted(agg, lambda kv: kv[1]["total"])
    names = [k for k, _ in items][::-1]
    data = {t: [pct(m["dist"].get(t, 0), m["total"]) for _, m in items][::-1] for t in CYCLE_TYPES}
    import numpy as np
    fig, ax = plt.subplots(figsize=(7.8, 5.2))
    left = np.zeros(len(names))
    for t in CYCLE_TYPES:
        vals = np.array(data[t])
        ax.barh(names, vals, left=left, color=TYPE_COLORS[t], label=t)
        left += vals
    ax.set_xlim(0, 100)
    ax.set_xlabel("사이클 유형 구성 비율 (%)", fontsize=10)
    ax.set_title("사출기별 사이클 유형 구성 (100% 누적)", fontsize=13, color=NAVY, fontweight="bold")
    ax.legend(ncol=5, frameon=False, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.09))
    return b64(fig)


def chart_senserr_rank(agg) -> str:
    def se(m):
        return m["dist"].get("NO_SIGNAL", 0) + m["dist"].get("SENSOR_ERROR", 0)
    items = _machines_sorted(agg, lambda kv: pct(se(kv[1]), kv[1]["total"]))
    names = [k for k, _ in items]
    rates = [pct(se(m), m["total"]) for _, m in items]
    colors = [RED if r >= 80 else (GOLD if r >= 40 else TEAL) for r in rates]
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    bars = ax.barh(names[::-1], rates[::-1], color=colors[::-1])
    ax.set_xlabel("센서 에러율 = (NO_SIGNAL+SENSOR_ERROR) / 전체 (%)", fontsize=9.5)
    ax.set_title("사출기별 센서·데이터 품질 에러율 (높을수록 점검 우선)", fontsize=12.5,
                 color=NAVY, fontweight="bold")
    for b, v in zip(bars, rates[::-1]):
        ax.text(v, b.get_y() + b.get_height() / 2, f" {v:.1f}%", va="center", fontsize=8)
    ax.margins(x=0.15)
    ax.grid(axis="x", alpha=0.25)
    return b64(fig)


def chart_warmup_idle(agg) -> str:
    items = _machines_sorted(agg, lambda kv: pct(kv[1]["dist"].get("IDLE", 0), kv[1]["total"]))
    names = [k for k, _ in items]
    warm = [pct(m["dist"].get("WARMUP", 0), m["total"]) for _, m in items]
    idle = [pct(m["dist"].get("IDLE", 0), m["total"]) for _, m in items]
    import numpy as np
    y = np.arange(len(names))
    h = 0.4
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    ax.barh(y + h / 2, warm[::-1], h, label="WARMUP%", color=GOLD)
    ax.barh(y - h / 2, idle[::-1], h, label="IDLE%", color=TEAL)
    ax.set_yticks(y)
    ax.set_yticklabels(names[::-1])
    ax.set_xlabel("비율 (%)", fontsize=10)
    ax.set_title("사출기별 가동 비효율 — WARMUP·IDLE", fontsize=13, color=NAVY, fontweight="bold")
    ax.legend(frameon=False, fontsize=10)
    ax.grid(axis="x", alpha=0.25)
    return b64(fig)


def chart_moldcount(agg) -> str:
    items = _machines_sorted(agg, lambda kv: kv[1]["mold_count"])
    names = [k for k, _ in items]
    counts = [m["mold_count"] for _, m in items]
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    bars = ax.barh(names[::-1], counts[::-1], color=NAVY)
    ax.set_xlabel("가동 금형(PartNo) 종 수", fontsize=10)
    ax.set_title("사출기별 가동 금형 수 (다품종 ↔ 전용)", fontsize=13, color=NAVY, fontweight="bold")
    for b, v in zip(bars, counts[::-1]):
        ax.text(v, b.get_y() + b.get_height() / 2, f" {v}", va="center", fontsize=8.5)
    ax.margins(x=0.12)
    ax.grid(axis="x", alpha=0.25)
    return b64(fig)


def chart_scatter(agg) -> str:
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    for name, m in agg["machines"].items():
        x = m["total"]
        y = pct(m["dist"].get("NORMAL", 0), m["total"])
        size = 30 + m["mold_count"] * 14
        color = NAVY if (m.get("maker") == "toprun") else GOLD
        ax.scatter(x, y, s=size, color=color, alpha=0.7, edgecolor="white", linewidth=0.8)
        ax.annotate(name, (x, y), fontsize=7.5, xytext=(4, 3), textcoords="offset points")
    ax.set_xscale("log")
    ax.set_xlabel("총 수집 사이클 (로그 스케일)", fontsize=10)
    ax.set_ylabel("NORMAL(분석대상) 비율 (%)", fontsize=10)
    ax.set_title("규모 대비 데이터 활용도 (점 크기=금형 수, 색=계열)", fontsize=12,
                 color=NAVY, fontweight="bold")
    ax.grid(alpha=0.25)
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([0], [0], marker="o", color="w", markerfacecolor=NAVY, label="toprun", markersize=9),
                       Line2D([0], [0], marker="o", color="w", markerfacecolor=GOLD, label="woosung", markersize=9)],
              frameon=False, fontsize=9)
    return b64(fig)


# 챕터 번호 → [(차트 함수, 캡션), ...]
CHAPTER_CHARTS = {
    1: [(chart_overall_donut, "전체 332만 사이클의 유형 구성. 분석대상(NORMAL)은 11.7%에 불과하고 NO_SIGNAL이 대부분이다.")],
    2: [(chart_cycles_per_machine, "사출기별 총 수집 사이클 규모. 상위 설비가 대부분의 데이터를 생성한다."),
        (chart_normal_rate, "사출기별 분석가능 데이터(NORMAL) 확보율. 규모와 무관하게 설비별 편차가 극심하다.")],
    3: [(chart_maker_compare, "제조계열별 NORMAL·NO_SIGNAL 비율. woosung 계열의 수집 안정성이 toprun보다 높다."),
        (chart_year_trend, "도입연도별 NORMAL 비율. 연식과 데이터 품질은 선형 관계가 아니다(2024년 도입군이 최저).")],
    4: [(chart_stacked_cycletype, "사출기별 사이클 유형 100% 누적 구성. 설비마다 유형 분포가 뚜렷이 갈린다.")],
    5: [(chart_senserr_rank, "사출기별 센서·데이터 품질 에러율. toprun 다수 설비가 90%대로 점검 최우선이다.")],
    6: [(chart_warmup_idle, "사출기별 WARMUP·IDLE 비율. 소규모 설비에서 가동 비효율 비중이 상대적으로 높다.")],
    7: [(chart_moldcount, "사출기별 가동 금형 수. toprun_C11(31종) 등 다품종 설비와 전용 설비가 갈린다.")],
    8: [(chart_scatter, "규모 대비 데이터 활용도 분포. 우상단=대규모·고활용, 우하단=대규모지만 데이터 대부분 무효.")],
}


def _insert_point(lines: list[str]) -> int:
    """첫 표 블록 끝 인덱스(다음 줄) 반환. 표 없으면 첫 H2 다음 단락 끝, 그것도 없으면 끝."""
    i = 0
    n = len(lines)
    # 첫 표 블록
    while i < n:
        if lines[i].lstrip().startswith("|"):
            while i < n and lines[i].lstrip().startswith("|"):
                i += 1
            return i
        i += 1
    # 첫 H2 뒤 첫 빈 줄
    for j, ln in enumerate(lines):
        if ln.startswith("## "):
            k = j + 1
            while k < n and lines[k].strip() != "":
                k += 1
            return k
    return n


def figure_md(data_uri_b64: str, num: int, caption: str) -> list[str]:
    return [
        "",
        "<figure>",
        f'<img src="data:image/png;base64,{data_uri_b64}" alt="그림 {num}" />',
        f"<figcaption>그림 {num}. {caption}</figcaption>",
        "</figure>",
        "",
    ]


def main() -> int:
    if len(sys.argv) < 2:
        print("사용법: add_charts.py <챕터_md_디렉토리>", file=sys.stderr)
        return 2
    book_dir = Path(sys.argv[1])
    if not book_dir.is_absolute():
        book_dir = Path.cwd() / book_dir
    agg = json.loads(AGG.read_text(encoding="utf-8"))

    chapters = sorted(book_dir.glob("chapter-*.md"),
                      key=lambda p: int(re.match(r"chapter-(\d+)", p.name).group(1)))
    if not chapters:
        print(f"[오류] 챕터 md 없음: {book_dir}", file=sys.stderr)
        return 1

    fignum = 0
    for ch in chapters:
        num = int(re.match(r"chapter-(\d+)", ch.name).group(1))
        specs = CHAPTER_CHARTS.get(num, [])
        if not specs:
            continue
        text = ch.read_text(encoding="utf-8")
        if "data:image/png;base64" in text:
            print(f"  [건너뜀] 이미 차트 있음: {ch.name}")
            fignum += len(specs)
            continue
        lines = text.splitlines()
        block = []
        for fn, cap in specs:
            fignum += 1
            block += figure_md(fn(agg), fignum, cap)
        pos = _insert_point(lines)
        lines[pos:pos] = block
        ch.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  [삽입] {ch.name}: 차트 {len(specs)}개 (그림 {fignum - len(specs) + 1}~{fignum})")
    print(f"[완료] 총 그림 {fignum}개 삽입")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

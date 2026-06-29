"""
도메인 무관 차트 엔진 — 어떤 책이든 grounding_digest의 '표'에서 차트를 그린다.

설계 원칙 (환각 0):
  파이프라인은 근거 없는 수치를 차단한다. 그래서 차트 숫자는 LLM이 만들지 않는다.
  LLM(agent/charts.py)은 '구조'만 정한다 — 어느 표·어느 열·차트 종류·대상 챕터.
  실제 숫자는 이 모듈이 digest의 마크다운 표 셀에서 직접 파싱해 그린다.

구성:
  - 한글 폰트 1회 설정 (Noto Sans CJK).
  - 차트 프리미티브: donut/bar/barh/grouped_bar/stacked100/line/scatter → base64 PNG.
  - find_table(): digest에서 지정 열을 가진 마크다운 표를 찾아 {열: [값...]} 로 파싱.
  - render_spec(): FigureSpec(dict) + digest → base64 PNG (해소 실패 시 None).
  - figure_md()/inject_chapter(): 챕터 md에 <figure> 삽입(멱등).

generator/ 와 무관한 독립 모듈. tools/add_charts.py(금형 전용)도 이 프리미티브를 쓴다.
"""
from __future__ import annotations

import base64
import io
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager as fm
import matplotlib.pyplot as plt

# ── 한글 폰트 ─────────────────────────────────────────────────────────
for _fp in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"):
    if Path(_fp).exists():
        fm.fontManager.addfont(_fp)
        plt.rcParams["font.family"] = fm.FontProperties(fname=_fp).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

# ── 팔레트 (책 표지 톤: 네이비/골드) ─────────────────────────────────
NAVY, GOLD, GRAY, RED, TEAL = "#0f2540", "#c9a14a", "#9aa5b1", "#c0392b", "#2a7f8e"
# 시리즈가 여러 개일 때 순환 색. 첫 둘은 네이비/골드(브랜드).
SERIES_COLORS = [NAVY, GOLD, TEAL, RED, GRAY, "#6a5acd", "#2e8b57", "#b8860b"]
# 사이클 유형 등 의미색(이름이 맞으면 우선 적용).
SEMANTIC = {"NORMAL": NAVY, "NO_SIGNAL": GRAY, "SENSOR_ERROR": RED,
            "WARMUP": GOLD, "IDLE": TEAL}


def _b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _color_for(name: str, idx: int) -> str:
    return SEMANTIC.get(name.strip().upper(), SERIES_COLORS[idx % len(SERIES_COLORS)])


# =====================================================================
# 1) 차트 프리미티브 — 모두 (labels, series, ...) → base64 PNG
#    series: list[(name, [values])]. 단일 시리즈도 [(name, vals)].
# =====================================================================
def donut(labels, values, title="") -> str:
    total = sum(values) or 1
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    colors = [_color_for(l, i) for i, l in enumerate(labels)]
    wedges, _ = ax.pie(values, colors=colors, startangle=90, counterclock=False,
                       wedgeprops=dict(width=0.42, edgecolor="white", linewidth=1.5))
    ax.text(0, 0, f"총\n{total:,.0f}", ha="center", va="center",
            fontsize=12, color=NAVY, fontweight="bold")
    leg = [f"{l}  {100*v/total:.1f}%" for l, v in zip(labels, values)]
    ax.legend(wedges, leg, loc="center left", bbox_to_anchor=(1.0, 0.5),
              frameon=False, fontsize=10)
    if title:
        ax.set_title(title, fontsize=13, color=NAVY, fontweight="bold")
    return _b64(fig)


def _barh_single(labels, values, title="", xlabel="", percent=False, color=NAVY) -> str:
    fig, ax = plt.subplots(figsize=(7.6, max(3.2, 0.34 * len(labels) + 1.4)))
    bars = ax.barh(labels[::-1], values[::-1], color=color)
    for b, v in zip(bars, values[::-1]):
        txt = f" {v:.1f}%" if percent else f" {v:,.0f}"
        ax.text(v, b.get_y() + b.get_height() / 2, txt, va="center", fontsize=8)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10)
    if title:
        ax.set_title(title, fontsize=13, color=NAVY, fontweight="bold")
    ax.margins(x=0.16)
    ax.grid(axis="x", alpha=0.25)
    return _b64(fig)


def barh(labels, series, title="", xlabel="", percent=False) -> str:
    """가로 막대. 단일 시리즈면 단순 barh, 여러 시리즈면 그룹 barh."""
    if len(series) == 1:
        return _barh_single(labels, series[0][1], title, xlabel or series[0][0],
                            percent, _color_for(series[0][0], 0))
    import numpy as np
    n = len(series)
    y = np.arange(len(labels))
    h = 0.8 / n
    fig, ax = plt.subplots(figsize=(7.6, max(3.4, 0.4 * len(labels) + 1.4)))
    for i, (name, vals) in enumerate(series):
        off = (i - (n - 1) / 2) * h
        ax.barh(y + off, vals[::-1], h, label=name, color=_color_for(name, i))
    ax.set_yticks(y)
    ax.set_yticklabels(labels[::-1])
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10)
    if title:
        ax.set_title(title, fontsize=13, color=NAVY, fontweight="bold")
    ax.legend(frameon=False, fontsize=9)
    ax.grid(axis="x", alpha=0.25)
    return _b64(fig)


def bar(labels, series, title="", ylabel="") -> str:
    """세로 막대(그룹). 범주 수가 적을 때 적합."""
    import numpy as np
    n = len(series)
    x = np.arange(len(labels))
    w = 0.8 / n
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for i, (name, vals) in enumerate(series):
        off = (i - (n - 1) / 2) * w
        b = ax.bar(x + off, vals, w, label=name, color=_color_for(name, i))
        for rect in b:
            ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height(),
                    f"{rect.get_height():.1f}", ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9.5)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    if title:
        ax.set_title(title, fontsize=13, color=NAVY, fontweight="bold")
    if n > 1:
        ax.legend(frameon=False, fontsize=9)
    ax.grid(axis="y", alpha=0.25)
    return _b64(fig)


# 별칭 (스펙 type 이름 호환)
grouped_bar = bar


def stacked100(labels, series, title="", xlabel="구성 비율 (%)") -> str:
    """100% 누적 가로 막대. series 값들을 행별 합으로 정규화."""
    import numpy as np
    mat = np.array([vals for _, vals in series], dtype=float)  # (series, labels)
    col_sum = mat.sum(axis=0)
    col_sum[col_sum == 0] = 1
    pct = mat / col_sum * 100.0
    fig, ax = plt.subplots(figsize=(7.8, max(3.6, 0.4 * len(labels) + 1.6)))
    left = np.zeros(len(labels))
    rev = slice(None, None, -1)
    names = [n for n, _ in series]
    for i, name in enumerate(names):
        vals = pct[i][rev]
        ax.barh(labels[rev], vals, left=left, color=_color_for(name, i), label=name)
        left += vals
    ax.set_xlim(0, 100)
    ax.set_xlabel(xlabel, fontsize=10)
    if title:
        ax.set_title(title, fontsize=13, color=NAVY, fontweight="bold")
    ax.legend(ncol=min(len(names), 5), frameon=False, fontsize=8.5,
              loc="upper center", bbox_to_anchor=(0.5, -0.08))
    return _b64(fig)


def line(labels, series, title="", ylabel="") -> str:
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for i, (name, vals) in enumerate(series):
        ax.plot(labels, vals, marker="o", linewidth=2,
                color=_color_for(name, i), label=name)
        for xv, yv in zip(labels, vals):
            ax.text(xv, yv, f"{yv:.1f}", ha="center", va="bottom", fontsize=8.5, color=NAVY)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    if title:
        ax.set_title(title, fontsize=13, color=NAVY, fontweight="bold")
    if len(series) > 1:
        ax.legend(frameon=False, fontsize=9)
    ax.margins(y=0.18)
    ax.grid(alpha=0.25)
    return _b64(fig)


def scatter(labels, series, title="", xlabel="", ylabel="") -> str:
    """series[0]=x, series[1]=y (값 리스트). labels=점 이름."""
    xs = series[0][1]
    ys = series[1][1]
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    ax.scatter(xs, ys, s=60, color=NAVY, alpha=0.7, edgecolor="white", linewidth=0.8)
    for lab, xv, yv in zip(labels, xs, ys):
        ax.annotate(str(lab), (xv, yv), fontsize=7.5, xytext=(4, 3),
                    textcoords="offset points")
    if max(xs) / (min(xs) or 1) > 50:
        ax.set_xscale("log")
    ax.set_xlabel(xlabel or series[0][0], fontsize=10)
    ax.set_ylabel(ylabel or series[1][0], fontsize=10)
    if title:
        ax.set_title(title, fontsize=12.5, color=NAVY, fontweight="bold")
    ax.grid(alpha=0.25)
    return _b64(fig)


_RENDERERS = {
    "donut": donut, "bar": bar, "grouped_bar": grouped_bar, "barh": barh,
    "stacked100": stacked100, "line": line, "scatter": scatter,
}


# =====================================================================
# 2) 마크다운 표 파서 — digest의 표에서 숫자를 직접 추출
# =====================================================================
def _num(cell: str):
    """'1,234' / '12.3%' / '58.0 초' → float. 숫자 없으면 None."""
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", cell.replace(",", "") if "," in cell else cell)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _iter_tables(md: str):
    """md에서 (헤더리스트, [행리스트...], 표직전_문맥줄) 들을 순회."""
    lines = md.split("\n")
    i, n = 0, len(lines)
    while i < n:
        if lines[i].lstrip().startswith("|") and i + 1 < n and re.search(r"\|\s*:?-{2,}", lines[i + 1]):
            header = _split_row(lines[i])
            ctx = ""
            j = i - 1
            while j >= 0 and lines[j].strip() == "":
                j -= 1
            if j >= 0:
                ctx = lines[j].strip()
            rows = []
            k = i + 2
            while k < n and lines[k].lstrip().startswith("|"):
                rows.append(_split_row(lines[k]))
                k += 1
            yield header, rows, ctx
            i = k
        else:
            i += 1


def find_table(digest: str, keyword: str = "", need_cols=()):
    """digest에서 표를 찾아 {열이름: [원셀...]} 반환. 못 찾으면 None.

    우선순위: (1) need_cols 가 헤더에 모두 있는 표 중, keyword 가 직전 문맥/헤더에
    걸리는 것 → (2) need_cols 만 만족하는 첫 표 → (3) keyword 만 걸리는 첫 표.
    """
    need = [c.strip() for c in need_cols if c.strip()]
    cand_colmatch = []
    cand_kw = []
    for header, rows, ctx in _iter_tables(digest):
        hset = [h.strip() for h in header]
        cols_ok = all(any(nc == h or nc in h for h in hset) for nc in need) if need else False
        kw_ok = bool(keyword) and (keyword in ctx or any(keyword in h for h in hset))
        table = {h: [r[idx] if idx < len(r) else "" for r in rows]
                 for idx, h in enumerate(header)}
        if cols_ok and kw_ok:
            return table
        if cols_ok:
            cand_colmatch.append(table)
        if kw_ok:
            cand_kw.append(table)
    if cand_colmatch:
        return cand_colmatch[0]
    if cand_kw:
        return cand_kw[0]
    return None


def _resolve_col(table: dict, name: str):
    """표에서 열 이름 해소(정확→부분일치). (실제키, 값리스트) 또는 None."""
    name = name.strip()
    if name in table:
        return name, table[name]
    for k in table:
        if name == k.strip() or name in k:
            return k, table[k]
    return None


# =====================================================================
# 3) 스펙 → 차트
# =====================================================================
def render_spec(spec: dict, digest: str):
    """FigureSpec(dict) + digest → base64 PNG. 해소 실패 시 None(드롭용)."""
    typ = spec.get("type")
    if typ not in _RENDERERS:
        return None
    need = [spec.get("label_col", "")] + list(spec.get("value_cols", []))
    table = find_table(digest, spec.get("table", ""), [c for c in need if c])
    if not table:
        return None
    lab = _resolve_col(table, spec.get("label_col", ""))
    if not lab:
        return None
    labels = [x for x in lab[1]]
    series = []
    for vc in spec.get("value_cols", []):
        rc = _resolve_col(table, vc)
        if not rc:
            return None
        vals = [_num(c) for c in rc[1]]
        if any(v is None for v in vals):
            # 일부 셀이 비수치면 해당 행 제거(라벨도 동기 제거는 단순화 위해 0 처리 대신 드롭)
            return None
        series.append((rc[0].replace("%", "").strip(), vals))
    if not series:
        return None

    # 정렬/상위 N (donut·scatter·line 제외: 순서 의미)
    if spec.get("sort", True) and typ in ("bar", "grouped_bar", "barh", "stacked100"):
        key = list(zip(labels, *[s[1] for s in series]))
        key.sort(key=lambda r: sum(r[1:]), reverse=True)
        labels = [r[0] for r in key]
        series = [(series[i][0], [r[1 + i] for r in key]) for i in range(len(series))]
    top_n = spec.get("top_n", 0)
    if top_n and typ in ("bar", "grouped_bar", "barh", "stacked100"):
        labels = labels[:top_n]
        series = [(n, v[:top_n]) for n, v in series]

    fn = _RENDERERS[typ]
    title = spec.get("title", "")
    percent = any("%" in vc or "율" in vc or "비율" in vc or "비중" in vc
                  for vc in spec.get("value_cols", []))
    try:
        if typ == "donut":
            return donut(labels, series[0][1], title)
        if typ == "barh":
            return barh(labels, series, title, percent=percent)
        if typ in ("bar", "grouped_bar"):
            return bar(labels, series, title)
        if typ == "stacked100":
            return stacked100(labels, series, title)
        if typ == "line":
            return line(labels, series, title)
        if typ == "scatter":
            if len(series) < 2:
                return None
            return scatter(labels, series, title)
    except Exception as e:  # 렌더 단계 어떤 실패도 차트 누락으로만(파이프라인 보호)
        print(f"  [charts] 렌더 실패({typ}): {e}")
        return None
    return None


# =====================================================================
# 4) 챕터 md 삽입 (멱등)
# =====================================================================
def figure_md(b64: str, num: int, caption: str) -> list[str]:
    return [
        "",
        "<figure>",
        f'<img src="data:image/png;base64,{b64}" alt="그림 {num}" />',
        f"<figcaption>그림 {num}. {caption}</figcaption>",
        "</figure>",
        "",
    ]


def _insert_point(lines: list[str]) -> int:
    """첫 표 블록 끝(다음 줄). 없으면 첫 H2 다음 빈 줄, 그것도 없으면 끝."""
    i, n = 0, len(lines)
    while i < n:
        if lines[i].lstrip().startswith("|"):
            while i < n and lines[i].lstrip().startswith("|"):
                i += 1
            return i
        i += 1
    for j, ln in enumerate(lines):
        if ln.startswith("## "):
            k = j + 1
            while k < n and lines[k].strip() != "":
                k += 1
            return k
    return n


def inject_chapter(path: Path, figures_b64_caption, start_num: int = 1) -> int:
    """figures_b64_caption: [(b64, caption), ...]. 챕터 첫 표 뒤에 삽입. 멱등.
    start_num: 그림 번호 시작값(책 전체 연속 번호용).
    삽입한 그림 수 반환(이미 차트 있으면 0)."""
    text = path.read_text(encoding="utf-8")
    if "data:image/png;base64" in text:
        return 0
    figs = [f for f in figures_b64_caption if f and f[0]]
    if not figs:
        return 0
    lines = text.splitlines()
    block = []
    for n, (b64, cap) in enumerate(figs, start_num):
        block += figure_md(b64, n, cap)
    pos = _insert_point(lines)
    lines[pos:pos] = block
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(figs)

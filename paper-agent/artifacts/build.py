"""
표/그림/통계 실제 생성 — plan.artifacts 의 '계획'을 데이터로 '실물'로 만든다.

★ 핵심 분리: LLM 은 "무엇을 만들지"만 정하고(plan), 수치는 여기서 데이터에서 뽑는다.
  → 본문 수치 환각을 원천 차단(unverified_numbers 가드와 짝).

현재 데이터 계약: 실험 summary.json 형태
  {"by_orchestrator": {"<orch>": {"<metric>": {"mean":..,"std":..,"n":..}, ...}}}
이 구조에서 (구조 × 지표) 행렬을 만들어
  - table → tables/<id>.tex  (booktabs, \\label{id})
  - figure → figures/<id>.png (지표별 정규화 그룹 막대) + 조립 시 float 로 감쌈
  - stat  → 표본이 충분하면 메모, 부족(n<2)하면 한계 명시
데이터 형태가 다르면 정중히 비우고(orchestrator 가 참조-only 로 진행) 넘어간다.
"""
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                       # 헤드리스
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np


def _setup_korean_font() -> None:
    """라벨/제목에 한글이 와도 안 깨지게 한국어 지원 폰트를 찾아 설정."""
    for cand in ("NanumGothic", "Noto Sans CJK KR", "Noto Serif CJK KR",
                 "UnDotum", "Baekmuk Gulim", "Baekmuk Batang"):
        try:
            font_manager.findfont(cand, fallback_to_default=False)
            plt.rcParams["font.family"] = cand
            break
        except Exception:
            continue
    plt.rcParams["axes.unicode_minus"] = False


_setup_korean_font()


def _safe(name: str) -> str:
    return re.sub(r"[^\w]+", "_", name).strip("_")


def _parse_metrics(source_text: str) -> tuple[list[str], list[str], dict]:
    """summary.json → (orchestrators, metrics, {orch:{metric:(mean,std,n)}}). 못 읽으면 빈 값."""
    try:
        data = json.loads(source_text)
    except (json.JSONDecodeError, ValueError):
        return [], [], {}
    by = data.get("by_orchestrator")
    if not isinstance(by, dict) or not by:
        return [], [], {}
    orchs = list(by.keys())
    metrics: list[str] = []
    table: dict = {}
    for orch, mdict in by.items():
        table[orch] = {}
        if not isinstance(mdict, dict):
            continue
        for metric, v in mdict.items():
            if isinstance(v, dict) and "mean" in v:
                table[orch][metric] = (v.get("mean"), v.get("std"), v.get("n"))
                if metric not in metrics:
                    metrics.append(metric)
    return orchs, metrics, table


def _fmt(x) -> str:
    if x is None:
        return "--"
    if isinstance(x, float):
        return f"{x:.2f}".rstrip("0").rstrip(".") if x != int(x) else str(int(x))
    return str(x)


def _render_table(art: dict, orchs, metrics, table, out: Path) -> dict | None:
    if not orchs or not metrics:
        return None
    cols = "l" + "r" * len(orchs)
    lines = [r"\begin{table}[t]", r"\centering",
             rf"\caption{{{art.get('title','')}}}", rf"\label{{{art['id']}}}",
             rf"\begin{{tabular}}{{{cols}}}", r"\toprule",
             "Metric & " + " & ".join(_safe(o) for o in orchs) + r" \\", r"\midrule"]
    for m in metrics:
        row = [m.replace("_", r"\_")] + [_fmt(table[o].get(m, (None,))[0]) for o in orchs]
        lines.append(" & ".join(row) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    path = out / "tables" / f"{_safe(art['id'])}.tex"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return {"id": art["id"], "kind": "table", "title": art.get("title", ""),
            "caption": art.get("purpose", ""), "path": str(path), "input": True}


def _render_figure(art: dict, orchs, metrics, table, out: Path) -> dict | None:
    if not orchs or not metrics:
        return None
    # 지표마다 스케일이 달라 지표별 [0,1] 정규화 후 그룹 막대(상대 비교용).
    M = np.array([[(table[o].get(m, (0,))[0] or 0) for o in orchs] for m in metrics], dtype=float)
    norm = M.copy()
    for r in range(M.shape[0]):
        rng = M[r].max() - M[r].min()
        norm[r] = (M[r] - M[r].min()) / rng if rng else 0.5
    x = np.arange(len(metrics))
    w = 0.8 / max(len(orchs), 1)
    fig, ax = plt.subplots(figsize=(max(6, len(metrics) * 1.1), 3.8))
    for j, o in enumerate(orchs):
        ax.bar(x + j * w, norm[:, j], w, label=_safe(o))
    ax.set_xticks(x + w * (len(orchs) - 1) / 2)
    ax.set_xticklabels([m.replace("_", " ") for m in metrics], rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("normalized (0-1 per metric)")
    ax.set_title(art.get("title", ""))
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = out / "figures" / f"{_safe(art['id'])}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return {"id": art["id"], "kind": "figure", "title": art.get("title", ""),
            "caption": art.get("purpose", "") + " (지표별 0~1 정규화)",
            "path": str(path), "input": False}


def _digest(orchs, metrics, table) -> str:
    """생성된 자료의 실제 값을 텍스트로 — writer/reviewer 가 인용·검증할 수 있게."""
    if not orchs or not metrics:
        return ""
    lines = ["구조별 지표 실제 값(mean):"]
    for m in metrics:
        vals = ", ".join(f"{o}={_fmt(table[o].get(m,(None,))[0])}" for o in orchs)
        lines.append(f"- {m}: {vals}")
    return "\n".join(lines)


def build_artifacts(plan: dict, source_text: str, out: Path) -> tuple[list[dict], str]:
    """plan.artifacts 를 데이터로 실제 생성. 반환: (manifest, 실제값 digest 텍스트)."""
    orchs, metrics, table = _parse_metrics(source_text)
    manifest: list[dict] = []
    for art in plan.get("artifacts", []):
        kind = art.get("kind")
        if kind == "table":
            m = _render_table(art, orchs, metrics, table, out)
        elif kind == "figure":
            m = _render_figure(art, orchs, metrics, table, out)
        elif kind == "stat":
            ns = [table[o].get(mt, (None, None, 0))[2] or 0 for o in orchs for mt in metrics]
            note = ("표본 부족(n<2) — 유의성 검정 보류, 기술통계만 보고"
                    if (not ns or max(ns) < 2) else "표본 확보 — 검정 가능")
            m = {"id": art["id"], "kind": "stat", "title": art.get("title", ""),
                 "caption": art.get("purpose", ""), "note": note, "input": False}
        else:
            m = None
        if m:
            manifest.append(m)
    return manifest, _digest(orchs, metrics, table)

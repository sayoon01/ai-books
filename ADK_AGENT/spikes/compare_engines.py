"""
엔진 비교 하네스 — graph vs agent 를 '같은 책·같은 design'으로 돌려 산출물 비교.

공정성:
  - design.json(목차·write_brief·grounding_digest)을 양쪽에 동일 주입 → 순수 '엔진 차이'만 비교.
  - 같은 slug 를 넘겨 source 캐시도 양쪽 적중(네트워크 변수 제거).
  - push/pdf/trace 끔(부가 I/O·오버헤드 제거).

산출물(참고 레포 02_model_compare_book 형식 차용):
  output/_compare/<slug>/
    ├─ graph/  agent/                각 엔진의 챕터 .md + logs/chapter-*.json
    ├─ gpu_usage_graph.csv  gpu_usage_agent.csv     5초 샘플 GPU 시계열
    ├─ comparison_summary.json       엔진별 총시간·평균점수·flagged·GPU 통계
    ├─ comparison_report.md          표 + 차트 + 우열 요약
    └─ charts/  compare_elapsed.png  compare_score.png  compare_gpu.png

실행:
  .venv/bin/python spikes/compare_engines.py --toc toc/mold-dx-auto.json
  .venv/bin/python spikes/compare_engines.py --toc ... --limit 2     # 스모크(앞 2챕터)
"""
import argparse
import asyncio
import csv
import json
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # ADK_AGENT/ 를 import 경로에

from pipeline import generate
from core.llm import MODEL

ADK_ROOT = Path(__file__).resolve().parent.parent


def title_to_slug(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug


# ── GPU 샘플러 ────────────────────────────────────────────────────────────
class GpuSampler(threading.Thread):
    """nvidia-smi 로 interval 마다 GPU별 (메모리·util) 기록. t_rel=실행시작 기준 상대초."""

    def __init__(self, csv_path: Path, interval: float = 5.0):
        super().__init__(daemon=True)
        self.csv_path = csv_path
        self.interval = interval
        self._stop_evt = threading.Event()      # ⚠ 'self._stop' 는 Thread 내부 메서드와 충돌(join 깨짐)
        self.rows: list[tuple] = []

    @staticmethod
    def _query() -> list[tuple[int, int, int]]:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,memory.used,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10).stdout.strip()
        res = []
        for line in out.splitlines():
            idx, mem, util = (p.strip() for p in line.split(","))
            res.append((int(idx), int(mem), int(util)))
        return res

    def run(self):
        t0 = time.perf_counter()
        # 증분 저장: 매 샘플마다 CSV에 바로 쓰고 flush → 끝에서 죽어도 그때까지는 디스크에 남음.
        with self.csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t_rel_sec", "gpu_index", "mem_used_mib", "util_pct"])
            f.flush()
            while not self._stop_evt.is_set():
                t_rel = round(time.perf_counter() - t0, 1)
                try:
                    for idx, mem, util in self._query():
                        row = (t_rel, idx, mem, util)
                        self.rows.append(row)
                        w.writerow(row)
                    f.flush()
                except Exception:
                    pass
                self._stop_evt.wait(self.interval)

    def stop(self):
        self._stop_evt.set()

    def dump(self):
        """run()에서 이미 증분 저장됨. 호환용 안전망 — 파일이 없을 때만 메모리에서 복구."""
        if self.csv_path.exists():
            return
        with self.csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t_rel_sec", "gpu_index", "mem_used_mib", "util_pct"])
            w.writerows(self.rows)


# ── design 주입 ───────────────────────────────────────────────────────────
def seed_design(src_design: Path, dst_dir: Path, limit: int | None) -> int:
    d = json.loads(src_design.read_text(encoding="utf-8"))
    if limit:
        d["chapters"] = d["chapters"][:limit]
    dst_dir.mkdir(parents=True, exist_ok=True)
    (dst_dir / "design.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(d["chapters"])


# ── 엔진 1회 실행 ─────────────────────────────────────────────────────────
def run_engine(doc: dict, slug: str, out_dir: Path, engine: str, gpu_csv: Path) -> float:
    sampler = GpuSampler(gpu_csv)
    sampler.start()
    t0 = time.perf_counter()
    try:
        asyncio.run(generate(doc, out_dir, slug, force_redesign=False,
                             push=False, do_pdf=False, trace=False, engine=engine))
    finally:
        elapsed = time.perf_counter() - t0
        sampler.stop()
        sampler.join(timeout=15)
        sampler.dump()
    return elapsed


# ── 지표 집계 ─────────────────────────────────────────────────────────────
def collect_metrics(out_dir: Path, engine: str, elapsed: float, gpu_csv: Path) -> dict:
    chapters = []
    for p in sorted((out_dir / "logs").glob("chapter-*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        chapters.append({
            "number": d.get("chapter", {}).get("number"),
            "best_score": d.get("best_score"),
            "elapsed_sec": d.get("elapsed_sec"),
            "write_count": d.get("write_count"),
            "pass_count": d.get("pass_count"),
            "flagged": d.get("flagged"),
        })
    scores = [c["best_score"] for c in chapters if isinstance(c["best_score"], (int, float))]
    # GPU 통계
    gpu = {}
    if gpu_csv.exists():
        per_idx: dict[int, dict] = {}
        with gpu_csv.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                idx = int(r["gpu_index"])
                g = per_idx.setdefault(idx, {"mem": [], "util": []})
                g["mem"].append(int(r["mem_used_mib"]))
                g["util"].append(int(r["util_pct"]))
        for idx, g in per_idx.items():
            if g["mem"]:
                gpu[f"gpu{idx}"] = {
                    "mem_avg_mib": round(sum(g["mem"]) / len(g["mem"])),
                    "mem_max_mib": max(g["mem"]),
                    "util_avg_pct": round(sum(g["util"]) / len(g["util"])),
                    "util_max_pct": max(g["util"]),
                }
    return {
        "engine": engine,
        "total_elapsed_sec": round(elapsed, 1),
        "avg_sec_per_chapter": round(elapsed / len(chapters), 1) if chapters else None,
        "chapter_count": len(chapters),
        "avg_best_score": round(sum(scores) / len(scores), 1) if scores else None,
        "min_best_score": min(scores) if scores else None,
        "flagged_count": sum(1 for c in chapters if c["flagged"]),
        "total_write_passes": sum(c["write_count"] or 0 for c in chapters),
        "total_review_passes": sum(c["pass_count"] or 0 for c in chapters),
        "chapters": chapters,
        "gpu": gpu,
    }


# ── 차트 ──────────────────────────────────────────────────────────────────
def make_charts(summary: dict, charts_dir: Path, gpu_csvs: dict[str, Path]):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    charts_dir.mkdir(parents=True, exist_ok=True)
    engines = list(summary["engines"].keys())
    colors = {"graph": "#4C78A8", "agent": "#F58518"}

    def _bar(metric: str, title: str, ylabel: str, fname: str):
        fig, ax = plt.subplots(figsize=(10, 4.5))
        nums = summary["engines"][engines[0]]["chapters"]
        x = list(range(1, len(nums) + 1))
        width = 0.38
        for i, eng in enumerate(engines):
            vals = [c.get(metric) or 0 for c in summary["engines"][eng]["chapters"]]
            off = (i - (len(engines) - 1) / 2) * width
            ax.bar([xi + off for xi in x], vals, width,
                   label=eng, color=colors.get(eng, None))
        ax.set_xlabel("chapter"); ax.set_ylabel(ylabel); ax.set_title(title)
        ax.set_xticks(x); ax.legend(); ax.grid(axis="y", alpha=0.3)
        fig.tight_layout(); fig.savefig(charts_dir / fname, dpi=120); plt.close(fig)

    _bar("elapsed_sec", "Per-chapter elapsed (graph vs agent)", "seconds", "compare_elapsed.png")
    _bar("best_score", "Per-chapter best score (graph vs agent)", "score", "compare_score.png")

    # GPU 시계열(엔진별 전체 VRAM 합)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for eng, csv_path in gpu_csvs.items():
        if not csv_path.exists():
            continue
        agg: dict[float, int] = {}
        with csv_path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                t = float(r["t_rel_sec"])
                agg[t] = agg.get(t, 0) + int(r["mem_used_mib"])
        ts = sorted(agg)
        ax.plot([t / 60 for t in ts], [agg[t] for t in ts],
                label=eng, color=colors.get(eng, None))
    ax.set_xlabel("minutes"); ax.set_ylabel("VRAM used (MiB, all GPUs)")
    ax.set_title("GPU VRAM over time (graph vs agent)")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(charts_dir / "compare_gpu.png", dpi=120); plt.close(fig)


# ── 리포트 ────────────────────────────────────────────────────────────────
def write_report(summary: dict, out_root: Path):
    e = summary["engines"]
    engs = list(e.keys())

    def cell(eng, key, suffix=""):
        v = e[eng].get(key)
        return f"{v}{suffix}" if v is not None else "—"

    lines = [
        f"# 엔진 비교 리포트 — graph vs agent",
        "",
        f"- 모델: `{summary['model']}`  ·  책: {summary['toc']}  ·  챕터: {summary['chapter_count']}개",
        f"- 생성: {summary['generated_at']}",
        f"- 공정성: 동일 design.json 주입(목차·write_brief·grounding 동일), push/pdf/trace off",
        "",
        "## 종합",
        "",
        "| 지표 | " + " | ".join(engs) + " | 우위 |",
        "|---|" + "---|" * (len(engs) + 1),
    ]

    def row(label, key, suffix="", lower_better=False):
        vals = {eng: e[eng].get(key) for eng in engs}
        nums = {k: v for k, v in vals.items() if isinstance(v, (int, float))}
        win = ""
        if len(nums) == len(engs) and len(set(nums.values())) > 1:
            win = (min if lower_better else max)(nums, key=nums.get)
        cells = " | ".join(f"{vals[eng]}{suffix}" if vals[eng] is not None else "—" for eng in engs)
        return f"| {label} | {cells} | {win or '='} |"

    lines += [
        row("총 소요(초)", "total_elapsed_sec", lower_better=True),
        row("평균 초/챕터", "avg_sec_per_chapter", lower_better=True),
        row("평균 best score", "avg_best_score"),
        row("최저 best score", "min_best_score"),
        row("flagged 챕터 수", "flagged_count", lower_better=True),
        row("총 초안 재작성(write)", "total_write_passes", lower_better=True),
        row("총 재검수(review pass)", "total_review_passes", lower_better=True),
        "",
        "## GPU",
        "",
    ]
    for eng in engs:
        g = e[eng].get("gpu", {})
        if g:
            parts = ", ".join(
                f"{k}: avg {v['mem_avg_mib']}MiB / max {v['mem_max_mib']}MiB, util avg {v['util_avg_pct']}%"
                for k, v in g.items())
            lines.append(f"- **{eng}** — {parts}")
    lines += ["", "## 차트", "",
              "![elapsed](charts/compare_elapsed.png)",
              "![score](charts/compare_score.png)",
              "![gpu](charts/compare_gpu.png)", "",
              "## 챕터별 상세", ""]
    for eng in engs:
        lines += [f"### {eng}", "",
                  "| ch | score | sec | write | pass | flagged |",
                  "|---|---|---|---|---|---|"]
        for c in e[eng]["chapters"]:
            lines.append(f"| {c['number']} | {c['best_score']} | {c['elapsed_sec']} | "
                         f"{c['write_count']} | {c['pass_count']} | {c['flagged']} |")
        lines.append("")
    (out_root / "comparison_report.md").write_text("\n".join(lines), encoding="utf-8")


# ── main ──────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="graph vs agent 엔진 비교")
    ap.add_argument("--toc", required=True)
    ap.add_argument("--limit", type=int, default=None, help="앞 N챕터만(스모크). 미지정=전체")
    ap.add_argument("--engines", default="graph,agent")
    ap.add_argument("--out", default=None, help="비교 출력 루트(기본 output/_compare/<slug>)")
    ap.add_argument("--force", action="store_true",
                    help="이미 완료된 엔진도 무시하고 재실행(기본은 완료분 재사용)")
    args = ap.parse_args()

    doc = json.loads(Path(args.toc).read_text(encoding="utf-8"))
    slug = title_to_slug(doc["title"])
    engines = [s.strip() for s in args.engines.split(",") if s.strip()]

    out_root = Path(args.out) if args.out else ADK_ROOT / "output" / "_compare" / slug
    out_root.mkdir(parents=True, exist_ok=True)

    # 기존 캐시 design.json 위치(없으면 에러).
    src_design = ADK_ROOT / "output" / slug / "design.json"
    if not src_design.exists():
        raise SystemExit(f"[오류] design 캐시 없음: {src_design}\n"
                         f"  먼저 'main.py --toc {args.toc} --no-push --no-pdf' 로 design 을 1회 생성하세요.")

    print(f"=== 엔진 비교 시작 === 책={doc['title']} · 엔진={engines} · limit={args.limit or '전체'}")
    results = {}
    gpu_csvs = {}
    for eng in engines:
        out_dir = out_root / eng
        n = seed_design(src_design, out_dir, args.limit)
        gpu_csv = out_root / f"gpu_usage_{eng}.csv"
        gpu_csvs[eng] = gpu_csv
        done = len(list((out_dir / "logs").glob("chapter-*.json"))) if (out_dir / "logs").exists() else 0

        if done >= n and not args.force:
            # 이미 완료 — 재실행 없이 로그의 챕터별 시간 합으로 elapsed 재구성(재사용).
            elapsed = sum(json.loads(p.read_text(encoding="utf-8")).get("elapsed_sec", 0) or 0
                          for p in (out_dir / "logs").glob("chapter-*.json"))
            print(f"\n[{eng}] 이미 {done}/{n}챕터 완료 → 재사용(실행 생략, {elapsed:.0f}s)")
        else:
            print(f"\n[{eng}] design 주입 {n}챕터 → 실행 시작 ({datetime.now():%H:%M:%S})")
            elapsed = run_engine(doc, slug, out_dir, eng, gpu_csv)
            print(f"[{eng}] 완료 — {elapsed:.0f}s")
        results[eng] = collect_metrics(out_dir, eng, elapsed, gpu_csv)

    summary = {
        "model": MODEL,
        "toc": doc["title"],
        "chapter_count": results[engines[0]]["chapter_count"],
        "limit": args.limit,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "engines": results,
    }
    (out_root / "comparison_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        make_charts(summary, out_root / "charts", gpu_csvs)
    except Exception as ex:
        print(f"[차트] 생성 실패(건너뜀): {ex}")
    write_report(summary, out_root)

    print(f"\n=== 완료 === 산출물: {out_root}")
    for eng in engines:
        r = results[eng]
        print(f"  {eng}: {r['total_elapsed_sec']:.0f}s · 평균점수 {r['avg_best_score']} · "
              f"flagged {r['flagged_count']}")


if __name__ == "__main__":
    main()

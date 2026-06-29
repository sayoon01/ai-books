"""
사출기(설비) 단위 금형 사출 통계 digest 빌더 — 전문가용 7장 보고서의 grounding 소스 생성.

왜 필요한가:
  기존 build_mold_digest.py 와 33001 API 는 통계를 전부 '금형(Model/PartNo) 단위'로만 집계한다.
  이 보고서는 축이 다르다 — '사출기(injection machine) 단위'다. 그런데
    (1) 33001 API 에는 사출기 단위 집계 엔드포인트가 없고,
    (2) cycle_type(NORMAL/SENSOR_NO_SIGNAL/SENSOR_ERROR/IDLE/WARMUP)은 CSV 컬럼에 없다(서버가 계산).
  그래서 원본 전처리본(MinIO mold-data/Dump2CSV_new)을 직접 스트리밍해
    - 사이클을 분류(가이드북 chapter-03 규칙 재현)하고
    - 사출기(=machine 컬럼, controller 폴더와 1:1) 단위로 집계해
    - 인용 가능한 실측 숫자만 담은 digest 를 만든다.

데이터 구조:
  mold-data/Dump2CSV_new/{controller}/{PartNo}/{날짜}_TotalData.csv
    - controller : P-M02-YYYY-A###  (사출기 한 대, 폴더명 = CSV의 controller 열)
    - machine    : toprun_A3 / woosung_48 ...  (controller 와 1:1, 실제 사출기 명)
    - PartNo     : 금형 코드(IMBN65285701 ...) = 두 번째 폴더
    - Model      : 제품군([GM]RSI ...)
  잡폴더(Telegram Desktop, master)는 제외.

분류 규칙(가이드북 chapter-03, 순서대로 첫 매치). per (사출기,금형) 폴더 모집단에서
채널 장착여부·IQR 을 먼저 구한 뒤 행별 판정:
  1) NO_SIGNAL    : T1_Max..T8_Max 전부 NaN(빈값)
  2) SENSOR_ERROR : (장착 T채널 T_Max==0 이 2개↑) OR (장착 P채널 P_Max==0 이 1개↑) OR CycleInterval==0
                    (미장착 채널 = 폴더 사이클 95%↑가 T_Max<30 / P_Max<50 → 판정 제외)
  3) WARMUP       : 장착 T채널의 T_Detect 최댓값 == 0 (레진 미도달)
  4) IDLE         : CycleInterval > P75 + 3*(P75-P25)
  5) NORMAL       : 위 어디에도 안 걸림 (= 분석 대상)
  ※ 재현 산출물이므로 33001 공식값과 100% 일치하지 않을 수 있음(미장착/IQR 모집단 범위 선택차).

실행:
  .venv/bin/python tools/build_machine_digest.py                       # 집계 + digest 생성(+캐시)
  .venv/bin/python tools/build_machine_digest.py --no-cache            # 캐시 무시하고 재집계
  .venv/bin/python tools/build_machine_digest.py --patch-design X.json # digest 를 design 의 grounding 으로 주입
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import boto3
from botocore.config import Config

# .env 자동 로드 (core.config 와 동일 위치)
ADK_ROOT = Path(__file__).resolve().parent.parent              # ADK_AGENT/
REPO_ROOT = ADK_ROOT.parent                                    # ai-books/
try:
    from dotenv import load_dotenv
    if (ADK_ROOT / ".env").exists():
        load_dotenv(ADK_ROOT / ".env")
except ImportError:
    pass

import os

ENDPOINT = os.getenv("MINIO_ENDPOINT", "https://minio.k-sw.mooo.com")
ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
BUCKET = os.getenv("MINIO_BUCKET", "mold-data")
PREFIX = "Dump2CSV_new/"

DEFAULT_OUT = REPO_ROOT / "data" / "machine-stats-digest.md"
CACHE_PATH = REPO_ROOT / "data" / "machine-agg.json"
DEFAULT_SLUG = "금형-사출-사출기-단위-가동품질-통계-분석-보고서"
DEFAULT_DESIGN = ADK_ROOT / "output" / DEFAULT_SLUG / "design.json"

JUNK_FOLDERS = {"Telegram Desktop", "master"}
CYCLE_TYPES = ["NORMAL", "NO_SIGNAL", "SENSOR_ERROR", "WARMUP", "IDLE"]

T_MAX = [f"T{i}_Max" for i in range(1, 9)]
T_DET = [f"T{i}_Detect" for i in range(1, 9)]
P_MAX = [f"P{i}_Max" for i in range(1, 9)]


# ── 유틸 ────────────────────────────────────────────────────────────────
def s3_client():
    if not (ACCESS_KEY and SECRET_KEY):
        print("[오류] MINIO_ACCESS_KEY / MINIO_SECRET_KEY 가 .env 에 없습니다.", file=sys.stderr)
        raise SystemExit(2)
    return boto3.client(
        "s3", endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", connect_timeout=15, read_timeout=120,
                      retries={"max_attempts": 3}))


def pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 2) if whole else 0.0


def fmt(n) -> str:
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    return f"{n:,}" if isinstance(n, int) else f"{n}"


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def common_prefixes(s3, prefix: str) -> list[str]:
    out = []
    tok = None
    while True:
        kw = dict(Bucket=BUCKET, Prefix=prefix, Delimiter="/", MaxKeys=1000)
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        out += [c["Prefix"] for c in r.get("CommonPrefixes", [])]
        if not r.get("IsTruncated"):
            return out
        tok = r["NextContinuationToken"]


def list_csv(s3, prefix: str) -> list[str]:
    out = []
    tok = None
    while True:
        kw = dict(Bucket=BUCKET, Prefix=prefix, MaxKeys=1000)
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        out += [o["Key"] for o in r.get("Contents", []) if o["Key"].lower().endswith(".csv")]
        if not r.get("IsTruncated"):
            return out
        tok = r["NextContinuationToken"]


# ── 분류 ────────────────────────────────────────────────────────────────
def classify_folder(rows: list[dict]) -> Counter:
    """한 (사출기,금형) 폴더의 사이클들을 5종으로 분류해 Counter 반환."""
    n = len(rows)
    dist = Counter()
    if n == 0:
        return dist

    # 미장착 채널 마스크: 폴더 사이클 95%↑가 임계 미만이면 '미장착' → 오류판정 제외
    def installed(cols, thr):
        mask = {}
        for c in cols:
            low = 0
            for r in rows:
                v = fnum(r.get(c))
                if v is None or v < thr:
                    low += 1
            mask[c] = (low / n) < 0.95
        return mask

    t_inst = installed(T_MAX, 30.0)
    p_inst = installed(P_MAX, 50.0)
    inst_det = [f"T{i}_Detect" for i in range(1, 9) if t_inst.get(f"T{i}_Max", False)]

    # IDLE 임계: CycleInterval 의 P75 + 3*IQR
    cis = sorted(v for v in (fnum(r.get("CycleInterval")) for r in rows) if v is not None)

    def quart(p):
        if not cis:
            return None
        i = min(len(cis) - 1, int(p * (len(cis) - 1)))
        return cis[i]

    p25, p75 = quart(0.25), quart(0.75)
    idle_thr = (p75 + 3.0 * (p75 - p25)) if (p25 is not None and p75 is not None) else float("inf")

    for r in rows:
        tmax = [fnum(r.get(c)) for c in T_MAX]
        if all(v is None for v in tmax):
            dist["NO_SIGNAL"] += 1
            continue
        ci = fnum(r.get("CycleInterval"))
        t_zero = sum(1 for c in T_MAX if t_inst[c] and fnum(r.get(c)) == 0)
        p_zero = sum(1 for c in P_MAX if p_inst[c] and fnum(r.get(c)) == 0)
        if t_zero >= 2 or p_zero >= 1 or ci == 0:
            dist["SENSOR_ERROR"] += 1
            continue
        det = [fnum(r.get(c)) for c in inst_det]
        det = [v for v in det if v is not None]
        if det and max(det) == 0:
            dist["WARMUP"] += 1
            continue
        if ci is not None and ci > idle_thr:
            dist["IDLE"] += 1
            continue
        dist["NORMAL"] += 1
    return dist


# ── 집계 ────────────────────────────────────────────────────────────────
def aggregate() -> dict:
    """MinIO 전체 스트리밍 집계. 사출기 단위 + 사출기×금형 구조 반환."""
    s3 = s3_client()
    controllers = [c for c in common_prefixes(s3, PREFIX)
                   if c.split("/")[-2] not in JUNK_FOLDERS]
    print(f"[집계] controller 폴더 {len(controllers)}개 (잡폴더 제외)", file=sys.stderr)

    machines = {}          # machine_name -> {...}
    mold_to_machines = defaultdict(set)   # PartNo -> {machine}

    for ci, cprefix in enumerate(controllers, 1):
        controller = cprefix.split("/")[-2]
        machine_name = None
        product_model = None
        molds = {}         # PartNo -> {"dist":Counter,"total":int,"model":str,"part":str}
        for mprefix in common_prefixes(s3, cprefix):
            partno = mprefix.split("/")[-2]
            rows = []
            for key in list_csv(s3, mprefix):
                body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode("utf-8", "replace")
                rd = csv.DictReader(io.StringIO(body))
                for r in rd:
                    rows.append(r)
            if not rows:
                continue
            if machine_name is None:
                machine_name = (rows[0].get("machine") or controller).strip()
                product_model = (rows[0].get("Model") or "").strip()
            dist = classify_folder(rows)
            molds[partno] = {
                "dist": dict(dist),
                "total": sum(dist.values()),
                "model": (rows[0].get("Model") or "").strip(),
                "part": (rows[0].get("PartName") or "").strip(),
            }
            mold_to_machines[partno].add(machine_name or controller)

        if machine_name is None:        # CSV 없는 controller
            machine_name = controller
        mdist = Counter()
        for m in molds.values():
            mdist.update(m["dist"])
        # 도입연도: controller 의 P-M02-YYYY-A###
        year = ""
        parts = controller.split("-")
        for p in parts:
            if p.isdigit() and len(p) == 4:
                year = p
                break
        maker = machine_name.split("_")[0] if "_" in machine_name else ""
        machines[machine_name] = {
            "controller": controller,
            "maker": maker,
            "year": year,
            "product_model": product_model or "",
            "molds": molds,
            "mold_count": len(molds),
            "dist": dict(mdist),
            "total": sum(mdist.values()),
        }
        print(f"  [{ci}/{len(controllers)}] {machine_name:14} ({controller})  "
              f"금형 {len(molds):>2}  사이클 {sum(mdist.values()):>7,}", file=sys.stderr)

    shared = {p: sorted(ms) for p, ms in mold_to_machines.items() if len(ms) >= 2}
    return {"machines": machines, "shared_molds": shared}


# ── digest 렌더 ──────────────────────────────────────────────────────────
def render(agg: dict) -> str:
    machines = agg["machines"]
    shared = agg.get("shared_molds", {})
    L: list[str] = []
    w = L.append

    # 전체 합계
    grand = Counter()
    for m in machines.values():
        grand.update(m["dist"])
    grand_total = sum(grand.values())
    n_machines = len(machines)
    makers = Counter(m["maker"] for m in machines.values() if m["maker"])
    distinct_molds = {p for m in machines.values() for p in m["molds"]}

    # ── 0. 메타·방법론 ────────────────────────────────────────────────
    w("# 금형 사출 — 사출기(설비) 단위 가동·품질 통계 digest")
    w("")
    w(f"- 데이터 출처: MinIO `{BUCKET}/{PREFIX}` (33001 분석 시스템이 사용하는 전처리본)")
    w(f"- 집계 단위: 사출기(injection machine, CSV의 `machine` 열 = `controller` 폴더와 1:1)")
    w("- 본 digest 의 모든 수치는 원본 CSV 를 직접 스트리밍해 집계한 실측값이다. 본문은 이 값만 인용한다.")
    w("- cycle_type 은 CSV 에 없어 가이드북 분류 규칙으로 재현했다(아래). 33001 공식 집계와 미세 차이 가능.")
    w("")
    w("분류 규칙(순서대로 첫 매치):")
    w("")
    w("| 유형 | 판정 |")
    w("|---|---|")
    w("| NO_SIGNAL | T1~T8_Max 전부 결측(NaN) — 센서 미연결 |")
    w("| SENSOR_ERROR | 장착 T채널 T_Max=0 이 2개↑, 또는 장착 P채널 P_Max=0 이 1개↑, 또는 사이클타임=0 |")
    w("| WARMUP | 장착 T채널 T_Detect 최댓값=0 — 레진 미도달(예열) |")
    w("| IDLE | 사이클타임 > P75 + 3×IQR — 비정상적 장시간(휴지) |")
    w("| NORMAL | 위 어디에도 안 걸림 — 분석 대상 |")
    w("")
    w("(장착여부·IQR 임계는 각 사출기×금형 폴더 모집단에서 계산. 미장착 채널=폴더 95%↑가 T<30℃/P<50bar.)")
    w("")

    # ── 1. 총괄 ───────────────────────────────────────────────────────
    w("## 1. 전체 총괄")
    w("")
    w(f"- 가동 사출기: {n_machines} 대 (" + ", ".join(f"{k} {v}대" for k, v in makers.most_common()) + ")")
    w(f"- 가동 금형(고유 PartNo): {len(distinct_molds)} 종")
    w(f"- 총 수집 사이클: {fmt(grand_total)} 회")
    w("")
    w("전체 사이클 유형 분포:")
    w("")
    w("| 유형 | 건수 | 비중 |")
    w("|---|---|---|")
    for k in CYCLE_TYPES:
        v = grand.get(k, 0)
        w(f"| {k} | {fmt(v)} | {pct(v, grand_total)}% |")
    w("")

    rows = sorted(machines.items(), key=lambda kv: -kv[1]["total"])

    # ── 2. 사출기 15대 총괄표 ─────────────────────────────────────────
    w("## 2. 사출기별 설비 현황 총괄")
    w("")
    w("| 사출기 | controller | 제조계열 | 도입연도 | 가동금형수 | 총사이클 | NORMAL | NORMAL% |")
    w("|---|---|---|---|---|---|---|---|")
    for name, m in rows:
        nrm = m["dist"].get("NORMAL", 0)
        w(f"| {name} | {m['controller']} | {m['maker']} | {m['year']} | "
          f"{m['mold_count']} | {fmt(m['total'])} | {fmt(nrm)} | {pct(nrm, m['total'])}% |")
    w("")

    # ── 3. 사출기 × cycle_type 교차표 ─────────────────────────────────
    w("## 3. 사출기별 사이클 유형 분해 (건수)")
    w("")
    w("| 사출기 | NORMAL | NO_SIGNAL | SENSOR_ERROR | WARMUP | IDLE | 합계 |")
    w("|---|---|---|---|---|---|---|")
    for name, m in rows:
        d = m["dist"]
        w(f"| {name} | " + " | ".join(fmt(d.get(k, 0)) for k in CYCLE_TYPES) + f" | {fmt(m['total'])} |")
    w("")
    w("### 3-1. 사출기별 사이클 유형 분해 (비율 %)")
    w("")
    w("| 사출기 | NORMAL% | NO_SIGNAL% | SENSOR_ERROR% | WARMUP% | IDLE% |")
    w("|---|---|---|---|---|---|")
    for name, m in rows:
        d = m["dist"]
        t = m["total"]
        w(f"| {name} | " + " | ".join(f"{pct(d.get(k, 0), t)}%" for k in CYCLE_TYPES) + " |")
    w("")

    # ── 4. 데이터 품질 랭킹 ───────────────────────────────────────────
    w("## 4. 데이터 품질(센서 안정성) — 센서 에러 비율 랭킹")
    w("")
    w("센서계 에러 = NO_SIGNAL + SENSOR_ERROR (수집 안정성 문제, 제품 불량 아님).")
    w("")
    w("| 사출기 | NO_SIGNAL | SENSOR_ERROR | 센서에러합 | 센서에러율 |")
    w("|---|---|---|---|---|")
    def senserr(m):
        return m["dist"].get("NO_SIGNAL", 0) + m["dist"].get("SENSOR_ERROR", 0)
    for name, m in sorted(machines.items(), key=lambda kv: -pct(senserr(kv[1]), kv[1]["total"])):
        se = senserr(m)
        w(f"| {name} | {fmt(m['dist'].get('NO_SIGNAL', 0))} | {fmt(m['dist'].get('SENSOR_ERROR', 0))} | "
          f"{fmt(se)} | {pct(se, m['total'])}% |")
    w("")

    # ── 5. 가동 안정성: WARMUP / IDLE ─────────────────────────────────
    w("## 5. 가동 안정성 — WARMUP / IDLE 비율")
    w("")
    w("| 사출기 | WARMUP | WARMUP% | IDLE | IDLE% |")
    w("|---|---|---|---|---|")
    for name, m in sorted(machines.items(), key=lambda kv: -pct(kv[1]['dist'].get('IDLE', 0), kv[1]['total'])):
        d = m["dist"]
        t = m["total"]
        w(f"| {name} | {fmt(d.get('WARMUP', 0))} | {pct(d.get('WARMUP', 0), t)}% | "
          f"{fmt(d.get('IDLE', 0))} | {pct(d.get('IDLE', 0), t)}% |")
    w("")

    # ── 6. 사출기→금형 매핑 ───────────────────────────────────────────
    w("## 6. 사출기별 가동 금형 상세")
    w("")
    for name, m in rows:
        w(f"### {name} ({m['controller']}) — 금형 {m['mold_count']}종, 총 {fmt(m['total'])} 사이클")
        w("")
        w("| 금형(PartNo) | 제품군(Model) | 파트명 | 총사이클 | NORMAL | NORMAL% |")
        w("|---|---|---|---|---|---|")
        for pn, mm in sorted(m["molds"].items(), key=lambda kv: -kv[1]["total"]):
            nrm = mm["dist"].get("NORMAL", 0)
            w(f"| {pn} | {mm['model']} | {mm['part']} | {fmt(mm['total'])} | {fmt(nrm)} | {pct(nrm, mm['total'])}% |")
        w("")

    # ── 7. N:N — 여러 사출기에 걸친 금형 ──────────────────────────────
    w("## 7. 여러 사출기에 걸쳐 사용된 금형 (N:N)")
    w("")
    if shared:
        w(f"고유 금형 {len(distinct_molds)}종 중 {len(shared)}종이 2대 이상의 사출기에서 가동되었다.")
        w("")
        w("| 금형(PartNo) | 사용 사출기 수 | 사출기 목록 |")
        w("|---|---|---|")
        for pn, ms in sorted(shared.items(), key=lambda kv: -len(kv[1])):
            w(f"| {pn} | {len(ms)} | {', '.join(ms)} |")
        w("")
    else:
        w("2대 이상 사출기에 걸친 금형은 없다(모든 금형이 단일 사출기 전용).")
        w("")

    return "\n".join(L)


def patch_design(design_path: Path, digest: str) -> None:
    """design.json 의 grounding_digest 를 전체 digest 로 덮어쓴다(Design 과압축 보정)."""
    if not design_path.exists():
        print(f"[패치 건너뜀] design.json 없음: {design_path}\n"
              f"  → main.py --design-only 로 design.json 을 먼저 만든 뒤 --patch-design 하세요.",
              file=sys.stderr)
        return
    d = json.loads(design_path.read_text(encoding="utf-8"))
    old = len(d.get("grounding_digest", ""))
    d["grounding_digest"] = digest
    design_path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[패치] grounding_digest {old} → {len(digest)}자 교체: {design_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="사출기 단위 금형 사출 통계 digest 빌더")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="출력 경로(.md)")
    ap.add_argument("--no-cache", action="store_true", help="집계 캐시 무시하고 재집계")
    ap.add_argument("--patch-design", nargs="?", const=str(DEFAULT_DESIGN), default=None,
                    metavar="DESIGN_JSON",
                    help="digest 생성 후 design.json 의 grounding_digest 를 전체 digest 로 교체")
    args = ap.parse_args()

    if CACHE_PATH.exists() and not args.no_cache:
        print(f"[캐시] {CACHE_PATH} 사용 (재집계하려면 --no-cache)", file=sys.stderr)
        agg = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    else:
        agg = aggregate()
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[캐시] 집계 결과 저장: {CACHE_PATH}", file=sys.stderr)

    text = render(agg)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"[완료] {out}  ({len(text):,}자)")

    if args.patch_design is not None:
        patch_design(Path(args.patch_design), text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

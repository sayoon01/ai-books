"""
B. 산출물 유사도 — graph vs agent 가 '같은 챕터'를 얼마나 비슷하게 썼는지.

두 엔진은 단계 로직(write/review/revise 판정 함수)을 공유하므로 결과가 거의 같을 수 있다.
거의 같으면 → 품질 논쟁 무의미, 결정은 속도·코드 단순성·API 지원으로 환원된다.

의존성 없음(difflib + 토큰 Jaccard). 임베딩 안 씀.
입력: output/_compare/<slug>/{graph,agent}/chapter-*.md
출력: output/_compare/<slug>/similarity.json  + 콘솔 표
"""
import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ADK_ROOT = Path(__file__).resolve().parent.parent
_WORD = re.compile(r"\w+", re.UNICODE)


def normalize(text: str) -> str:
    """H1 제목 줄 제거 + 공백 정규화(엔진 무관 비교)."""
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("# ")]
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def chapter_num(p: Path) -> int:
    m = re.search(r"chapter-(\d+)", p.name)
    return int(m.group(1)) if m else -1


def md_by_chapter(d: Path) -> dict[int, Path]:
    return {chapter_num(p): p for p in d.glob("chapter-*.md")}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a or b) else 1.0


def main():
    ap = argparse.ArgumentParser(description="graph vs agent 산출물 유사도(B)")
    ap.add_argument("--root", required=True, help="output/_compare/<slug> 경로")
    ap.add_argument("--a", default="graph")
    ap.add_argument("--b", default="agent")
    args = ap.parse_args()

    root = Path(args.root)
    A, B = md_by_chapter(root / args.a), md_by_chapter(root / args.b)
    nums = sorted(set(A) & set(B))
    if not nums:
        raise SystemExit(f"[오류] 공통 챕터 없음. {root}/{args.a}, {root}/{args.b} 확인.")

    rows = []
    print(f"=== 유사도(B): {args.a} vs {args.b} === 공통 {len(nums)}챕터\n")
    print(f"{'ch':>3} | {'seqratio':>8} | {'jaccard':>7} | {'len_a':>6} | {'len_b':>6} | {'len%':>5}")
    print("-" * 52)
    for n in nums:
        ta, tb = normalize(A[n].read_text(encoding="utf-8")), normalize(B[n].read_text(encoding="utf-8"))
        seq = SequenceMatcher(None, ta, tb).ratio()
        jac = jaccard(set(tokens(ta)), set(tokens(tb)))
        la, lb = len(ta.replace(" ", "")), len(tb.replace(" ", ""))
        lenpct = round(100 * min(la, lb) / max(la, lb)) if max(la, lb) else 100
        rows.append({"chapter": n, "seq_ratio": round(seq, 3), "jaccard": round(jac, 3),
                     "chars_a": la, "chars_b": lb, "len_pct": lenpct})
        print(f"{n:>3} | {seq:>8.3f} | {jac:>7.3f} | {la:>6} | {lb:>6} | {lenpct:>4}%")

    avg_seq = sum(r["seq_ratio"] for r in rows) / len(rows)
    avg_jac = sum(r["jaccard"] for r in rows) / len(rows)
    # 해석: jaccard 0.5+ = 어휘 상당 겹침, seq 0.6+ = 문장구조도 유사.
    if avg_jac >= 0.6 and avg_seq >= 0.5:
        verdict = "거의 같음 — 품질 논쟁 불필요, 속도·단순성·API로 결정"
    elif avg_jac >= 0.4:
        verdict = "상당히 유사 — 부분 차이만, A(블라인드 심사)로 미세 우열 확인 권장"
    else:
        verdict = "유의미하게 다름 — A(블라인드 심사)로 품질 우열 판정 필요"

    out = {"a": args.a, "b": args.b, "chapters": len(nums),
           "avg_seq_ratio": round(avg_seq, 3), "avg_jaccard": round(avg_jac, 3),
           "verdict": verdict, "per_chapter": rows}
    (root / "similarity.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n평균 seq_ratio {avg_seq:.3f} · 평균 jaccard {avg_jac:.3f}")
    print(f"판정: {verdict}")
    print(f"저장: {root / 'similarity.json'}")


if __name__ == "__main__":
    main()

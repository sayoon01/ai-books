"""
오케스트레이터 — 4개 에이전트를 코드로 엮는 상태머신(코드 오케스트레이션).

흐름:
  [Plan] → plan.json
     → [Artifacts.build]  (plan.artifacts 대로 데이터에서 표/그림/통계 실제 생성)
     → for section in plan.sections:
            [Write] → 초안
            loop(PASS_MAX): [Review](다른 모델) → gate → [Revise]
            best_draft 저장 (output/<slug>/sections/<id>.tex)
     → trace(logs/) 기록
반환: {plan, sections:{id: latex}, order:[...], meta}
조립(main.tex)·CLI 는 run.py 가 담당한다.
"""
import json
import re
from pathlib import Path

from core.config import OUTPUT_ROOT, MODEL, REVIEW_MODEL, MIN_CHARS, WRITE_MAX, PASS_MAX
from core.grounding import read_source
from core.usage import METER
from agents.common import axes_for, get_rubric
from agents.plan import run_or_load_plan
from agents.write import write_section, length_decision
from agents.review import do_review, gate_decision
from agents.revise import revise_section


def _summarize(latex_body: str, limit: int = 360) -> str:
    """앞 섹션 요약(가벼움) — LLM 호출 없이 LaTeX 명령 제거 후 앞부분만."""
    txt = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?", " ", latex_body)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:limit] + ("…" if len(txt) > limit else "")


def _write_with_guard(plan, section, grounding, prev, sec_arts, min_chars,
                      length_hint, target_chars, log):
    """초안 생성 + 길이 가드 재작성 루프. 반환: 본문."""
    body, wc = "", 0
    while True:
        body = write_section(plan, section, grounding, prev, sec_arts,
                             length_hint, target_chars)
        route, wc = length_decision(body, min_chars, wc)
        if route == "ok":
            if len(body.strip()) < min_chars:
                log(f"    [가드] 끝까지 {len(body.strip())}자 — flagged 후 진행")
            return body, wc
        log(f"    [가드] 본문 {len(body.strip())}자 < {min_chars} → 재작성({wc}/{WRITE_MAX})")


def _refine_section(state: dict, log) -> dict:
    """한 섹션의 review→gate→revise 루프. state 를 갱신하며 best_* 를 채운다."""
    while True:
        updates, err = do_review(state)
        state.update(updates)
        if err:
            log(f"    [심사 미수렴] {err} — flagged 후 종료")
        else:
            r = state["review"]
            log(f"    [심사:{REVIEW_MODEL}] score {r['score']} · issues {len(r['issues'])} · "
                f"best {state.get('best_score')}")

        stop, info, gupd = gate_decision(state)
        state.update(gupd)
        if stop:
            log(f"    [게이트] 종료 — {info['kind']} "
                f"(score {info['score']}, 위반 {info['violations']})")
            return state
        log(f"    [게이트] 재수정({info['kind']}) 위반 {info['violations']} · 약한축 {list(info['weak'])}")
        state["draft"] = revise_section(
            state["plan"], state["section"], state["review"], state["draft"], state["grounding"])


def run_paper(spec: dict, *, force: bool = False, limit: int = 0) -> dict:
    """논문 한 편을 생성한다. spec: {slug, topic, venue?, source?}."""
    slug = spec["slug"]
    out = OUTPUT_ROOT / slug
    (out / "sections").mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(parents=True, exist_ok=True)

    def log(msg): print(msg)

    rubric = get_rubric(spec.get("tier"))
    tier = (spec.get("tier") or "conference").lower()
    log(f"\n=== 논문 생성: {slug} ===")
    log(f"  생성 모델 {MODEL} · 검수 모델 {REVIEW_MODEL}")
    log(f"  등급 {tier} (게이트 {rubric['quality_gate']} · 목표 {rubric['target_score']} · "
        f"섹션 분량 ~{rubric['min_chars']}자)")

    # ── grounding (실측 자료) ──
    source_text = read_source(spec.get("source"), slug)

    # ── ① Plan ──
    plan = run_or_load_plan(spec["topic"], source_text, out,
                            venue=spec.get("venue", ""), tier=tier, force=force)

    # ── Artifacts: plan 대로 표/그림/통계 실제 생성 (수치는 데이터에서) ──
    data_digest = source_text
    manifest: list[dict] = []
    try:
        from artifacts.build import build_artifacts
        manifest, extra_digest = build_artifacts(plan, source_text, out)
        if extra_digest:
            data_digest = (source_text + "\n\n[생성된 자료의 실제 값]\n" + extra_digest).strip()
        log(f"  [artifacts] {len(manifest)}개 생성")
    except Exception as e:
        log(f"  [artifacts] 건너뜀({e}) — 본문은 자료 없이/참조만 진행")

    art_by_id = {a["id"]: a for a in plan.get("artifacts", [])}

    # ── 섹션 루프 ──
    sections, order, prev_summaries, sec_meta = {}, [], [], []
    todo = plan["sections"][:limit] if limit else plan["sections"]
    for i, section in enumerate(todo, 1):
        sid = section["id"]
        applicable = axes_for(section)
        log(f"\n[{i}/{len(todo)}] 섹션 '{sid}' — {section.get('title','')}  축={applicable}")
        sec_arts = [art_by_id[a] for a in section.get("artifact_ids", []) if a in art_by_id]

        is_abs = sid == "abstract"
        target_chars = section.get("target_chars") or (
            rubric["abstract_chars"] if is_abs else rubric["min_chars"])
        # 길이 가드(빈 섹션 방지)는 목표의 일부만 강제 — 장문에서 과도한 재작성 방지.
        guard_floor = int(target_chars * 0.7) if is_abs else max(MIN_CHARS, int(target_chars * 0.6))

        draft, _ = _write_with_guard(plan, section, data_digest, prev_summaries, sec_arts,
                                     guard_floor, rubric["length_hint"], target_chars, log)

        state = {
            "plan": plan, "section": section, "draft": draft, "grounding": data_digest,
            "quality_gate": rubric["quality_gate"], "target_score": rubric["target_score"],
            "applicable_axes": applicable, "rubric": rubric,
            "best_score": -1, "best_draft": draft, "best_review": None,
            "pass_count": 0, "last_score": -1,
        }
        state = _refine_section(state, log)

        best = state.get("best_draft") or state["draft"]
        sections[sid] = best
        order.append(sid)
        (out / "sections" / f"{sid}.tex").write_text(best, encoding="utf-8")
        prev_summaries.append(f"[{section.get('title', sid)}] {_summarize(best)}")
        sec_meta.append({"id": sid, "title": section.get("title", ""),
                         "score": state.get("best_score"),
                         "chars": len(best),
                         "issues": len((state.get("best_review") or {}).get("issues", []))})

    # ── trace / 메타 ──
    usage = METER.snapshot()
    meta = {"slug": slug, "model": MODEL, "review_model": REVIEW_MODEL, "tier": tier,
            "sections": sec_meta,
            "tokens": {"prompt": usage.prompt, "completion": usage.completion,
                       "total": usage.total, "calls": usage.calls},
            "tokens_by_model": {k: vars(v) for k, v in METER.by_model().items()}}
    (out / "logs" / "run.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    log(f"\n=== 완료: 섹션 {len(order)}개 · 토큰 {usage.total} ===")
    return {"plan": plan, "sections": sections, "order": order,
            "manifest": manifest, "meta": meta, "out": out}

"""
드라이버 — Design(1회) → 챕터별 그래프 Workflow 실행 → 저장 / push / PDF.

ADK 몫: 챕터 1개의 write→guard→review→gate→revise 그래프.
파이썬 몫: design 로드/생성, 챕터 for문, summaries 누적, 파일 저장, push, PDF (전부 I/O).
"""
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.genai import types

from agent.design import run_or_load_design
from agent.graph import build_chapter_graph
from core.source_reader import read_source, unverified_numbers
from core.textutil import normalize_math, strip_title_h1, chapter_filename
from core.llm import MODEL

_REQUIRED = ("title", "language", "description", "target_reader", "writing_guidelines")
_SKIP_KEYS = {"chapters", "source"}                       # config(정체성)에서 제외
QUALITY_GATE = 80
TARGET_SCORE = 90
MIN_CHARS = 500
_GO = types.Content(role="user", parts=[types.Part(text="go")])


def _validate(doc: dict) -> None:
    missing = [k for k in _REQUIRED if not doc.get(k)]
    if missing:
        raise ValueError(f"필수 필드 누락: {missing}")


def _config(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in _SKIP_KEYS}


async def generate(doc: dict, output_dir: Path, slug: str, *,
                   force_redesign: bool = False, push: bool = True, do_pdf: bool = True) -> None:
    _validate(doc)
    title = doc["title"]
    config = _config(doc)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    # --- Design (책당 1회): design.json 있으면 로드, 없으면 생성 ---
    source_text = read_source(doc.get("source"), slug)
    design_config = {**config, **({"chapters": doc["chapters"]} if doc.get("chapters") else {})}
    auto_outline = not doc.get("chapters")
    design = run_or_load_design(design_config, source_text, output_dir, force=force_redesign)

    chapters = design["chapters"]
    write_brief = design["write_brief"]
    grounding = design["grounding_digest"]

    print(f"\n생성 시작: {title}  (챕터 {len(chapters)}개, source={'있음' if source_text else '없음'})\n")

    graph = build_chapter_graph()
    runner = InMemoryRunner(agent=graph, app_name="adk_book")
    base = {"config": config, "write_brief": write_brief, "grounding": grounding,
            "min_chars": MIN_CHARS, "quality_gate": QUALITY_GATE, "target_score": TARGET_SCORE}

    summaries: list[str] = []
    t_start = time.perf_counter()
    chapter_times: list[float] = []

    for i, ch in enumerate(chapters, 1):
        num = ch.get("number", i)
        ctitle = ch["title"]
        print(f"--- 챕터 {num}: {ctitle} ---")
        t_ch = time.perf_counter()

        sess = await runner.session_service.create_session(
            app_name="adk_book", user_id="u",
            state={**base, "chapter": ch, "prev_summaries": summaries[:],
                   "last_score": -1, "best_score": -1, "write_count": 0,
                   "pass_count": 0, "history": []})
        async for _ in runner.run_async(user_id="u", session_id=sess.id, new_message=_GO):
            pass
        st = (await runner.session_service.get_session(
            app_name="adk_book", user_id="u", session_id=sess.id)).state

        # keep-best: 최고 점수 초안을 최종으로(없으면 마지막 draft 폴백).
        final = st.get("best_draft") or st.get("draft", "") or "<!-- 생성 실패: draft 없음 -->"
        flagged = st.get("flagged", False)
        final_bad = unverified_numbers(final, grounding) if grounding else []

        content = f"# {num}. {ctitle}\n\n{normalize_math(strip_title_h1(final))}"
        filename = chapter_filename(num, ctitle)
        (output_dir / filename).write_text(content, encoding="utf-8")

        ch_elapsed = time.perf_counter() - t_ch
        chapter_times.append(ch_elapsed)
        (log_dir / f"chapter-{num:02d}.json").write_text(json.dumps({
            "chapter": {"number": num, "title": ctitle},
            "flagged": flagged, "best_score": st.get("best_score"),
            "final_review": st.get("best_review") or st.get("review"),
            "write_count": st.get("write_count"), "pass_count": st.get("pass_count"),
            "unverified_remaining": final_bad, "elapsed_sec": round(ch_elapsed, 1),
            # 전 과정: write(초안) → review(매 패스) → gate(판정) 순서대로 누적
            "history": st.get("history", []),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        flag = "  ⚠flagged" if flagged else ""
        print(f"  저장: {filename}  (소요 {ch_elapsed:.0f}s){flag}")

        if push:
            from publish.github_push import push_chapter, update_meta
            push_chapter(slug, num, ctitle, content, filename=filename)
            update_meta(slug, doc, completed=num)

        summaries.append(f"{num}. {ctitle}: {ch.get('description', '')}")
        print()

    gen_elapsed = time.perf_counter() - t_start

    if do_pdf and push:
        try:
            from publish.github_push import push_pdf, REPO_ROOT
            from publish.pdf_export import build_pdf
            pdf_path = build_pdf(REPO_ROOT / slug, slug, title,
                                 language=config.get("language", "ko"),
                                 subtitle=config.get("description", ""),
                                 model=MODEL, auto_outline=auto_outline, gen_seconds=gen_elapsed)
            if pdf_path:
                push_pdf(slug, pdf_path)
        except Exception as e:
            print(f"  [PDF] 생성 실패(건너뜀): {e}")

    total = time.perf_counter() - t_start
    mins, secs = divmod(int(total), 60)
    avg = (sum(chapter_times) / len(chapter_times)) if chapter_times else 0
    print(f"[완료] {title} — 총 {mins}분 {secs}초 "
          f"(챕터 {len(chapter_times)}개, 평균 {avg:.0f}s/챕터)")
    with (log_dir / "generation_time.log").open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')}\t{slug}\t"
                f"total={total:.0f}s\tchapters={len(chapter_times)}\tavg={avg:.0f}s\n")

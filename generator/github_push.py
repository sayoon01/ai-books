"""
작성 단위 완성마다 GitHub에 자동 커밋+푸시하는 모듈 (장르 무관).
"""
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent  # ai-books/

_UNITS_KEYS = ("units", "chapters", "sections")


def _units(doc: dict) -> list:
    for k in _UNITS_KEYS:
        if k in doc:
            return doc[k]
    return []


def _git(args: list[str]) -> str:
    result = subprocess.run(
        ["git"] + args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 실패:\n{result.stderr}")
    return result.stdout.strip()


def push_unit(slug: str, num: int, title: str, content: str) -> None:
    """작성 단위 파일을 저장하고 GitHub에 커밋+푸시"""
    doc_dir = REPO_ROOT / slug
    doc_dir.mkdir(parents=True, exist_ok=True)

    filename = f"unit-{num:02d}.md"
    (doc_dir / filename).write_text(content, encoding="utf-8")

    _git(["add", str(doc_dir / filename)])
    _git(["commit", "-m", f"feat({slug}): unit-{num:02d} {title}"])
    _git(["push"])
    print(f"  [GitHub] 푸시 완료: {slug}/{filename}")


def update_meta(slug: str, doc: dict, completed: int) -> None:
    """meta.json 갱신 후 커밋+푸시"""
    doc_dir = REPO_ROOT / slug
    doc_dir.mkdir(parents=True, exist_ok=True)

    total = len(_units(doc))
    meta = {
        "title":     doc["title"],
        "language":  doc.get("language", "ko"),
        "doc_type":  doc.get("doc_type", ""),
        "model":     "gemma4:31b",
        "total":     total,
        "completed": completed,
        "status":    "done" if completed >= total else "in_progress",
    }
    meta_path = doc_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    _git(["add", str(meta_path)])
    _git(["commit", "-m", f"chore({slug}): meta.json 업데이트 ({completed}/{total})"])
    _git(["push"])


def update_readme(slug: str, doc: dict) -> None:
    """루트 README.md 문서 목록 테이블 갱신 후 커밋+푸시"""
    readme_path = REPO_ROOT / "README.md"

    docs: dict[str, dict] = {}
    for meta_file in sorted(REPO_ROOT.glob("*/meta.json")):
        docs[meta_file.parent.name] = json.loads(meta_file.read_text(encoding="utf-8"))

    rows = ["| 제목 | 유형 | 언어 | 진행 | 모델 | 상태 |",
            "|---|---|---|---|---|---|"]
    for s, m in docs.items():
        status = "✅ 완료" if m.get("status") == "done" else "🔄 진행중"
        # 구 키(total_chapters) 폴백
        total = m.get("total", m.get("total_chapters", "?"))
        done = m.get("completed", m.get("completed_chapters", "?"))
        rows.append(
            f"| [{m['title']}](./{s}) "
            f"| {m.get('doc_type', '')} "
            f"| {m.get('language', 'ko')} "
            f"| {done}/{total} "
            f"| {m.get('model', '')} "
            f"| {status} |"
        )

    # 문서 테이블은 마커 블록 안에만 갱신 → README의 수동 설명은 보존
    start, end = "<!-- DOCS:START -->", "<!-- DOCS:END -->"
    block = f"{start}\n\n" + "\n".join(rows) + f"\n\n{end}"
    if readme_path.exists():
        cur = readme_path.read_text(encoding="utf-8")
        if start in cur and end in cur:
            import re
            content = re.sub(re.escape(start) + r".*?" + re.escape(end), block,
                             cur, flags=re.DOTALL)
        else:
            content = cur.rstrip() + "\n\n## 생성된 문서\n\n" + block + "\n"
    else:
        content = "# AI Books\n\n## 생성된 문서\n\n" + block + "\n"
    readme_path.write_text(content, encoding="utf-8")

    _git(["add", "README.md"])
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT)
    if result.returncode != 0:
        _git(["commit", "-m", "docs: 문서 목록 업데이트"])
        _git(["push"])
    print("  [GitHub] README.md 업데이트 완료")

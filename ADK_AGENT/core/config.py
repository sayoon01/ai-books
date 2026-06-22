"""
중앙 설정 — 흩어져 있던 튜닝 값을 한 곳에. 모두 env 로 덮어쓸 수 있다.

원칙:
- 여기엔 '튜닝 가능한 값'만 둔다(모델·품질 게이트·루프 상한·경로·플래그).
  도메인 데이터(정규식·폰트표·프롬프트·위반 타입 집합)는 각 모듈에 그대로 둔다.
- import 시 .env 를 자동 로드한다 → 쉘에 일일이 export 안 해도 된다.
  (ADK_AGENT/.env, ADK_AGENT/observability/.env 순으로 있으면 로드)
"""
import os
from pathlib import Path

# ── 경로 ──────────────────────────────────────────────────────────────
PKG_ROOT = Path(__file__).resolve().parent.parent          # ADK_AGENT/
REPO_ROOT = PKG_ROOT.parent                                # ai-books/  (git push 대상 루트)

# ── .env 자동 로드(있으면) ─────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    for _envp in (PKG_ROOT / ".env", PKG_ROOT / "observability" / ".env"):
        if _envp.exists():
            load_dotenv(_envp)
except ImportError:
    pass


def _int(key: str, default: int) -> int:
    return int(os.getenv(key, default))


def _float(key: str, default: float) -> float:
    return float(os.getenv(key, default))


def _bool(key: str, default: bool) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes", "on")


# ── 모델 / LLM (core/llm.py) ──────────────────────────────────────────
MODEL = os.getenv("ADK_MODEL", "gemma4:31b")
LLM_TEMPERATURE = _float("ADK_TEMPERATURE", 0.7)
LLM_NUM_CTX = _int("ADK_NUM_CTX", 32768)
LLM_REPEAT_PENALTY = _float("ADK_REPEAT_PENALTY", 1.2)
LLM_KEEP_ALIVE = os.getenv("ADK_KEEP_ALIVE", "30m")

# ── 품질 게이트 (pipeline.py / 그래프 노드) ────────────────────────────
QUALITY_GATE = _int("ADK_QUALITY_GATE", 80)               # 위반 0 + 이 점수 이상이면 통과
TARGET_SCORE = _int("ADK_TARGET_SCORE", 90)               # 이 점수면 더 안 끌어올림
MIN_CHARS = _int("ADK_MIN_CHARS", 500)                    # 본문 최소 길이(가드)

# ── 루프 상한 ─────────────────────────────────────────────────────────
WRITE_MAX = _int("ADK_WRITE_MAX", 3)                      # 초안 재작성 상한 (write.py)
PASS_MAX = _int("ADK_PASS_MAX", 3)                        # review→revise 재수정 상한 (review.py)

# ── 목차 (design.py) ──────────────────────────────────────────────────
DEFAULT_CHAPTER_COUNT = _int("ADK_DEFAULT_CHAPTER_COUNT", 10)

# ── grounding 소스 (core/grounding.py) ────────────────────────────────
MAX_FILE_CHARS = _int("ADK_MAX_FILE_CHARS", 12000)       # 토큰 예산 보호용 절단 한도

# ── 퍼블리시 (github_push.py) ─────────────────────────────────────────
PUSH_ENABLED = _bool("ADK_PUSH_ENABLED", True)

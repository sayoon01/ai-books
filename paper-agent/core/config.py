"""
중앙 설정 — 튜닝 가능한 값만 한 곳에. 모두 env 로 덮어쓸 수 있다.

paper-agent 는 책 엔진과 달리:
  - 모델이 2개다. 생성(plan/write/revise)=MODEL, 검수=REVIEW_MODEL(다른 계열 권장).
    같은 모델로 검수하면 자기 실수를 못 잡는다(self-consistency bias) → Qwen 계열로 분리.
  - 단위가 '섹션'이고, 출력이 LaTeX 다.
"""
import os
from pathlib import Path

# ── 경로 ──────────────────────────────────────────────────────────────
PKG_ROOT = Path(__file__).resolve().parent.parent          # paper-agent/
REPO_ROOT = PKG_ROOT.parent                                # ai-books/
OUTPUT_ROOT = PKG_ROOT / "output"
INPUT_ROOT = PKG_ROOT / "inputs"

# ── .env 자동 로드(있으면) ─────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    for _envp in (PKG_ROOT / ".env", REPO_ROOT / "ADK_AGENT" / ".env"):
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


# ── 모델 (core/llm.py) ────────────────────────────────────────────────
# 생성용(설계·집필·수정). 한 계열로 통일해 문체 일관성 확보.
MODEL = os.getenv("PAPER_MODEL", "gemma4:31b")
# 검수용. ★ 생성과 다른 계열을 권장 — 교차 검수가 자기 실수를 더 잘 잡는다.
#   후보: qwen3-coder:30b(기본) / hf.co/Lazarus-Ai/ReAligned-Qwen3.5-27B-GGUF:Q4_K_S
REVIEW_MODEL = os.getenv("PAPER_REVIEW_MODEL", "qwen3-coder:30b")

LLM_TEMPERATURE = _float("PAPER_TEMPERATURE", 0.7)
LLM_NUM_CTX = _int("PAPER_NUM_CTX", 32768)
LLM_REPEAT_PENALTY = _float("PAPER_REPEAT_PENALTY", 1.2)
LLM_KEEP_ALIVE = os.getenv("PAPER_KEEP_ALIVE", "30m")

# 단계별 temperature (생성은 창의·수정은 보수·판단은 결정적)
T_PLAN = _float("PAPER_T_PLAN", 0.4)
T_WRITE = _float("PAPER_T_WRITE", 0.7)
T_REVISE = _float("PAPER_T_REVISE", 0.4)
T_REVIEW = _float("PAPER_T_REVIEW", 0.2)

# ── 품질 게이트 (review.py / orchestrator.py) ──────────────────────────
QUALITY_GATE = _int("PAPER_QUALITY_GATE", 80)             # 위반 0 + 이 점수 이상이면 통과
TARGET_SCORE = _int("PAPER_TARGET_SCORE", 88)             # 이 점수면 더 안 끌어올림
MIN_CHARS = _int("PAPER_MIN_CHARS", 600)                  # 섹션 본문 최소 길이(가드)

# ── 루프 상한 ─────────────────────────────────────────────────────────
WRITE_MAX = _int("PAPER_WRITE_MAX", 3)                    # 초안 재작성 상한 (write.py)
PASS_MAX = _int("PAPER_PASS_MAX", 3)                      # review→revise 재수정 상한

# ── grounding 소스 (core/grounding.py) ────────────────────────────────
MAX_FILE_CHARS = _int("PAPER_MAX_FILE_CHARS", 16000)      # 토큰 예산 보호용 절단 한도

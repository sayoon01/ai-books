from .base import Orchestrator, Result
from .code_orch import CodeOrchestrator
from .llm_orch import LlmOrchestrator
from .hybrid_orch import HybridOrchestrator

REGISTRY = {
    "code": CodeOrchestrator,
    "llm": LlmOrchestrator,
    "hybrid": HybridOrchestrator,
}

__all__ = ["Orchestrator", "Result", "REGISTRY",
           "CodeOrchestrator", "LlmOrchestrator", "HybridOrchestrator"]

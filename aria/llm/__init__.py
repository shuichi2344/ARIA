"""
LLM integration layer for ARIA.

Provider hierarchy:
1. Ilmu AI (primary) — Malaysian sovereign AI, OpenAI-compatible
2. Ollama (fallback) — Local inference when cloud is unavailable

Use LLMClient for automatic failover, or individual clients directly.
"""

from aria.llm.ollama_client import OllamaClient, OllamaError
from aria.llm.ilmu_client import IlmuClient, IlmuError
from aria.llm.llm_client import LLMClient, LLMClientError
from aria.llm import prompts

__all__ = [
    "LLMClient",
    "LLMClientError",
    "IlmuClient",
    "IlmuError",
    "OllamaClient",
    "OllamaError",
    "prompts",
]

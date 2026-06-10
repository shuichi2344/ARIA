"""
Unified LLM client with Ilmu AI as primary and Ollama as fallback.

Strategy:
1. Try Ilmu AI first (cloud, higher quality, Malaysian-optimised)
2. If Ilmu fails with a non-retryable error (billing, auth), mark it as
   permanently unavailable for this process lifetime and skip it on all
   subsequent calls — go straight to Ollama.
3. If Ilmu fails with a transient error (network, timeout), fall back to
   Ollama for that call only and retry Ilmu next time.
4. If both fail, raise the last error.
"""

import logging
from typing import Dict, Any, Optional, List

from aria.config import get_settings

logger = logging.getLogger(__name__)

# Non-retryable HTTP status codes — billing/auth issues won't fix themselves
_NON_RETRYABLE_STATUS_CODES = {401, 402, 403}


def _is_non_retryable(error: Exception) -> bool:
    """Return True if this error type means Ilmu will keep failing."""
    msg = str(error).lower()
    # IlmuError wraps the status code in the message string
    for code in _NON_RETRYABLE_STATUS_CODES:
        if f"({code})" in str(error) or f"error ({code})" in str(error):
            return True
    # Also catch obvious billing/auth keywords
    return any(kw in msg for kw in ("billing_error", "insufficient_quota", "unauthorized", "payment required"))


class LLMClientError(Exception):
    """Exception raised when all LLM providers fail."""
    pass


class LLMClient:
    """
    Unified LLM client that routes to Ilmu AI (primary) with Ollama fallback.

    Once Ilmu AI fails with a non-retryable error (e.g. 402 billing), it is
    marked permanently unavailable for the lifetime of this instance and all
    subsequent calls go directly to Ollama without retrying Ilmu.
    """

    def __init__(self):
        """Initialize with available providers based on configuration."""
        settings = get_settings()
        self._ilmu_client = None
        self._ollama_client = None
        self._ilmu_available = False
        self._ollama_available = False
        # Set to True after a non-retryable Ilmu failure — bypasses Ilmu forever
        self._ilmu_permanently_down = False

        # Try to initialize Ilmu AI client (primary)
        if settings.ilmu_api_key:
            try:
                from aria.llm.ilmu_client import IlmuClient
                self._ilmu_client = IlmuClient()
                self._ilmu_available = True
                logger.info(
                    f"Ilmu AI configured as primary LLM (model: {settings.ilmu_model})"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Ilmu AI client: {e}")

        # Initialize Ollama client (fallback)
        try:
            from aria.llm.ollama_client import OllamaClient
            self._ollama_client = OllamaClient()
            self._ollama_available = True
            logger.info(
                f"Ollama configured as fallback LLM (model: {settings.ollama_model})"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Ollama client: {e}")

        if not self._ilmu_available and not self._ollama_available:
            raise LLMClientError(
                "No LLM provider available. Configure ILMU_API_KEY for Ilmu AI "
                "or ensure Ollama is running locally."
            )

    @property
    def primary_provider(self) -> str:
        """Return the name of the active primary provider."""
        if self._ilmu_available and not self._ilmu_permanently_down:
            return "ilmu"
        return "ollama"

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system: Optional[str] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate text using the best available LLM provider.
        Tries Ilmu AI first (unless permanently marked down), then Ollama.
        """
        errors = []

        # Try Ilmu AI first — skip entirely if already marked permanently down
        if self._ilmu_available and self._ilmu_client and not self._ilmu_permanently_down:
            try:
                result = await self._ilmu_client.generate(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system=system,
                    stream=stream,
                )
                result["provider"] = "ilmu"
                return result
            except Exception as e:
                if _is_non_retryable(e):
                    logger.warning(
                        f"Ilmu AI returned a non-retryable error — switching permanently "
                        f"to Ollama for this session. Error: {e}"
                    )
                    self._ilmu_permanently_down = True
                else:
                    logger.warning(f"Ilmu AI failed (transient), falling back to Ollama: {e}")
                errors.append(("ilmu", e))

        # Fallback to Ollama
        if self._ollama_available and self._ollama_client:
            try:
                result = await self._ollama_client.generate(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system=system,
                    stream=stream,
                )
                result["provider"] = "ollama"
                return result
            except Exception as e:
                logger.error(f"Ollama fallback also failed: {e}")
                errors.append(("ollama", e))

        error_details = "; ".join(f"{name}: {err}" for name, err in errors)
        raise LLMClientError(f"All LLM providers failed. {error_details}")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Chat completion using the best available LLM provider.
        Tries Ilmu AI first (unless permanently marked down), then Ollama.
        """
        errors = []

        # Try Ilmu AI first — skip entirely if already marked permanently down
        if self._ilmu_available and self._ilmu_client and not self._ilmu_permanently_down:
            try:
                result = await self._ilmu_client.chat(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                result["provider"] = "ilmu"
                return result
            except Exception as e:
                if _is_non_retryable(e):
                    logger.warning(
                        f"Ilmu AI returned a non-retryable error — switching permanently "
                        f"to Ollama for this session. Error: {e}"
                    )
                    self._ilmu_permanently_down = True
                else:
                    logger.warning(f"Ilmu AI chat failed (transient), falling back to Ollama: {e}")
                errors.append(("ilmu", e))

        # Fallback to Ollama
        if self._ollama_available and self._ollama_client:
            try:
                result = await self._ollama_client.chat(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                result["provider"] = "ollama"
                return result
            except Exception as e:
                logger.error(f"Ollama chat fallback also failed: {e}")
                errors.append(("ollama", e))

        error_details = "; ".join(f"{name}: {err}" for name, err in errors)
        raise LLMClientError(f"All LLM providers failed for chat. {error_details}")

    async def health_check(self) -> Dict[str, bool]:
        """Check health of all configured providers."""
        status = {}
        if self._ilmu_client:
            status["ilmu"] = await self._ilmu_client.health_check()
        if self._ollama_client:
            status["ollama"] = await self._ollama_client.health_check()
        return status

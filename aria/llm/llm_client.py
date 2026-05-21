"""
Unified LLM client with Ilmu AI as primary and Ollama as fallback.

Strategy:
1. Try Ilmu AI first (cloud, higher quality, Malaysian-optimised)
2. If Ilmu fails (network, rate limit, auth), fall back to local Ollama
3. If both fail, raise the last error

This ensures the system works even when:
- Ilmu AI is down or rate-limited → falls back to local Ollama
- Ollama is not running → uses Ilmu AI cloud
- Both are available → prefers Ilmu AI for quality
"""

import logging
from typing import Dict, Any, Optional, List

from aria.config import get_settings

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Exception raised when all LLM providers fail."""
    pass


class LLMClient:
    """
    Unified LLM client that routes to Ilmu AI (primary) with Ollama fallback.
    
    Exposes the same interface as OllamaClient so it's a drop-in replacement.
    """

    def __init__(self):
        """Initialize with available providers based on configuration."""
        settings = get_settings()
        self._ilmu_client = None
        self._ollama_client = None
        self._ilmu_available = False
        self._ollama_available = False

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
        """Return the name of the primary provider."""
        if self._ilmu_available:
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
        Tries Ilmu AI first, falls back to Ollama.

        Args:
            prompt: Input prompt for the model
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            system: System prompt for context
            stream: Whether to stream the response

        Returns:
            Dictionary with:
                - response: Generated text
                - model: Model name used
                - provider: Which provider was used ("ilmu" or "ollama")
                - done: Whether generation is complete

        Raises:
            LLMClientError: If all providers fail
        """
        errors = []

        # Try Ilmu AI first (primary)
        if self._ilmu_available and self._ilmu_client:
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
                logger.warning(f"Ilmu AI failed, falling back to Ollama: {e}")
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

        # Both failed
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
        Tries Ilmu AI first, falls back to Ollama.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Dictionary with chat response and provider info

        Raises:
            LLMClientError: If all providers fail
        """
        errors = []

        # Try Ilmu AI first (primary)
        if self._ilmu_available and self._ilmu_client:
            try:
                result = await self._ilmu_client.chat(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                result["provider"] = "ilmu"
                return result
            except Exception as e:
                logger.warning(f"Ilmu AI chat failed, falling back to Ollama: {e}")
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
        """
        Check health of all configured providers.

        Returns:
            Dictionary with provider health status
        """
        status = {}

        if self._ilmu_client:
            status["ilmu"] = await self._ilmu_client.health_check()

        if self._ollama_client:
            status["ollama"] = await self._ollama_client.health_check()

        return status

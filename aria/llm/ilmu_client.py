"""
Ilmu AI client for LLM inference.
Uses the OpenAI-compatible API at https://api.ilmu.ai/v1.
Malaysian sovereign AI platform with data residency in Malaysia.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError
from aria.config import get_settings

logger = logging.getLogger(__name__)


class IlmuError(Exception):
    """Exception raised for Ilmu AI client errors."""
    pass


class IlmuClient:
    """Client for interacting with Ilmu AI API (OpenAI-compatible)."""

    DEFAULT_BASE_URL = "https://api.ilmu.ai/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 120.0,
    ):
        """
        Initialize Ilmu AI client.

        Args:
            api_key: Ilmu API key (if None, loads from settings)
            base_url: Ilmu API base URL (if None, uses default)
            model: Model name (if None, loads from settings)
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            timeout: Request timeout in seconds
        """
        settings = get_settings()
        self.api_key = api_key or settings.ilmu_api_key
        self.base_url = base_url or settings.ilmu_base_url or self.DEFAULT_BASE_URL
        self.model = model or settings.ilmu_model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

        if not self.api_key:
            raise IlmuError(
                "Ilmu API key not configured. "
                "Set ILMU_API_KEY in your .env file. "
                "Get your key at https://console.ilmu.ai/dashboard/keys"
            )

        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=0,  # We handle retries ourselves for fallback logic
        )

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system: Optional[str] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate text using Ilmu AI model.
        Matches the OllamaClient.generate() interface for drop-in compatibility.

        Args:
            prompt: Input prompt for the model
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            system: System prompt for context
            stream: Whether to stream (not yet supported, ignored)

        Returns:
            Dictionary with:
                - response: Generated text
                - model: Model name used
                - done: Whether generation is complete

        Raises:
            IlmuError: If generation fails after all retries
        """
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return await self._chat_with_retry(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Chat completion using Ilmu AI model.
        Matches the OllamaClient.chat() interface for drop-in compatibility.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Dictionary with:
                - response: Generated text
                - message: Message dict (for compatibility)
                - model: Model name used
                - done: Whether generation is complete

        Raises:
            IlmuError: If chat fails after all retries
        """
        return await self._chat_with_retry(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def _chat_with_retry(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> Dict[str, Any]:
        """Internal method with retry logic. Non-retryable errors (4xx billing/auth) fail immediately."""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return await self._do_chat(messages, temperature, max_tokens)
            except IlmuError as e:
                last_error = e
                # Don't retry billing/auth errors — they won't resolve on their own
                error_str = str(e)
                is_permanent = any(
                    code in error_str for code in ("(401)", "(402)", "(403)", "billing_error", "insufficient_quota")
                )
                if is_permanent:
                    logger.warning(f"Ilmu AI non-retryable error, aborting retries: {e}")
                    raise e
                if attempt < self.max_retries - 1:
                    wait = self.retry_delay * (attempt + 1)
                    logger.warning(
                        f"Ilmu AI attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {wait}s..."
                    )
                    await asyncio.sleep(wait)

        raise last_error

    async def _do_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> Dict[str, Any]:
        """Single chat completion attempt."""
        try:
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens

            completion = await self._client.chat.completions.create(**kwargs)

            content = completion.choices[0].message.content or ""
            return {
                "response": content,
                "message": {"role": "assistant", "content": content},
                "model": completion.model,
                "done": True,
                "done_reason": completion.choices[0].finish_reason or "stop",
                "usage": {
                    "prompt_tokens": completion.usage.prompt_tokens if completion.usage else 0,
                    "completion_tokens": completion.usage.completion_tokens if completion.usage else 0,
                    "total_tokens": completion.usage.total_tokens if completion.usage else 0,
                },
            }

        except APIConnectionError as e:
            raise IlmuError(f"Cannot connect to Ilmu AI API: {e}")
        except RateLimitError as e:
            raise IlmuError(f"Ilmu AI rate limit exceeded: {e}")
        except APIError as e:
            raise IlmuError(f"Ilmu AI API error ({e.status_code}): {e.message}")
        except Exception as e:
            if isinstance(e, IlmuError):
                raise
            raise IlmuError(f"Unexpected error calling Ilmu AI: {e}")

    async def health_check(self) -> bool:
        """
        Check if Ilmu AI API is accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            models = await self._client.models.list()
            return any(m.id == self.model for m in models.data)
        except Exception:
            return False

    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List all available models on Ilmu AI.

        Returns:
            List of model information dictionaries

        Raises:
            IlmuError: If listing fails
        """
        try:
            models = await self._client.models.list()
            return [
                {
                    "id": m.id,
                    "owned_by": m.owned_by,
                    "created": m.created,
                }
                for m in models.data
            ]
        except Exception as e:
            raise IlmuError(f"Failed to list Ilmu AI models: {e}")

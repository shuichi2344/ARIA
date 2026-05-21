"""
Ollama client for LLM inference.
Handles communication with local Ollama server for Gemma 2 model.
"""

import aiohttp
import asyncio
from typing import Dict, Any, Optional
from aria.config import get_settings


class OllamaError(Exception):
    """Exception raised for Ollama client errors."""
    pass


class OllamaClient:
    """Client for interacting with Ollama API for LLM inference."""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize Ollama client.
        
        Args:
            base_url: Ollama server URL (if None, loads from settings)
            model: Model name (if None, loads from settings)
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        settings = get_settings()
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = aiohttp.ClientTimeout(total=180)  # 3 minutes for reasoning models
    
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system: Optional[str] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Generate text using Ollama model.
        
        Args:
            prompt: Input prompt for the model
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate (None for model default)
            system: System prompt for context
            stream: Whether to stream the response
        
        Returns:
            Dictionary with:
                - response: Generated text
                - model: Model name used
                - done: Whether generation is complete
                - context: Context for follow-up requests
        
        Raises:
            OllamaError: If generation fails
        """
        for attempt in range(self.max_retries):
            try:
                return await self._generate_with_retry(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system=system,
                    stream=stream
                )
            except OllamaError as e:
                if attempt == self.max_retries - 1:
                    raise
                
                # Wait before retrying
                await asyncio.sleep(self.retry_delay * (attempt + 1))
                print(f"Retry attempt {attempt + 1}/{self.max_retries} after error: {e}")
    
    async def _generate_with_retry(
        self,
        prompt: str,
        temperature: float,
        max_tokens: Optional[int],
        system: Optional[str],
        stream: bool
    ) -> Dict[str, Any]:
        """
        Internal method to generate text with a single attempt.
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            system: System prompt
            stream: Stream response
        
        Returns:
            Generation result dictionary
        
        Raises:
            OllamaError: If generation fails
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": stream,
                    "options": {
                        "temperature": temperature
                    }
                }
                
                if max_tokens is not None:
                    payload["options"]["num_predict"] = max_tokens
                
                if system is not None:
                    payload["system"] = system
                
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Some models put thinking in a separate field.
                        # The actual answer is in "response".
                        actual_response = data.get("response", "")
                        return {
                            "response": actual_response,
                            "model": data.get("model", self.model),
                            "done": data.get("done", True),
                            "done_reason": data.get("done_reason", ""),
                            "context": data.get("context", [])
                        }
                    elif response.status == 404:
                        raise OllamaError(f"Model '{self.model}' not found. Please run: ollama pull {self.model}")
                    else:
                        error_text = await response.text()
                        raise OllamaError(f"Ollama API error {response.status}: {error_text}")
        
        except aiohttp.ClientConnectorError:
            raise OllamaError(
                "Cannot connect to Ollama server. "
                "Please ensure Ollama is running with: ollama serve"
            )
        except asyncio.TimeoutError:
            raise OllamaError("Ollama request timed out. The model might be overloaded.")
        except Exception as e:
            if isinstance(e, OllamaError):
                raise
            raise OllamaError(f"Unexpected error: {str(e)}")
    
    async def chat(
        self,
        messages: list[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Chat completion using Ollama model.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        
        Returns:
            Dictionary with chat response
        
        Raises:
            OllamaError: If chat fails
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature
                    }
                }
                
                if max_tokens is not None:
                    payload["options"]["num_predict"] = max_tokens
                
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "message": data.get("message", {}),
                            "model": data.get("model", self.model),
                            "done": data.get("done", True)
                        }
                    else:
                        error_text = await response.text()
                        raise OllamaError(f"Ollama chat error {response.status}: {error_text}")
        
        except aiohttp.ClientConnectorError:
            raise OllamaError("Cannot connect to Ollama server")
        except asyncio.TimeoutError:
            raise OllamaError("Ollama chat request timed out")
        except Exception as e:
            if isinstance(e, OllamaError):
                raise
            raise OllamaError(f"Unexpected error: {str(e)}")
    
    async def health_check(self) -> bool:
        """
        Check if Ollama server is accessible and model is available.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                # Check if server is running
                async with session.get(f"{self.base_url}/api/tags") as response:
                    if response.status != 200:
                        return False
                    
                    data = await response.json()
                    models = data.get("models", [])
                    
                    # Check if our model is available
                    model_found = any(
                        model.get("name", "").startswith(self.model.split(":")[0])
                        for model in models
                    )
                    
                    return model_found
        
        except Exception:
            return False
    
    async def list_models(self) -> list[Dict[str, Any]]:
        """
        List all available models in Ollama.
        
        Returns:
            List of model information dictionaries
        
        Raises:
            OllamaError: If listing fails
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("models", [])
                    else:
                        raise OllamaError(f"Failed to list models: {response.status}")
        
        except aiohttp.ClientConnectorError:
            raise OllamaError("Cannot connect to Ollama server")
        except Exception as e:
            if isinstance(e, OllamaError):
                raise
            raise OllamaError(f"Unexpected error: {str(e)}")
    
    async def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model.
        
        Returns:
            Dictionary with model information
        
        Raises:
            OllamaError: If request fails
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                payload = {"name": self.model}
                
                async with session.post(
                    f"{self.base_url}/api/show",
                    json=payload
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        raise OllamaError(f"Failed to get model info: {response.status}")
        
        except aiohttp.ClientConnectorError:
            raise OllamaError("Cannot connect to Ollama server")
        except Exception as e:
            if isinstance(e, OllamaError):
                raise
            raise OllamaError(f"Unexpected error: {str(e)}")

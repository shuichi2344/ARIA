"""
Ollama verification script for ARIA.
Checks if Ollama is running and if Gemma 2 model is available.
"""

import sys
import os
import asyncio
import aiohttp

# Add parent directory to path so we can import aria modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from aria.config import get_settings
except ImportError:
    # Fallback if config module not available yet
    from dotenv import load_dotenv
    load_dotenv()
    
    class MockSettings:
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL", "gemma2:2b")
    
    def get_settings():
        return MockSettings()
    
    print("⚠️  Note: Using environment variables directly (aria.config not fully initialized)")
    print()


async def check_ollama():
    """Check Ollama installation and model availability."""
    settings = get_settings()
    base_url = settings.ollama_base_url
    model_name = settings.ollama_model
    
    print("="*60)
    print("ARIA - Ollama Verification")
    print("="*60)
    print(f"\nOllama URL: {base_url}")
    print(f"Model: {model_name}")
    
    # Check if Ollama is running
    print("\n1. Checking if Ollama is running...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    print("   ✓ Ollama is running!")
                    data = await response.json()
                    models = data.get("models", [])
                    
                    # Check if Gemma 2 model is available
                    print(f"\n2. Checking for {model_name} model...")
                    model_found = any(model.get("name", "").startswith(model_name.split(":")[0]) for model in models)
                    
                    if model_found:
                        print(f"   ✓ {model_name} model is available!")
                    else:
                        print(f"   ✗ {model_name} model not found!")
                        print(f"\n   Available models:")
                        for model in models:
                            print(f"     - {model.get('name', 'unknown')}")
                        
                        print(f"\n   To install {model_name}, run:")
                        print(f"   ollama pull {model_name}")
                        return False
                    
                    # Test basic inference
                    print("\n3. Testing basic LLM inference...")
                    test_prompt = "Say 'Hello from ARIA!' in one sentence."
                    
                    async with session.post(
                        f"{base_url}/api/generate",
                        json={
                            "model": model_name,
                            "prompt": test_prompt,
                            "stream": False
                        },
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as gen_response:
                        if gen_response.status == 200:
                            result = await gen_response.json()
                            response_text = result.get("response", "")
                            print(f"   ✓ Inference successful!")
                            print(f"   Response: {response_text[:100]}...")
                        else:
                            print(f"   ✗ Inference failed with status {gen_response.status}")
                            return False
                    
                    print("\n" + "="*60)
                    print("✓ All checks passed! Ollama is ready for ARIA.")
                    print("="*60)
                    return True
                else:
                    print(f"   ✗ Ollama returned status {response.status}")
                    return False
                    
    except aiohttp.ClientConnectorError:
        print("   ✗ Cannot connect to Ollama!")
        print("\n   Ollama is not running. Please start it with:")
        print("   ollama serve")
        print("\n   If Ollama is not installed, download it from:")
        print("   https://ollama.ai/download")
        return False
    except asyncio.TimeoutError:
        print("   ✗ Connection timeout!")
        print("   Ollama might be starting up. Please wait and try again.")
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def main():
    """Main entry point."""
    try:
        result = asyncio.run(check_ollama())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(1)


if __name__ == "__main__":
    main()

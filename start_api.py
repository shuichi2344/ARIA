"""
Startup script for ARIA FastAPI backend server.

Usage:
    python start_api.py
"""

import uvicorn
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging BEFORE starting uvicorn
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('aria_api.log', mode='a')
    ],
    force=True
)

# Set specific loggers
logging.getLogger('aria.agents.scenario_suggestion').setLevel(logging.INFO)
logging.getLogger('aria.external.news_api').setLevel(logging.INFO)
logging.getLogger('aria.external.dosm').setLevel(logging.INFO)

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 Starting ARIA API Server")
    print("=" * 70)
    print()
    print("📍 API will be available at: http://localhost:8000")
    print("📖 API docs will be available at: http://localhost:8000/docs")
    print("🔍 Health check: http://localhost:8000/api/health")
    print()
    print("💡 Make sure:")
    print("   - Ollama is running (for AI analysis)")
    print("   - Database is configured in .env file")
    print("   - Web UI is running on http://localhost:8080")
    print()
    print("📝 Logs are being written to: aria_api.log")
    print("   Run 'Get-Content aria_api.log -Wait' in another terminal to watch logs")
    print()
    print("Press CTRL+C to stop the server")
    print("=" * 70)
    print()
    
    # Force stdout to be unbuffered
    sys.stdout.reconfigure(line_buffering=True)
    
    uvicorn.run(
        "aria.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info",
        use_colors=True
    )

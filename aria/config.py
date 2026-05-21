"""
Configuration management for ARIA platform.
Loads and validates environment variables using Pydantic Settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, HttpUrl
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Supabase Configuration
    supabase_url: HttpUrl = Field(..., description="Supabase project URL")
    supabase_key: str = Field(..., description="Supabase anon/service key")
    supabase_db_password: str = Field(..., description="Supabase database password")
    
    # DOSM API Configuration (optional)
    dosm_api_key: Optional[str] = Field(None, description="DOSM API key (optional)")
    
    # News API Configuration (optional)
    news_api_key: Optional[str] = Field(None, description="NewsAPI.org API key (optional)")
    news_api_enabled: bool = Field(default=False, description="Enable News API integration")
    news_cache_hours: int = Field(default=6, description="Cache news for N hours")
    
    # Ilmu AI Configuration (Primary LLM)
    ilmu_api_key: Optional[str] = Field(
        default=None,
        description="Ilmu AI API key (get from https://console.ilmu.ai/dashboard/keys)"
    )
    ilmu_base_url: str = Field(
        default="https://api.ilmu.ai/v1",
        description="Ilmu AI API base URL"
    )
    ilmu_model: str = Field(
        default="ilmu-nemo-nano",
        description="Ilmu AI model to use (nemo-super or ilmu-nemo-nano)"
    )
    
    # Ollama Configuration (Fallback LLM)
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server base URL (fallback when Ilmu AI is unavailable)"
    )
    ollama_model: str = Field(
        default="qwen2.5:7b",
        description="Ollama model to use as fallback"
    )
    
    # Application Configuration
    environment: str = Field(default="development", description="Environment (development/production)")
    debug: bool = Field(default=True, description="Debug mode")
    app_url: str = Field(default="http://localhost:3000", description="Frontend app URL for email links")
    
    # SMTP Configuration (for password reset emails)
    smtp_host: Optional[str] = Field(default=None, description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_user: Optional[str] = Field(default=None, description="SMTP username/email")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password")
    smtp_from_email: Optional[str] = Field(default=None, description="From email address (defaults to smtp_user)")
    
    # Resource Limits
    max_vram_gb: float = Field(default=6.0, description="Maximum VRAM usage in GB")
    vram_warning_threshold: float = Field(default=0.90, description="VRAM warning threshold (0-1)")
    
    # Simulation Defaults
    min_simulation_weeks: int = Field(default=1, description="Minimum simulation duration in weeks")
    max_simulation_weeks: int = Field(default=52, description="Maximum simulation duration in weeks")
    min_agent_count: int = Field(default=15, description="Minimum number of agents")
    max_agent_count: int = Field(default=20, description="Maximum number of agents")


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings


# Export commonly used settings as module-level variables
NEWS_API_KEY = settings.news_api_key
NEWS_API_ENABLED = settings.news_api_enabled
ILMU_API_KEY = settings.ilmu_api_key
ILMU_BASE_URL = settings.ilmu_base_url
ILMU_MODEL = settings.ilmu_model
OLLAMA_BASE_URL = settings.ollama_base_url
OLLAMA_MODEL = settings.ollama_model

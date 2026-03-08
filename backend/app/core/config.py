"""
Core configuration for FastAPI application.
Settings are loaded from environment variables.
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # API Keys
    openrouter_api_key: str = Field(..., alias="OPENROUTER_API_KEY")
    openweathermap_api_key: Optional[str] = Field(None, alias="OPENWEATHERMAP_API_KEY")
    google_places_api_key: Optional[str] = Field(None, alias="GOOGLE_PLACES_API_KEY")
    google_calendar_client_id: Optional[str] = Field(None, alias="GOOGLE_CALENDAR_CLIENT_ID")
    google_calendar_client_secret: Optional[str] = Field(None, alias="GOOGLE_CALENDAR_CLIENT_SECRET")
    
    # Database
    database_url: str = Field(..., alias="DATABASE_URL")
    
    # Security
    secret_key: str = Field(..., alias="SECRET_KEY")
    algorithm: str = Field("HS256", alias="ALGORITHM")
    access_token_expire_days: int = Field(30, alias="ACCESS_TOKEN_EXPIRE_DAYS")
    
    # OpenRouter config
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_models: dict = {
        "orchestrator": "anthropic/claude-3-haiku",
        "fast": "mistralai/mixtral-8x7b-instruct",
        "creative": "anthropic/claude-3-haiku"
    }
    
    # API limits
    max_agents_per_query: int = 5
    request_timeout_seconds: int = 30
    
    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
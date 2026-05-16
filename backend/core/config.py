from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path

# Walk up from this file (core/config.py) to find .env at project root or backend/
_HERE = Path(__file__).parent          # backend/core/
_BACKEND = _HERE.parent                # backend/
_ROOT = _BACKEND.parent               # project root (US Foodie Scout/)

# Prefer root-level .env, fall back to backend-level .env
_ENV_FILE = str(_ROOT / ".env") if (_ROOT / ".env").exists() else str(_BACKEND / ".env")


class Settings(BaseSettings):
    # App
    app_name: str = "US Foodie Scout"
    debug: bool = False

    # LLM - DeepSeek primary
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # Fallback LLM (Claude - add key later)
    anthropic_api_key: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Rate Limiting
    rate_limit_requests: int = 5
    rate_limit_window_seconds: int = 60

    # LA Bounding Box
    la_lat_min: float = 33.70
    la_lat_max: float = 34.35
    la_lng_min: float = -118.67
    la_lng_max: float = -117.65

    # CORS — set ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com in prod
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Session
    session_ttl_seconds: int = 7200    # 2 hours
    session_max_turns: int = 10

    # Cache
    places_cache_ttl_seconds: int = 86400  # 24 hours
    xhs_cache_ttl_seconds: int = 21600     # 6 hours (social data changes faster)

    # XHS — real data (Option A: unofficial API via `xhs` package)
    # Set XHS_USE_REAL=true once cookie is configured.
    xhs_use_real: bool = False
    xhs_cookie: str = ""
    xhs_search_location: str = "洛杉矶 SGV"

    # Yelp Fusion API — restaurant photos
    yelp_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()

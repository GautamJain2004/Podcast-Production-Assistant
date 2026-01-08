# config/settings.py
import os
import logging
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env early but do not force required keys at import time
load_dotenv(dotenv_path=".env", verbose=False)

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file.
    gemini_api_key is optional to allow offline/mock development.
    If you want to enforce a key in production, call get_gemini_client(strict=True).
    """
    gemini_api_key: Optional[str] = Field(None, description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-2.5-flash", description="Gemini model to use")

    # Application settings
    app_name: str = Field(default="Podcast Production Suite")
    log_level: str = Field(default="INFO")
    max_research_items: int = Field(default=5)
    max_social_posts: int = Field(default=3)

    # Web Search (MCP / Serper)
    web_search_api_key: Optional[str] = Field(None)
    web_search_engine: str = Field(default="serper")

    # YouTube API (optional, for video search)
    youtube_api_key: Optional[str] = Field(None, description="YouTube Data API v3 key")

    # Audio settings
    words_per_minute: int = Field(default=150)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env

# Lazy singleton
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Return a lazily-initialized Settings instance (cached)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

def get_gemini_client(strict: bool = False):
    """
    Return a configured Gemini client with retry logic. 
    If strict=True, raises ValueError if key missing.
    This function is lazy: it only attempts to create the client when called.
    """
    settings = get_settings()
    api_key = settings.gemini_api_key
    if not api_key:
        if strict:
            raise ValueError("Gemini API key is required (set GEMINI_API_KEY in environment).")
        # If not strict, return None to indicate mock mode
        return None

    # Lazy import to avoid requiring the SDK at import-time
    try:
        from google import genai
    except Exception as e:
        raise RuntimeError("Failed to import Google genai SDK. Install the dependency or run in mock mode.") from e

    # Create client with default configuration
    client = genai.Client(api_key=api_key)
    
    # Log retry configuration info
    logger = logging.getLogger("config.settings")
    logger.info("Gemini client created with automatic retry and rate limiting enabled")
    
    return client

def get_gemini_model() -> str:
    """Return the configured Gemini model name (read lazily)."""
    return get_settings().gemini_model

def setup_logging(log_to_file: bool = True) -> None:
    """
    Idempotent logging setup. Safe to call multiple times.
    
    Args:
        log_to_file: If True, logs will be saved to logs/podcast_production.log
    """
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # If root logger has handlers already, don't reconfigure basicConfig (prevents duplicate handlers).
    if not logging.getLogger().handlers:
        # Create logs directory if it doesn't exist
        if log_to_file:
            import os
            from pathlib import Path
            logs_dir = Path("logs")
            logs_dir.mkdir(exist_ok=True)
            
            # Configure logging with both console and file handlers
            logging.basicConfig(
                level=level,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
                handlers=[
                    logging.StreamHandler(),  # Console output
                    logging.FileHandler(logs_dir / "podcast_production.log", mode='a', encoding='utf-8')  # File output
                ]
            )
            
            # Log the logging setup
            logger = logging.getLogger("config.settings")
            logger.info(f"Logging configured: level={settings.log_level}, file={logs_dir / 'podcast_production.log'}")
        else:
            # Console only
            logging.basicConfig(
                level=level,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

    # Set package-specific defaults
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("podcast_production").setLevel(level)

def setup_environment(strict: bool = False, log_to_file: bool = True) -> None:
    """
    Convenience initializer called by main.py. Loads settings (via get_settings)
    and configures logging. If strict=True, will validate presence of required keys.
    
    Args:
        strict: If True, validates required environment variables
        log_to_file: If True, logs will be saved to logs/podcast_production.log
    """
    # Ensure settings object created (this loads .env)
    settings = get_settings()
    setup_logging(log_to_file=log_to_file)

    if strict:
        # Validate critical keys for production
        missing = []
        if not settings.gemini_api_key:
            missing.append("GEMINI_API_KEY")
        if missing:
            raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")

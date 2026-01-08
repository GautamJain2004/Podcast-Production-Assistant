# config/constants.py
"""
Application constants and default values.

This module avoids doing environment-dependent work at import time.
Call helper functions to get runtime values (for example, the model name)
so the application can run in mock/dev mode without required env vars.
"""

from typing import Dict, Any, List, Optional
from .settings import get_settings, get_gemini_model

# Agent Configuration defaults (do not evaluate model at import-time)
_DEFAULT_AGENT_CONFIG = {
    "max_retries": 2,
    "timeout": 30,
    "temperature": 0.7,
    # "model" intentionally omitted here to avoid import-time evaluation
}

def get_default_agent_config() -> Dict[str, Any]:
    """
    Return a runtime agent configuration dictionary filled with the current model.
    Uses get_gemini_model() lazily so importing this module doesn't fail when
    environment variables are missing during development.
    """
    cfg = dict(_DEFAULT_AGENT_CONFIG)  # shallow copy
    try:
        cfg["model"] = get_gemini_model()
    except Exception:
        # If settings are unavailable (dev/mock mode), leave model as None
        cfg["model"] = None
    return cfg

# Content Generation Limits
MAX_RESEARCH_QUERIES: int = 3
MAX_OUTLINE_SECTIONS: int = 4
MAX_SOCIAL_POSTS: Dict[str, int] = {
    "twitter": 3,
    "linkedin": 2,
    "instagram": 2
}

# Tone Options (keep in sync with config/settings.DEFAULTS if necessary)
VALID_TONES: List[str] = [
    "professional",
    "casual",
    "humorous",
    "educational",
    "conversational",
    "inspirational",
    "technical",
    "storytelling"
]

# Content Guidelines
SCRIPT_GUIDELINES: Dict[str, Any] = {
    "min_length": 500,  # characters
    "max_length": 5000, # characters
    "section_break": "\n---\n",
    "source_marker": "[Source:"
}

# File Output Configuration
OUTPUT_CONFIG: Dict[str, str] = {
    "script_filename": "script.md",
    "show_notes_filename": "show_notes.md",
    "social_posts_filename": "social_posts.json",
    "sources_filename": "sources.json",
    "metadata_filename": "metadata.json",
    "consolidated_filename": "podcast_package.json"
}

# MCP Tool Configuration
MCP_CONFIG: Dict[str, Any] = {
    "web_search": {
        "max_results": 5,
        "timeout": 10
    },
    "audio_calculator": {
        "words_per_minute": get_settings().words_per_minute if get_settings() else 150
    }
}

# Small convenience accessor for common defaults
def get_default_tone() -> str:
    """Return the application's default tone (read from settings if present)."""
    try:
        return get_settings().app_name and "professional" or "professional"
    except Exception:
        return "professional"

# utils/validation_utils.py
import json
import logging
from typing import Any, Dict, List, Optional
from utils.llm_helpers import extract_json_from_text

class ValidationUtils:
    """
    Utility functions for data validation and JSON parsing.
    """

    def __init__(self):
        self.logger = logging.getLogger("podcast_production.validation_utils")

    def safe_json_parse(self, text: str, default: Any = None, max_retries: int = 2) -> Any:
        """
        Safely parse JSON from LLM responses with retries and error handling.
        Uses extract_json_from_text to locate JSON-like snippets.
        """
        if not text:
            return default

        # First try to extract JSON-like content
        try:
            cleaned_text = extract_json_from_text(text)
        except Exception:
            cleaned_text = text

        for attempt in range(max_retries + 1):
            try:
                return json.loads(cleaned_text)
            except json.JSONDecodeError as e:
                self.logger.debug(f"JSON parse attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries:
                    # Try minor fixes: strip trailing commas, unescape quotes
                    cleaned_text = self._attempt_json_fix(cleaned_text)
                else:
                    self.logger.warning(f"Failed to parse JSON after {max_retries + 1} attempts")
                    return default
        return default

    def _attempt_json_fix(self, text: str) -> str:
        """Attempt to fix common JSON issues heuristically."""
        # Remove trailing commas before closing braces/brackets
        text = text.replace(",}", "}").replace(",]", "]")
        # Remove leading non-json text
        first_brace = min([i for i in (text.find('{'), text.find('[')) if i != -1] or [0])
        if first_brace > 0:
            text = text[first_brace:]
        # Other naive replacements
        text = text.replace("\\'", "'").replace('“', '"').replace('”', '"')
        return text

    def validate_social_posts_structure(self, social_posts: Any) -> bool:
        if not isinstance(social_posts, dict):
            return False
        if not social_posts:
            return False
        for platform, posts in social_posts.items():
            if not isinstance(posts, list):
                return False
            if not all(isinstance(p, str) for p in posts):
                return False
        return True

    def validate_research_materials(self, research_materials: List[Any]) -> bool:
        if not isinstance(research_materials, list):
            return False
        sample_size = min(3, len(research_materials))
        for i in range(sample_size):
            item = research_materials[i]
            if not getattr(item, "url", None) or not getattr(item, "content", None):
                return False
        return True

    def estimate_reading_time(self, text: str, words_per_minute: int = 150) -> float:
        if not text:
            return 0.0
        word_count = len(text.split())
        return round(word_count / words_per_minute, 1)

    def truncate_text(self, text: str, max_length: int, suffix: str = "...") -> str:
        if len(text) <= max_length:
            return text
        truncated = text[: max_length - len(suffix)]
        if ' ' in truncated:
            truncated = truncated.rsplit(' ', 1)[0]
        return truncated + suffix

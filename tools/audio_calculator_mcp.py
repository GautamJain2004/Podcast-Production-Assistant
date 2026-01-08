"""
AudioDurationTool: calculate estimated audio duration from script text.

Provides:
  - async execute(script_text: str, words_per_minute: Optional[int]) -> dict
  - sync wrapper calculate_duration(script_text, wpm) -> float
"""

import re
import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("tools.audio_calculator_mcp")
logger.addHandler(logging.NullHandler())


class AudioDurationTool:
    def __init__(self, default_wpm: int = 150):
        self.default_wpm = default_wpm

    async def execute(self, script_text: str, words_per_minute: Optional[int] = None) -> Dict[str, Any]:
        """
        Async entrypoint. Runs count in threadpool for safety (if heavy cleaning needed).
        Returns a dict with word_count, duration_minutes, formatted strings.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._calculate_sync, script_text, words_per_minute)

    def _clean_text(self, text: str) -> str:
        # Remove markdown, code fences, source markers
        clean = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        clean = re.sub(r'[#*_`~>\-]{1,}', ' ', clean)
        clean = re.sub(r'\[Source:[^\]]*\]', '', clean)
        clean = re.sub(r'\s+', ' ', clean)
        return clean.strip()

    def _format_duration(self, minutes: float) -> str:
        if minutes < 1:
            return f"{int(minutes * 60)} sec"
        elif minutes < 60:
            mins = int(minutes)
            secs = int((minutes - mins) * 60)
            return f"{mins} min {secs} sec"
        else:
            h = int(minutes // 60)
            m = int(minutes % 60)
            return f"{h}h {m}m"

    def _calculate_sync(self, script_text: str, words_per_minute: Optional[int] = None) -> Dict[str, Any]:
        wpm = words_per_minute or self.default_wpm
        try:
            clean = self._clean_text(script_text or "")
            words = clean.split()
            word_count = len(words)
            minutes = word_count / wpm if wpm > 0 else 0.0
            result = {
                "word_count": word_count,
                "words_per_minute": wpm,
                "duration_minutes": round(minutes, 1),
                "duration_formatted": self._format_duration(minutes),
                "estimated_range": f"{round(minutes*0.9,1)}-{round(minutes*1.1,1)} min"
            }
            return result
        except Exception as e:
            logger.exception(f"Audio duration calculation failed: {e}")
            return {
                "word_count": 0,
                "words_per_minute": wpm,
                "duration_minutes": 0.0,
                "duration_formatted": "0 min",
                "estimated_range": "0-0 min",
                "error": str(e)
            }

    # Sync convenience
    def calculate_duration(self, script_text: str, words_per_minute: Optional[int] = None) -> float:
        result = self._calculate_sync(script_text, words_per_minute)
        return result.get("duration_minutes", 0.0)

# utils/llm_helpers.py
import re
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

def extract_json_from_text(text: str) -> str:
    """
    Attempts to extract a JSON object or array from an LLM response string.
    Handles fenced code blocks (```json ... ```), plain JSON, and JSON embedded in text.
    If no JSON structure is found, returns the original text trimmed.
    """
    if not text:
        raise ValueError("Empty response text")

    # Prefer explicit ```json fenced blocks
    if "```json" in text:
        try:
            return text.split("```json", 1)[1].split("```", 1)[0].strip()
        except Exception:
            pass

    # Next prefer any fenced block (``` ... ```)
    if "```" in text:
        try:
            between = text.split("```", 1)[1]
            if "```" in between:
                candidate = between.split("```", 1)[0].strip()
                # If it looks like JSON, return it
                if candidate.startswith("{") or candidate.startswith("["):
                    return candidate
        except Exception:
            pass

    # Try to find the first balanced {...} or [...] block using simple heuristics.
    obj_match = None
    # Find first { ... } block
    brace_match = re.search(r"\{(?:[^{}]|\{[^}]*\})*\}", text, re.DOTALL)
    if brace_match:
        obj_match = brace_match.group(0)
        return obj_match.strip()
    # Find first [ ... ] block
    array_match = re.search(r"\[(?:[^\[\]]|\[[^\]]*\])*\]", text, re.DOTALL)
    if array_match:
        obj_match = array_match.group(0)
        return obj_match.strip()

    # Nothing JSON-like found — return trimmed text
    return text.strip()


def parse_llm_json_response(resp: Any) -> Any:
    """
    Normalize an LLM response into a Python object when possible.
    Accepts:
      - a string (raw text)
      - an object with .text attribute
      - a dict-like response
    Returns:
      - Python object parsed from JSON if possible
      - otherwise returns the cleaned string
    """
    text: Optional[str] = None

    # Handle raw string
    if isinstance(resp, str):
        text = resp
    else:
        # Common SDK shapes: resp.text
        text = getattr(resp, "text", None)

        # Some clients return candidates or choices
        if text is None:
            # try `candidates` list or `choices`
            try:
                cand = getattr(resp, "candidates", None) or getattr(resp, "choices", None)
                if cand:
                    first = cand[0]
                    # candidate may be dict-like or object
                    if isinstance(first, dict):
                        text = first.get("content") or first.get("text") or first.get("message") or None
                    else:
                        text = getattr(first, "content", None) or getattr(first, "text", None)
            except Exception:
                text = None

        # If still None and resp is dict-like
        if text is None and isinstance(resp, dict):
            text = resp.get("text") or resp.get("content") or resp.get("message") or None

    if not text:
        raise ValueError("Could not extract text from LLM response object")

    # Extract potential JSON snippet
    extracted = extract_json_from_text(text)

    # Attempt JSON parse
    try:
        return json.loads(extracted)
    except Exception:
        # Fallback: return the cleaned/extracted text (may be non-JSON)
        logger.debug("parse_llm_json_response: json.loads failed on extracted content", exc_info=True)
        return extracted

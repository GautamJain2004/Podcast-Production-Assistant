# utils/pydantic_compat.py
from typing import Any, Dict

def model_to_dict(model: Any) -> Dict:
    """
    Convert a Pydantic model to a plain dictionary in a version-agnostic way.
    Works with Pydantic v2 (.model_dump()) and v1 (.dict()) and fallback to __dict__.
    """
    if model is None:
        return {}
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    # Final fallback: shallow copy of __dict__ if present
    try:
        return dict(getattr(model, "__dict__", {}))
    except Exception:
        return {}

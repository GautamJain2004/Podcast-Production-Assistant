"""
Message serialization helpers for A2A protocol.
Converts PodcastProductionState <-> pure dict (JSON safe).
"""

from typing import Dict, Any
from schemas.state_models import PodcastProductionState


def state_to_message(state: PodcastProductionState) -> Dict[str, Any]:
    return {
        "type": "state_update",
        "payload": state.model_dump(),
    }


def message_to_state(message: Dict[str, Any]) -> PodcastProductionState:
    if "payload" not in message:
        raise ValueError("Invalid A2A message — missing payload")
    return PodcastProductionState(**message["payload"])

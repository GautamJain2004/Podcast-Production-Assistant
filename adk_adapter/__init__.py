"""
ADK Adapter Package
Exposes utilities to wrap internal agents into ADK-compatible handlers
with A2A (agent-to-agent) messaging support via the broker.
"""

from .adapter import ADKAgentWrapper
from .a2a_message import state_to_message, message_to_state

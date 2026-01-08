"""
LangGraph adapter package for A2A communication.
Provides wrappers and utilities for integrating LangGraph agents with the A2A broker.
"""

from .adapter import LangGraphAgentWrapper, register_wrappers_with_broker

__all__ = [
    "LangGraphAgentWrapper",
    "register_wrappers_with_broker",
]

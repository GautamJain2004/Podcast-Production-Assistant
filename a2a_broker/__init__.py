"""
A2A Broker package for routing A2A messages between runtimes (ADK, LangGraph, etc.)

Usage:
    from a2a_broker.broker import Broker, get_global_broker
    broker = get_global_broker()
    broker.publish_sync("topic", {"type":"podcast_state", "payload": {...}})
"""
from .broker import Broker, get_global_broker  # noqa: F401

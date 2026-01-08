"""
tools package: MCP tool implementations and client wrapper.
"""

from .mcp_client import get_mcp_client, get_mcp_client_sync, execute_tool_sync  # re-export
from .web_search_mcp import WebSearchTool
from .audio_calculator_mcp import AudioDurationTool

__all__ = [
    "get_mcp_client",
    "get_mcp_client_sync",
    "execute_tool_sync",
    "WebSearchTool",
    "AudioDurationTool",
]

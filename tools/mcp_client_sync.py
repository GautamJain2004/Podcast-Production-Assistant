# tools/mcp_client_sync.py
"""
Synchronous wrapper around the async MCP client.
Agents (which in this project are synchronous) should import and call execute_tool_sync(...)
This wrapper uses asyncio.run to call the async client when running in a normal CLI process.
If an event loop is already running, it will attempt a safe fallback to run the tool's synchronous interface
(if available), otherwise it logs and raises a RuntimeError to avoid blocking.
"""

import asyncio
import logging
from typing import Any, Dict

from .mcp_client import get_mcp_client

logger = logging.getLogger(__name__)

def execute_tool_sync(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    Synchronously execute a tool by name with the given arguments.
    Uses asyncio.run when possible. If an event loop is already running, tries to call the tool sync entrypoint.
    """
    try:
        # Normal case: no running loop -> use asyncio.run to call async client
        async def _call():
            client = await get_mcp_client()
            return await client.execute_tool(tool_name, arguments)
        return asyncio.run(_call())

    except RuntimeError:
        # Event loop already running — try safe fallbacks
        logger.warning("Detected running event loop. Attempting synchronous tool call (if available).")

        # Attempt to import and call the tool module directly to provide a sync fallback
        try:
            if tool_name == "web_search":
                from .web_search_mcp import WebSearchTool
                tool = WebSearchTool()
                return tool.search_web_sync(arguments.get("query", ""), arguments.get("num_results", 5))
            elif tool_name == "audio_duration_calculator":
                from .audio_calculator_mcp import AudioDurationTool
                tool = AudioDurationTool()
                return tool.calculate_duration_sync(arguments.get("script_text", ""), arguments.get("words_per_minute", None))
            else:
                raise RuntimeError("No sync fallback available for tool: " + tool_name)
        except Exception as e:
            logger.error(f"Sync fallback for tool {tool_name} failed: {e}", exc_info=True)
            raise

"""
MCP client helper and execute_tool_sync entrypoint.

Provides:
  - async get_mcp_client() -> MCPClient
  - get_mcp_client_sync() -> MCPClient (blocking)
  - execute_tool_sync(tool_name: str, arguments: dict) -> result  (blocking)
  - MCPClient.execute_tool(tool_name, args) is async and dispatches tools

This wrapper is intentionally defensive and will fall back to local tool implementations
if a production MCP server is not available.

Now uses HTTP MCP servers by default for better reliability and ease of use.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from .web_search_mcp import WebSearchTool
from .audio_calculator_mcp import AudioDurationTool

# Try to import HTTP MCP client (preferred)
try:
    from .mcp_client_http import MCPClientHTTP, execute_tool_http
    HTTP_MCP_AVAILABLE = True
except ImportError:
    HTTP_MCP_AVAILABLE = False
    MCPClientHTTP = None
    execute_tool_http = None

# Try to import real MCP client (stdio - legacy)
try:
    from .mcp_client_real import RealMCPClient
    REAL_MCP_AVAILABLE = True
except ImportError:
    REAL_MCP_AVAILABLE = False
    RealMCPClient = None

logger = logging.getLogger("tools.mcp_client")
logger.addHandler(logging.NullHandler())

# Singleton clients
_mcp_client = None
_real_mcp_client = None

# Tool to server mapping for real MCP client
TOOL_SERVER_MAP = {
    "web_search": "web-search",
    "audio_duration_calculator": "audio-tools"
}


class MCPClient:
    """
    Hybrid MCPClient that tries to use real MCP servers first, then falls back to local tools.
    
    This client will attempt to connect to real MCP servers via stdio protocol.
    If that fails or is not available, it falls back to local tool implementations.
    """

    def __init__(self, use_real_mcp: bool = True):
        """
        Initialize the MCP client.
        
        Args:
            use_real_mcp: If True, attempt to use real MCP servers. If False, use local tools only.
        """
        self.use_real_mcp = use_real_mcp and REAL_MCP_AVAILABLE
        self.real_client = None
        
        if self.use_real_mcp:
            try:
                self.real_client = RealMCPClient()
                logger.info("Real MCP client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize real MCP client, falling back to local tools: {e}")
                self.use_real_mcp = False
        
        # Pre-register local tool handlers as fallback
        self.tools = {
            "web_search": self._web_search,
            "audio_duration_calculator": self._audio_duration
        }

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Async execution API. Tries real MCP first, then falls back to local tools.
        """
        # Try real MCP client first
        if self.use_real_mcp and self.real_client and tool_name in TOOL_SERVER_MAP:
            try:
                server_name = TOOL_SERVER_MAP[tool_name]
                logger.debug(f"Attempting to execute {tool_name} via real MCP server {server_name}")
                result = await self.real_client.call_tool(server_name, tool_name, arguments)
                logger.info(f"Successfully executed {tool_name} via real MCP")
                return result
            except Exception as e:
                logger.warning(f"Real MCP execution failed for {tool_name}, falling back to local: {e}")
        
        # Fallback to local tool implementation
        logger.debug(f"Using local implementation for {tool_name}")
        if tool_name not in self.tools:
            raise ValueError(f"Tool not found: {tool_name}")

        handler = self.tools[tool_name]
        # If handler is coroutine, await it
        if asyncio.iscoroutinefunction(handler):
            return await handler(arguments)
        # Otherwise run in executor to keep event loop responsive
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: handler(arguments))

    # Local tool dispatchers (fallback implementations)
    def _web_search(self, arguments: Dict[str, Any]):
        query = arguments.get("query") or arguments.get("q") or ""
        num_results = int(arguments.get("num_results", arguments.get("num", 5)))
        tool = WebSearchTool()
        return tool.search_web(query, num_results)

    def _audio_duration(self, arguments: Dict[str, Any]):
        script_text = arguments.get("script_text", "")
        wpm = arguments.get("words_per_minute", None)
        tool = AudioDurationTool()
        return tool.calculate_duration(script_text, wpm)


async def get_mcp_client(use_real_mcp: bool = True) -> MCPClient:
    """
    Async accessor for the global MCP client.
    
    Args:
        use_real_mcp: If True, attempt to use real MCP servers. If False, use local tools only.
    """
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient(use_real_mcp=use_real_mcp)
    return _mcp_client


def get_mcp_client_sync(use_real_mcp: bool = True) -> MCPClient:
    """
    Blocking accessor for the global MCP client.
    
    Args:
        use_real_mcp: If True, attempt to use real MCP servers. If False, use local tools only.
    """
    loop = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an async loop; return already-created client or create synchronously
        # but avoid blocking; assume caller is async-capable.
        # Create a new client directly (fast)
        global _mcp_client
        if _mcp_client is None:
            _mcp_client = MCPClient(use_real_mcp=use_real_mcp)
        return _mcp_client

    # No running loop: safe to use asyncio.run
    return asyncio.run(get_mcp_client(use_real_mcp=use_real_mcp))


def execute_tool_sync(
    tool_name: str, 
    arguments: Optional[Dict[str, Any]] = None,
    use_real_mcp: bool = True
) -> Any:
    """
    Synchronous wrapper agents should import and call.

    It will:
      - try HTTP MCP servers first (if available and enabled)
      - fall back to local tool implementations if needed
      
    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments as a dictionary
        use_real_mcp: If True, attempt to use MCP servers. If False, use local tools only.
    
    Returns:
        Tool execution result
    """
    arguments = arguments or {}
    
    # Try HTTP MCP client first (preferred method)
    if HTTP_MCP_AVAILABLE and use_real_mcp:
        try:
            logger.debug(f"Attempting HTTP MCP for {tool_name}")
            return execute_tool_http(tool_name, arguments, use_http_mcp=True)
        except Exception as e:
            logger.debug(f"HTTP MCP failed for {tool_name}: {e}")
            # Continue to fallback
    
    # Final fallback: direct local dispatch (safe in any context)
    logger.debug(f"Using direct local fallback for {tool_name}")
    try:
        if tool_name == "web_search":
            tool = WebSearchTool()
            return tool.search_web(arguments.get("query", ""), int(arguments.get("num_results", 5)))
        elif tool_name == "audio_duration_calculator":
            tool = AudioDurationTool()
            return tool.calculate_duration(arguments.get("script_text", ""), arguments.get("words_per_minute", None))
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    except Exception as e:
        logger.exception(f"execute_tool_sync final fallback failed for {tool_name}: {e}")
        raise


async def execute_tool_async(
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    use_real_mcp: bool = True
) -> Any:
    """
    Async wrapper for tool execution.
    
    This is the preferred method for calling tools from async contexts.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments as a dictionary
        use_real_mcp: If True, attempt to use real MCP servers. If False, use local tools only.
    
    Returns:
        Tool execution result
    """
    arguments = arguments or {}
    client = await get_mcp_client(use_real_mcp=use_real_mcp)
    return await client.execute_tool(tool_name, arguments)

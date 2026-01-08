"""
Updated MCP client that uses HTTP servers instead of stdio.

This module provides the same interface as mcp_client.py but connects to
HTTP MCP servers running on localhost.
"""

import logging
from typing import Any, Dict, Optional

from .web_search_mcp import WebSearchTool
from .audio_calculator_mcp import AudioDurationTool

# Try to import HTTP MCP client
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from mcp_servers.http_mcp_client import HTTPMCPClient
    HTTP_MCP_AVAILABLE = True
except ImportError:
    HTTP_MCP_AVAILABLE = False
    HTTPMCPClient = None

logger = logging.getLogger("tools.mcp_client_http")
logger.addHandler(logging.NullHandler())

# Singleton client
_http_mcp_client = None


class MCPClientHTTP:
    """
    Hybrid MCP Client that tries HTTP MCP servers first, then falls back to local tools.
    """

    def __init__(self, use_http_mcp: bool = True):
        """
        Initialize the MCP client.
        
        Args:
            use_http_mcp: If True, attempt to use HTTP MCP servers. If False, use local tools only.
        """
        self.use_http_mcp = use_http_mcp and HTTP_MCP_AVAILABLE
        self.http_client = None
        
        if self.use_http_mcp:
            try:
                self.http_client = HTTPMCPClient()
                
                # Check which servers are available
                available = self.http_client.list_available_servers()
                logger.info(f"HTTP MCP servers status: {available}")
                
                if any(available.values()):
                    logger.info("HTTP MCP client initialized with available servers")
                else:
                    logger.warning("No HTTP MCP servers are running, will use local fallback")
                    self.use_http_mcp = False
                    
            except Exception as e:
                logger.warning(f"Failed to initialize HTTP MCP client: {e}")
                self.use_http_mcp = False
        
        # Pre-register local tool handlers as fallback
        self.local_tools = {
            "web_search": self._web_search_local,
            "audio_duration_calculator": self._audio_duration_local
        }

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute a tool. Tries HTTP MCP first, then falls back to local tools.
        """
        # Try HTTP MCP client first
        if self.use_http_mcp and self.http_client:
            try:
                logger.debug(f"Attempting to execute {tool_name} via HTTP MCP")
                result = self.http_client.execute_tool(tool_name, arguments)
                logger.info(f"Successfully executed {tool_name} via HTTP MCP")
                return result
            except Exception as e:
                logger.warning(f"HTTP MCP execution failed for {tool_name}: {e}")
                logger.info(f"Falling back to local implementation for {tool_name}")
        
        # Fallback to local tool implementation
        logger.debug(f"Using local implementation for {tool_name}")
        if tool_name not in self.local_tools:
            raise ValueError(f"Tool not found: {tool_name}")

        handler = self.local_tools[tool_name]
        return handler(arguments)

    # Local tool dispatchers (fallback implementations)
    def _web_search_local(self, arguments: Dict[str, Any]):
        """Local web search fallback."""
        query = arguments.get("query") or arguments.get("q") or ""
        num_results = int(arguments.get("num_results", arguments.get("num", 5)))
        tool = WebSearchTool()
        return tool.search_web(query, num_results)

    def _audio_duration_local(self, arguments: Dict[str, Any]):
        """Local audio duration fallback."""
        script_text = arguments.get("script_text", "")
        wpm = arguments.get("words_per_minute", None)
        tool = AudioDurationTool()
        return tool.calculate_duration(script_text, wpm)


def get_mcp_client_http(use_http_mcp: bool = True) -> MCPClientHTTP:
    """
    Get the global HTTP MCP client.
    
    Args:
        use_http_mcp: If True, attempt to use HTTP MCP servers. If False, use local tools only.
    """
    global _http_mcp_client
    if _http_mcp_client is None:
        _http_mcp_client = MCPClientHTTP(use_http_mcp=use_http_mcp)
    return _http_mcp_client


def execute_tool_http(
    tool_name: str, 
    arguments: Optional[Dict[str, Any]] = None,
    use_http_mcp: bool = True
) -> Any:
    """
    Execute a tool using HTTP MCP servers with automatic fallback.
    
    This is the main entry point for executing tools. It will:
      - Try HTTP MCP servers first (if available and enabled)
      - Fall back to local tool implementations if needed
      
    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments as a dictionary
        use_http_mcp: If True, attempt to use HTTP MCP servers. If False, use local tools only.
    
    Returns:
        Tool execution result
    """
    arguments = arguments or {}
    
    try:
        client = get_mcp_client_http(use_http_mcp=use_http_mcp)
        return client.execute_tool(tool_name, arguments)
    except Exception as e:
        logger.exception(f"execute_tool_http failed for {tool_name}: {e}")
        raise

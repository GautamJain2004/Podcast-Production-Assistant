"""
HTTP-based MCP Client

This client connects to HTTP MCP servers instead of spawning stdio processes.
"""

import requests
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("http_mcp_client")


class HTTPMCPClient:
    """
    HTTP-based MCP client that connects to running HTTP MCP servers.
    """
    
    def __init__(self):
        """Initialize the HTTP MCP client."""
        self.logger = logger
        
        # Server URLs
        self.servers = {
            "web-search": "http://localhost:8001",
            "audio-tools": "http://localhost:8002"
        }
        
        # Tool to server mapping
        self.tool_server_map = {
            "web_search": "web-search",
            "audio_duration_calculator": "audio-tools"
        }
    
    def check_server_health(self, server_name: str) -> bool:
        """
        Check if a server is running and healthy.
        
        Args:
            server_name: Name of the server (e.g., "web-search")
            
        Returns:
            True if server is healthy, False otherwise
        """
        if server_name not in self.servers:
            return False
        
        url = self.servers[server_name]
        
        try:
            response = requests.get(f"{url}/health", timeout=2)
            if response.status_code == 200:
                data = response.json()
                return data.get("status") == "healthy"
        except Exception as e:
            self.logger.debug(f"Health check failed for {server_name}: {e}")
        
        return False
    
    def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a tool on an HTTP MCP server.
        
        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to call
            arguments: Tool arguments as a dictionary
            
        Returns:
            Tool execution result
            
        Raises:
            ConnectionError: If server is not reachable
            ValueError: If server returns an error
        """
        if server_name not in self.servers:
            raise ValueError(f"Unknown server: {server_name}")
        
        url = self.servers[server_name]
        
        try:
            # Check if server is healthy first
            if not self.check_server_health(server_name):
                raise ConnectionError(f"Server {server_name} is not healthy or not running")
            
            # Make request
            self.logger.info(f"Calling tool '{tool_name}' on server '{server_name}'")
            
            response = requests.post(
                f"{url}/execute",
                json={
                    "tool": tool_name,
                    "arguments": arguments
                },
                timeout=30
            )
            
            # Check response
            if response.status_code != 200:
                error_data = response.json() if response.headers.get('content-type') == 'application/json' else {}
                error_msg = error_data.get('error', f"HTTP {response.status_code}")
                raise ValueError(f"Server error: {error_msg}")
            
            # Parse response
            data = response.json()
            
            if not data.get('success', False):
                raise ValueError(f"Tool execution failed: {data.get('error', 'Unknown error')}")
            
            self.logger.info(f"Tool '{tool_name}' executed successfully")
            
            # Return the appropriate data based on tool
            if tool_name == "web_search":
                return data.get('results', [])
            elif tool_name == "audio_duration_calculator":
                return data.get('duration_minutes', 0)
            else:
                return data
            
        except requests.exceptions.ConnectionError as e:
            self.logger.warning(f"Connection error to {server_name}: {e}")
            raise ConnectionError(f"Cannot connect to server {server_name} at {url}")
        except requests.exceptions.Timeout as e:
            self.logger.warning(f"Timeout connecting to {server_name}: {e}")
            raise ConnectionError(f"Timeout connecting to server {server_name}")
        except Exception as e:
            self.logger.exception(f"Error calling tool '{tool_name}': {e}")
            raise
    
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute a tool by routing to the appropriate server.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        # Map tool to server
        if tool_name not in self.tool_server_map:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        server_name = self.tool_server_map[tool_name]
        
        return self.call_tool(server_name, tool_name, arguments)
    
    def list_available_servers(self) -> Dict[str, bool]:
        """
        Check which servers are currently available.
        
        Returns:
            Dictionary mapping server names to availability status
        """
        status = {}
        for server_name in self.servers.keys():
            status[server_name] = self.check_server_health(server_name)
        return status

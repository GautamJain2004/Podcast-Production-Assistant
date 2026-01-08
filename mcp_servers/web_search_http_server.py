"""
HTTP-based MCP Server for Web Search

This server runs independently and accepts HTTP requests for web search operations.
Start it with: python mcp_servers/web_search_http_server.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from dotenv import load_dotenv

from tools.web_search_mcp import WebSearchTool

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("web_search_http_server")

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

# Initialize tool
web_tool = WebSearchTool()

# Server info
SERVER_NAME = "web-search"
SERVER_VERSION = "1.0.0"
SERVER_PORT = 8001


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "server": SERVER_NAME,
        "version": SERVER_VERSION
    })


@app.route('/tools', methods=['GET'])
def list_tools():
    """List available tools."""
    return jsonify({
        "tools": [
            {
                "name": "web_search",
                "description": (
                    "Search the web using Serper API. Returns relevant web pages, "
                    "articles, and content related to the search query."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
                        },
                        "num_results": {
                            "type": "number",
                            "description": "Number of results to return (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
    })


@app.route('/execute', methods=['POST'])
def execute_tool():
    """Execute a tool."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No JSON data provided"
            }), 400
        
        tool_name = data.get('tool')
        arguments = data.get('arguments', {})
        
        logger.info(f"Executing tool: {tool_name} with arguments: {arguments}")
        
        if tool_name != 'web_search':
            return jsonify({
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }), 400
        
        # Extract arguments
        query = arguments.get('query', '')
        num_results = int(arguments.get('num_results', 5))
        
        if not query:
            return jsonify({
                "success": False,
                "error": "Query parameter is required"
            }), 400
        
        # Execute tool
        results = web_tool.search_web(query, num_results)
        
        # Return response
        response = {
            "success": True,
            "tool": tool_name,
            "results": results,
            "query": query,
            "count": len(results)
        }
        
        logger.info(f"Tool executed successfully. Found {len(results)} results")
        
        return jsonify(response)
        
    except Exception as e:
        logger.exception(f"Error executing tool: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/', methods=['GET'])
def index():
    """Server info endpoint."""
    return jsonify({
        "server": SERVER_NAME,
        "version": SERVER_VERSION,
        "status": "running",
        "endpoints": {
            "health": "/health",
            "list_tools": "/tools",
            "execute": "/execute (POST)"
        }
    })


def main():
    """Start the HTTP server."""
    logger.info("="*60)
    logger.info(f"Starting {SERVER_NAME} HTTP MCP Server")
    logger.info("="*60)
    
    # Check for API key
    serper_key = os.getenv("SERPER_API_KEY")
    if serper_key:
        logger.info(f"✅ SERPER_API_KEY found: {serper_key[:10]}...")
    else:
        logger.warning("⚠️  SERPER_API_KEY not found - will use mock results")
    
    logger.info(f"Server: {SERVER_NAME}")
    logger.info(f"Version: {SERVER_VERSION}")
    logger.info(f"Port: {SERVER_PORT}")
    logger.info(f"URL: http://localhost:{SERVER_PORT}")
    logger.info("="*60)
    logger.info("Available endpoints:")
    logger.info(f"  GET  / - Server info")
    logger.info(f"  GET  /health - Health check")
    logger.info(f"  GET  /tools - List available tools")
    logger.info(f"  POST /execute - Execute a tool")
    logger.info("="*60)
    logger.info("Press Ctrl+C to stop the server")
    logger.info("="*60)
    
    # Start server
    app.run(
        host='0.0.0.0',
        port=SERVER_PORT,
        debug=False,
        use_reloader=False
    )


if __name__ == "__main__":
    main()

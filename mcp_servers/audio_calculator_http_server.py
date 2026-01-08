"""
HTTP-based MCP Server for Audio Duration Calculator

This server runs independently and accepts HTTP requests for audio duration calculations.
Start it with: python mcp_servers/audio_calculator_http_server.py
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

from tools.audio_calculator_mcp import AudioDurationTool

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("audio_calculator_http_server")

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

# Initialize tool
audio_tool = AudioDurationTool()

# Server info
SERVER_NAME = "audio-tools"
SERVER_VERSION = "1.0.0"
SERVER_PORT = 8002


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
                "name": "audio_duration_calculator",
                "description": (
                    "Calculate estimated audio duration for podcast scripts. "
                    "Analyzes text and estimates speaking time based on word count "
                    "and speaking rate (words per minute)."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_text": {
                            "type": "string",
                            "description": "The podcast script text to analyze"
                        },
                        "words_per_minute": {
                            "type": "number",
                            "description": "Speaking rate in words per minute (default: 150)",
                            "default": 150
                        }
                    },
                    "required": ["script_text"]
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
        
        logger.info(f"Executing tool: {tool_name} with arguments keys: {list(arguments.keys())}")
        
        if tool_name != 'audio_duration_calculator':
            return jsonify({
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }), 400
        
        # Extract arguments
        script_text = arguments.get('script_text', '')
        wpm = arguments.get('words_per_minute', None)
        
        if not script_text:
            return jsonify({
                "success": False,
                "error": "script_text parameter is required"
            }), 400
        
        # Execute tool
        result = audio_tool.calculate_duration(script_text, wpm)
        
        # Return response
        word_count = len(script_text.split())
        response = {
            "success": True,
            "tool": tool_name,
            "duration_minutes": result,
            "word_count": word_count,
            "words_per_minute": wpm or 150
        }
        
        logger.info(f"Tool executed successfully. Duration: {result:.2f} minutes")
        
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

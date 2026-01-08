"""
Start all HTTP MCP servers

This script starts both the web search and audio calculator MCP servers.
Run this before starting your frontend application.
"""

import subprocess
import sys
import time
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()


def start_servers():
    """Start both MCP servers in separate processes."""
    print("="*60)
    print("Starting HTTP MCP Servers")
    print("="*60)
    
    # Check for SERPER_API_KEY
    serper_key = os.getenv("SERPER_API_KEY")
    if serper_key:
        print(f"✅ SERPER_API_KEY found: {serper_key[:10]}...")
    else:
        print("⚠️  SERPER_API_KEY not found - web search will use mock results")
    
    print("\nStarting servers...")
    print("-"*60)
    
    # Start web search server
    print("Starting Web Search Server on port 8001...")
    web_search_process = subprocess.Popen(
        [sys.executable, "mcp_servers/web_search_http_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Start audio calculator server
    print("Starting Audio Calculator Server on port 8002...")
    audio_calc_process = subprocess.Popen(
        [sys.executable, "mcp_servers/audio_calculator_http_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Wait a bit for servers to start
    print("\nWaiting for servers to start...")
    time.sleep(3)
    
    # Check if servers are running
    if web_search_process.poll() is None and audio_calc_process.poll() is None:
        print("\n" + "="*60)
        print("✅ Both MCP Servers Started Successfully!")
        print("="*60)
        print("\nServer URLs:")
        print("  Web Search:        http://localhost:8001")
        print("  Audio Calculator:  http://localhost:8002")
        print("\nEndpoints:")
        print("  GET  /health  - Health check")
        print("  GET  /tools   - List available tools")
        print("  POST /execute - Execute a tool")
        print("\n" + "="*60)
        print("Servers are running. Press Ctrl+C to stop all servers.")
        print("="*60)
        
        try:
            # Keep script running and show output
            while True:
                # Read output from web search server
                if web_search_process.poll() is None:
                    line = web_search_process.stdout.readline()
                    if line:
                        print(f"[WEB] {line.strip()}")
                
                # Read output from audio calc server
                if audio_calc_process.poll() is None:
                    line = audio_calc_process.stdout.readline()
                    if line:
                        print(f"[AUDIO] {line.strip()}")
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n\nStopping servers...")
            web_search_process.terminate()
            audio_calc_process.terminate()
            
            # Wait for processes to terminate
            web_search_process.wait(timeout=5)
            audio_calc_process.wait(timeout=5)
            
            print("✅ All servers stopped.")
            
    else:
        print("\n❌ Error: One or more servers failed to start")
        
        if web_search_process.poll() is not None:
            print("\nWeb Search Server output:")
            print(web_search_process.stdout.read())
        
        if audio_calc_process.poll() is not None:
            print("\nAudio Calculator Server output:")
            print(audio_calc_process.stdout.read())
        
        # Clean up
        if web_search_process.poll() is None:
            web_search_process.terminate()
        if audio_calc_process.poll() is None:
            audio_calc_process.terminate()
        
        sys.exit(1)


if __name__ == "__main__":
    start_servers()

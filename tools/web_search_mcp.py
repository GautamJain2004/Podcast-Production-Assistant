"""
WebSearchTool: MCP-compatible web search tool.

Uses SERPER_API_KEY or WEB_SEARCH_API_KEY environment variables.
If no API key is found, returns mock search results for development.
Provides:
  - async execute(query: str, num_results: int) -> List[dict]
  - sync wrapper search_web(query: str, num_results: int) -> List[dict]
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional

import requests  # sync HTTP; keep simple and reliable

logger = logging.getLogger("tools.web_search_mcp")
logger.addHandler(logging.NullHandler())

SERPER_API_KEY = os.getenv("SERPER_API_KEY") or os.getenv("WEB_SEARCH_API_KEY")
SERPER_URL = "https://google.serper.dev/search"


class WebSearchTool:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or SERPER_API_KEY

    async def execute(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        Async entrypoint for the tool. For simplicity we run the sync HTTP call in a threadpool.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._search_sync, query, num_results)

    def _search_sync(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        Sync web search implementation. Uses Serper API if API key present; otherwise returns mocks.
        """
        logger.info(f"[WebSearchTool] Searching for: {query}")
        if not self.api_key:
            logger.warning("No SERPER_API_KEY found; returning mock search results.")
            return self._mock_results(query, num_results)

        try:
            payload = {"q": query, "num": num_results}
            headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
            resp = requests.post(SERPER_URL, headers=headers, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            results = []
            # Serper returns 'organic' results - normalize
            for item in data.get("organic", [])[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("link", "") or item.get("url", ""),
                    "source": "serper"
                })
            if not results:
                # fallback safe mock
                return self._mock_results(query, num_results)
            return results

        except Exception as e:
            logger.exception(f"Web search failed: {e}")
            return self._mock_results(query, num_results)

    def _mock_results(self, query: str, num_results: int) -> List[Dict[str, Any]]:
        return [
            {
                "title": f"Mock result {i+1} for {query}",
                "snippet": f"This is mock snippet about {query}.",
                "url": f"https://example.com/{query.replace(' ', '-')}/result-{i+1}",
                "source": "mock"
            }
            for i in range(num_results)
        ]

    # Convenience sync wrapper (callable from non-async code)
    def search_web(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        return self._search_sync(query, num_results)

from agents.base_adk_agent import BaseADKAgent
from google.genai import Client
from schemas.state_models import PodcastProductionState, ResearchMaterial
from config.settings import get_gemini_model
from tools.mcp_client import execute_tool_sync
import logging

class TopicResearcherAgent(BaseADKAgent):
    """Agent that researches the refined topic using web search tools."""

    def __init__(self, gemini_client: Client):
        super().__init__(
            name="TopicResearcherAgent",
            description="Researches podcast topics using web search tools and gathers sources",
            gemini_client=gemini_client
        )

    def execute(self, state: PodcastProductionState) -> PodcastProductionState:
        # Ensure topic is a string
        topic_str = state.selected_refined_topic
        if isinstance(topic_str, dict):
            topic_str = topic_str.get("title", str(topic_str))
        
        self.logger.info(f"Researching topic: {topic_str}")

        # Generate search queries via LLM (keep existing approach)
        query_prompt = f"""
        Generate 3 specific search queries to research this podcast topic: "{topic_str}"

        The queries should be optimized for finding:
        - Latest news and developments
        - Expert opinions and analysis
        - Data and statistics
        - Different perspectives on the topic

        Return the queries as a JSON list.
        """

        try:
            query_response = self.gemini_client.models.generate_content(
                model=get_gemini_model(),
                contents=query_prompt
            )

            import json
            content = query_response.text
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            queries = json.loads(content)
            
            # Ensure queries is a list
            if not isinstance(queries, list):
                self.logger.warning(f"LLM returned non-list queries: {type(queries)}, using fallback")
                queries = [
                    state.selected_refined_topic,
                    f"{state.selected_refined_topic} news",
                    f"{state.selected_refined_topic} statistics"
                ]

        except Exception as e:
            self.logger.warning(f"LLM query generation failed, falling back to naive queries: {e}")
            queries = [
                state.selected_refined_topic,
                f"{state.selected_refined_topic} news",
                f"{state.selected_refined_topic} statistics"
            ]

        research_results = []
        all_sources = []

        # Use the execute_tool_sync wrapper to call web_search MCP tool
        for i, query in enumerate(queries[:5]):  # limit to 5 queries for safety
            try:
                self.logger.info(f"Executing MCP web_search tool for query: {query}")
                results = execute_tool_sync("web_search", {"query": query, "num_results": 5})
                
                if not results:
                    self.logger.warning(f"No results returned for query: {query}")
                    continue
                
                # Handle different result formats
                # If results is a string, try to parse as JSON
                if isinstance(results, str):
                    try:
                        import json
                        results = json.loads(results)
                    except:
                        self.logger.warning(f"Could not parse results as JSON: {results[:100]}")
                        continue
                
                # Ensure results is a list
                if not isinstance(results, list):
                    self.logger.warning(f"Results is not a list: {type(results)}")
                    continue
                
                # results expected to be a list of dicts {title, snippet, url}
                for r in (results or [])[:5]:
                    try:
                        # Skip if r is not a dict
                        if not isinstance(r, dict):
                            self.logger.warning(f"Result item is not a dict: {type(r)}")
                            continue
                        
                        # Ensure ResearchMaterial objects are created correctly with validation
                        rm = ResearchMaterial(
                            query=query,
                            title=r.get("title", "")[:250],
                            snippet=r.get("snippet", "")[:500],
                            url=r.get("url", "") or r.get("link", ""),
                            content=(r.get("snippet", "") or r.get("title", ""))  # minimal content if not provided
                        )
                        research_results.append(rm)
                        if rm.url:
                            all_sources.append(rm.url)
                        self.logger.debug(f"Created ResearchMaterial: {rm.title[:50]}...")
                    except Exception as e:
                        self.logger.warning(f"Failed to create ResearchMaterial from result: {e}")
                        continue
                        
            except Exception as e:
                self.logger.error(f"MCP web search failed for query '{query}': {e}")
                # Continue with other queries even if one fails
                continue

        # Remove duplicates while preserving order
        unique_sources = []
        seen = set()
        for s in all_sources:
            if s and s not in seen:
                unique_sources.append(s)
                seen.add(s)

        # Handle case where no research materials were found
        if not research_results:
            # Ensure topic is a string
            topic_str = state.selected_refined_topic
            if isinstance(topic_str, dict):
                topic_str = topic_str.get("title", str(topic_str))
            
            self.logger.warning(f"No research materials found for topic: {topic_str}")
            # Create a minimal fallback research material
            fallback_material = ResearchMaterial(
                query=topic_str,
                title=f"Research topic: {topic_str}",
                snippet="No external research results available. Proceeding with topic information.",
                url="",
                content=f"Topic for research: {topic_str}"
            )
            research_results.append(fallback_material)

        state.research_materials = research_results
        state.all_sources = unique_sources

        self.logger.info(f"Research complete: Gathered {len(research_results)} research items from {len(unique_sources)} unique sources")

        # Validate state before returning
        try:
            state.model_validate(state.model_dump())
        except Exception as e:
            self.logger.error(f"State validation failed: {str(e)}")
            # Ensure minimal valid state
            if not state.research_materials:
                fallback_material = ResearchMaterial(
                    query=state.selected_refined_topic,
                    title=f"Research topic: {state.selected_refined_topic}",
                    snippet="Validation fallback material",
                    url="",
                    content=f"Topic: {state.selected_refined_topic}"
                )
                state.research_materials = [fallback_material]

        return state

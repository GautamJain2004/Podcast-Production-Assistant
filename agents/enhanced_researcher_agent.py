"""
Enhanced Topic Researcher Agent with YouTube and Academic Search

This agent extends the base researcher with:
- YouTube transcript extraction
- Academic paper search (arXiv, PubMed)
- Parallel execution of research tasks
"""

import json
import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from agents.base_adk_agent import BaseADKAgent
from google.genai import Client
from schemas.state_models import PodcastProductionState, ResearchMaterial
from config.settings import get_gemini_model
from tools.mcp_client import execute_tool_sync
from tools.youtube_transcript_tool import get_youtube_transcript, search_youtube_videos
from tools.academic_search_tool import search_academic_papers, format_paper_for_research
from tools.citation_manager import CitationManager

logger = logging.getLogger(__name__)


class EnhancedTopicResearcherAgent(BaseADKAgent):
    """
    Enhanced researcher that gathers information from multiple sources in parallel:
    - Web search (via MCP)
    - YouTube transcripts
    - Academic papers (arXiv, PubMed)
    """

    def __init__(self, gemini_client: Client, max_workers: int = 5):
        super().__init__(
            name="EnhancedTopicResearcherAgent",
            description="Researches topics using web search, YouTube, and academic databases in parallel",
            gemini_client=gemini_client
        )
        # Use object.__setattr__ for Pydantic models
        object.__setattr__(self, 'max_workers', max_workers)
        object.__setattr__(self, 'citation_manager', CitationManager())

    def generate_search_queries(self, topic: str) -> Dict[str, List[str]]:
        """
        Use LLM to generate optimized search queries for different sources.
        
        Returns:
            Dict with 'web', 'youtube', 'academic' keys containing query lists
        """
        query_prompt = f"""
        Generate search queries for researching this podcast topic: "{topic}"

        Create queries optimized for three different sources:
        1. Web search: 3 queries for finding news, articles, and general information
        2. YouTube: 2 queries for finding relevant video content and expert talks
        3. Academic: 2 queries for finding research papers and scholarly articles

        Return as JSON with this structure:
        {{
            "web": ["query1", "query2", "query3"],
            "youtube": ["query1", "query2"],
            "academic": ["query1", "query2"]
        }}
        """

        try:
            response = self.gemini_client.models.generate_content(
                model=get_gemini_model(),
                contents=query_prompt
            )

            content = response.text
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            
            queries = json.loads(content)
            
            # Validate structure
            if not all(k in queries for k in ['web', 'youtube', 'academic']):
                raise ValueError("Missing required query categories")
            
            return queries

        except Exception as e:
            self.logger.warning(f"LLM query generation failed: {e}, using fallback")
            return {
                "web": [topic, f"{topic} news", f"{topic} latest"],
                "youtube": [topic, f"{topic} explained"],
                "academic": [topic, f"{topic} research"]
            }

    def search_web(self, query: str) -> List[ResearchMaterial]:
        """Execute web search via MCP tool."""
        materials = []
        try:
            self.logger.info(f"Web search: {query}")
            results = execute_tool_sync("web_search", {"query": query, "num_results": 5})
            
            # Handle string results - try to parse as JSON
            if isinstance(results, str):
                try:
                    # Clean up the string - remove any leading/trailing whitespace
                    results = results.strip()
                    # Try to parse as JSON
                    results = json.loads(results)
                except json.JSONDecodeError as je:
                    self.logger.error(f"JSON decode error for web search: {je}")
                    self.logger.debug(f"Raw results: {results[:200]}")
                    return materials
            
            # If results is already a list, use it directly
            if not isinstance(results, list):
                self.logger.warning(f"Web search returned non-list type: {type(results)}")
                return materials
            
            for r in results[:5]:
                if not isinstance(r, dict):
                    continue
                
                try:
                    rm = ResearchMaterial(
                        query=query,
                        title=r.get("title", "")[:250],
                        snippet=r.get("snippet", "")[:500],
                        url=r.get("url", "") or r.get("link", ""),
                        content=r.get("snippet", "") or r.get("title", ""),
                        source="web"  # Set source type
                    )
                    materials.append(rm)
                    self.logger.info(f"Added web result: {rm.title[:50]}...")
                except Exception as e:
                    self.logger.warning(f"Failed to create ResearchMaterial: {e}")
                    
        except Exception as e:
            self.logger.error(f"Web search failed for '{query}': {e}", exc_info=True)
        
        return materials

    def search_youtube(self, query: str) -> List[ResearchMaterial]:
        """Search YouTube and extract transcripts."""
        materials = []
        try:
            self.logger.info(f"YouTube search: {query}")
            videos = search_youtube_videos(query, max_results=3)
            
            for video in videos:
                try:
                    # Get transcript
                    transcript_data = get_youtube_transcript(video['url'])
                    
                    if transcript_data['success']:
                        rm = ResearchMaterial(
                            query=query,
                            title=f"[VIDEO] {transcript_data['title']}",
                            snippet=transcript_data['transcript'][:500],
                            url=transcript_data['url'],
                            content=transcript_data['transcript'][:2000],  # Limit content size
                            source="youtube"  # Set source type
                        )
                        materials.append(rm)
                        self.logger.info(f"Extracted transcript from: {video['title']}")
                    else:
                        # Even without transcript, add video as reference
                        rm = ResearchMaterial(
                            query=query,
                            title=f"[VIDEO] {video['title']}",
                            snippet=f"Video reference (transcript unavailable): {video['title']}",
                            url=video['url'],
                            content=f"Video: {video['title']}",
                            source="youtube"  # Set source type
                        )
                        materials.append(rm)
                        
                except Exception as e:
                    self.logger.warning(f"Failed to process YouTube video: {e}")
                    
        except Exception as e:
            self.logger.error(f"YouTube search failed for '{query}': {e}")
        
        return materials

    def search_academic(self, query: str) -> List[ResearchMaterial]:
        """Search academic databases (arXiv, PubMed)."""
        materials = []
        try:
            self.logger.info(f"Academic search: {query}")
            results = search_academic_papers(query, max_results=5)
            
            for source, papers in results.items():
                for paper in papers[:3]:  # Limit papers per source
                    try:
                        formatted = format_paper_for_research(paper)
                        # Determine source type (arxiv or pubmed)
                        source_type = "arxiv" if source == "arxiv" else "pubmed"
                        rm = ResearchMaterial(
                            query=query,
                            title=f"[PAPER] {paper.get('title', 'Unknown')}",
                            snippet=paper.get('summary', '')[:500],
                            url=paper.get('url', ''),
                            content=formatted[:2000],
                            source=source_type  # Set source type
                        )
                        materials.append(rm)
                        self.logger.info(f"Found paper: {paper.get('title', 'Unknown')[:50]}...")
                    except Exception as e:
                        self.logger.warning(f"Failed to process academic paper: {e}")
                        
        except Exception as e:
            self.logger.error(f"Academic search failed for '{query}': {e}")
        
        return materials

    def execute_parallel_research(self, queries: Dict[str, List[str]]) -> List[ResearchMaterial]:
        """
        Execute all research tasks in parallel using ThreadPoolExecutor.
        
        Args:
            queries: Dict with 'web', 'youtube', 'academic' query lists
        
        Returns:
            Combined list of ResearchMaterial objects
        """
        all_materials = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            
            # Submit web search tasks
            for query in queries.get('web', []):
                futures.append(executor.submit(self.search_web, query))
            
            # Submit YouTube search tasks
            for query in queries.get('youtube', []):
                futures.append(executor.submit(self.search_youtube, query))
            
            # Submit academic search tasks
            for query in queries.get('academic', []):
                futures.append(executor.submit(self.search_academic, query))
            
            # Collect results as they complete
            for future in as_completed(futures):
                try:
                    materials = future.result()
                    all_materials.extend(materials)
                    self.logger.debug(f"Collected {len(materials)} materials from parallel task")
                except Exception as e:
                    self.logger.error(f"Parallel research task failed: {e}")
        
        return all_materials

    def execute(self, state: PodcastProductionState) -> PodcastProductionState:
        """
        Execute enhanced research with parallel execution.
        
        Args:
            state: Current podcast production state
            
        Returns:
            Updated state with research materials from all sources
        """
        topic_str = state.selected_refined_topic
        if isinstance(topic_str, dict):
            topic_str = topic_str.get("title", str(topic_str))
        
        self.logger.info(f"Starting enhanced research for: {topic_str}")
        
        # Initialize citation manager for this research session
        object.__setattr__(self, 'citation_manager', CitationManager())
        
        # Generate optimized queries for all sources
        queries = self.generate_search_queries(topic_str)
        self.logger.info(f"Generated queries - Web: {len(queries['web'])}, YouTube: {len(queries['youtube'])}, Academic: {len(queries['academic'])}")
        
        # Execute all research in parallel
        research_materials = self.execute_parallel_research(queries)
        
        # Add citations for all research materials
        for material in research_materials:
            citation_id = self.citation_manager.add_citation_from_research_material(material)
            material.citation_id = citation_id
            # Mark as used in research phase
            self.citation_manager.mark_citation_used(citation_id, "research")
        
        # Extract unique sources
        all_sources = []
        seen = set()
        for material in research_materials:
            if material.url and material.url not in seen:
                all_sources.append(material.url)
                seen.add(material.url)
        
        # Handle case where no materials found
        if not research_materials:
            self.logger.warning(f"No research materials found for: {topic_str}")
            fallback = ResearchMaterial(
                query=topic_str,
                title=f"Research topic: {topic_str}",
                snippet="No external research results available.",
                url="",
                content=f"Topic: {topic_str}"
            )
            research_materials = [fallback]
        
        # Update state
        state.research_materials = research_materials
        state.all_sources = all_sources
        
        # Store citation data in state
        state.citations_data = self.citation_manager.to_json()
        
        self.logger.info(f"Research complete: {len(research_materials)} materials from {len(all_sources)} sources")
        self.logger.info(f"  - Web results: {sum(1 for m in research_materials if not m.title.startswith('['))}")
        self.logger.info(f"  - YouTube results: {sum(1 for m in research_materials if m.title.startswith('[VIDEO]'))}")
        self.logger.info(f"  - Academic results: {sum(1 for m in research_materials if m.title.startswith('[PAPER]'))}")
        self.logger.info(f"  - Citations tracked: {len(self.citation_manager.get_all_citations())}")
        
        # Validate state
        try:
            state.model_validate(state.model_dump())
        except Exception as e:
            self.logger.error(f"State validation failed: {e}")
            if not state.research_materials:
                state.research_materials = [fallback]
        
        return state

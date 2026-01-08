from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List, Dict, Any, Optional
from agents.base_langgraph_agent import BaseLangGraphAgent
from schemas.state_models import PodcastProductionState, EpisodeOutline
from config.settings import get_gemini_client, get_gemini_model
import logging


class ScriptGraphState(TypedDict):
    """State schema for the script generation graph."""
    selected_refined_topic: str
    tone: str
    episode_outline: Optional[Dict[str, Any]]
    research_materials: List[Dict[str, Any]]
    outline_text: str
    research_context: str
    raw_script: str
    final_script: str
    used_citation_ids: List[str]


class ScriptWriterAgent(BaseLangGraphAgent):
    """Agent that writes the full podcast script based on the outline and research using LangGraph."""

    def __init__(self):
        super().__init__(
            name="ScriptWriterAgent",
            description="Writes engaging podcast scripts in conversational tone"
        )
        self.llm = get_gemini_client(strict=True)
        self.model = get_gemini_model()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state graph for script generation."""
        # Define the state graph
        workflow = StateGraph(ScriptGraphState)
        
        # Add nodes for: extract_outline, generate_script, format_script
        workflow.add_node("extract_outline", self._extract_outline_node)
        workflow.add_node("generate_script", self._generate_script_node)
        workflow.add_node("format_script", self._format_script_node)
        
        # Add edges connecting nodes
        workflow.set_entry_point("extract_outline")
        workflow.add_edge("extract_outline", "generate_script")
        workflow.add_edge("generate_script", "format_script")
        workflow.add_edge("format_script", END)
        
        # Compile graph with checkpointing
        checkpointer = MemorySaver()
        return workflow.compile(checkpointer=checkpointer)

    def _extract_outline_node(self, state: ScriptGraphState) -> ScriptGraphState:
        """Extract outline and research from state to prepare for script generation."""
        self.logger.info("Extracting outline and research materials")
        
        episode_outline = state.get("episode_outline")
        research_materials = state.get("research_materials", [])
        
        # Format outline as text
        if episode_outline:
            outline_parts = [
                f"TITLE: {episode_outline.get('title', 'Untitled')}",
                f"\nINTRODUCTION:\n{episode_outline.get('introduction', '')}",
                "\nMAIN SECTIONS:"
            ]
            
            for i, section in enumerate(episode_outline.get('main_sections', []), 1):
                outline_parts.append(f"\n{i}. {section.get('title', 'Section')}")
                for point in section.get('key_points', []):
                    outline_parts.append(f"   - {point}")
            
            outline_parts.append(f"\nCONCLUSION:\n{episode_outline.get('conclusion', '')}")
            outline_text = "\n".join(outline_parts)
        else:
            outline_text = "No outline available."
        
        # Format research context with sources
        if research_materials:
            research_context = "\n".join([
                f"- {item.get('content', '')} [Source: {item.get('url', 'N/A')}]"
                for item in research_materials[:5]
            ])
        else:
            research_context = "No research available."
        
        state["outline_text"] = outline_text
        state["research_context"] = research_context
        self.logger.info(f"Extracted outline and {len(research_materials[:5])} research items")
        
        return state

    def _generate_script_node(self, state: ScriptGraphState) -> ScriptGraphState:
        """Generate script by calling Gemini API with outline context."""
        self.logger.info("Generating podcast script")
        
        topic = state.get("selected_refined_topic", "Unknown Topic")
        tone = state.get("tone", "professional")
        outline_text = state.get("outline_text", "No outline available.")
        research_materials = state.get("research_materials", [])
        
        # Format research with citation IDs
        research_context = ""
        if research_materials:
            research_parts = []
            for item in research_materials[:10]:  # Use more sources
                citation_id = item.get('citation_id', 'unknown')
                content = item.get('content', '')[:300]  # Limit length
                title = item.get('title', 'Unknown')
                research_parts.append(f"[{citation_id}] {title}\n{content}")
            research_context = "\n\n".join(research_parts)
        else:
            research_context = "No research available."
        
        prompt = f"""
        Write a full podcast script based on the outline and research below.

        EPISODE TOPIC: {topic}
        TONE: {tone}

        OUTLINE:
        {outline_text}

        RESEARCH SOURCES (with citation IDs):
        {research_context}

        IMPORTANT INSTRUCTIONS:
        1. Follow the outline structure exactly
        2. Maintain a {tone} tone throughout
        3. ONLY use facts and information from the research sources provided above
        4. When you use information from a source, cite it using its citation ID like this: "According to recent research [ref1], ..." or "Studies show [ref3] that..."
        5. DO NOT cite sources you don't actually use
        6. Sound natural when spoken aloud
        7. Include smooth transitions between sections
        8. Be specific with facts, statistics, and examples from the sources

        Format the script with clear section markers.
        Return the complete script as plain text, ready to be read aloud.
        REMEMBER: Only include citation IDs [refX] for sources you actually reference!
        """
        
        # Don't catch exceptions here - let retry logic handle them
        response = self.llm.models.generate_content(
            model=self.model,
            contents=prompt
        )
        
        raw_script = response.text
        state["raw_script"] = raw_script
        self.logger.info(f"Successfully generated script ({len(raw_script)} characters)")
        
        return state

    def _format_script_node(self, state: ScriptGraphState) -> ScriptGraphState:
        """Clean and format the final script."""
        self.logger.info("Formatting final script")
        
        raw_script = state.get("raw_script", "")
        
        # Clean up the script (remove markdown code blocks if present)
        final_script = raw_script
        if "```" in final_script:
            # Remove markdown code block markers
            final_script = final_script.replace("```markdown", "").replace("```", "").strip()
        
        # Ensure proper spacing
        final_script = final_script.strip()
        
        # Extract citation IDs used in the script
        import re
        citation_pattern = r'\[ref\d+\]'
        used_citations = re.findall(citation_pattern, final_script)
        unique_citations = list(set(used_citations))
        
        state["final_script"] = final_script
        state["used_citation_ids"] = unique_citations
        
        self.logger.info(f"Formatted script ready ({len(final_script)} characters)")
        self.logger.info(f"Found {len(unique_citations)} unique citations used in script: {unique_citations}")
        
        return state

    def _state_to_graph_input(self, state: PodcastProductionState) -> ScriptGraphState:
        """Convert PodcastProductionState to graph input format."""
        # Serialize episode_outline to dict
        episode_outline_dict = None
        if state.episode_outline:
            episode_outline_dict = state.episode_outline.model_dump()
        
        # Serialize research materials to dicts
        research_materials = [
            material.model_dump() for material in (state.research_materials or [])
        ]
        
        return ScriptGraphState(
            selected_refined_topic=state.selected_refined_topic or state.initial_topic,
            tone=state.tone,
            episode_outline=episode_outline_dict,
            research_materials=research_materials,
            outline_text="",
            research_context="",
            raw_script="",
            final_script=""
        )

    def _graph_output_to_state(
        self, 
        output: Dict[str, Any], 
        original: PodcastProductionState
    ) -> PodcastProductionState:
        """Merge graph output back into PodcastProductionState with final_script."""
        # Extract the final_script from graph output
        final_script = output.get("final_script", "")
        used_citation_ids = output.get("used_citation_ids", [])
        
        if final_script:
            # Update the original state with the final script
            original.final_script = final_script
            original.update_timestamp()
            self.logger.info(f"Updated state with final script ({len(final_script)} characters)")
        
        # Update citation manager with used citations
        if used_citation_ids and hasattr(original, 'citations_data') and original.citations_data:
            self.logger.info(f"Marking {len(used_citation_ids)} citations as used in script")
            # Store used citation IDs in state for later processing
            if not hasattr(original, 'used_citation_ids'):
                original.used_citation_ids = []
            original.used_citation_ids = used_citation_ids
        
        # Validate state before returning
        try:
            original.model_validate(original.model_dump())
        except Exception as e:
            self.logger.error(f"State validation failed: {str(e)}")
            # Ensure minimal valid script if validation fails
            if not original.final_script:
                original.final_script = f"Script placeholder for {original.selected_refined_topic}"
        
        return original

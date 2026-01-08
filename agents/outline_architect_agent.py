from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List, Dict, Any
from agents.base_langgraph_agent import BaseLangGraphAgent
from schemas.state_models import PodcastProductionState, EpisodeOutline, Section
from config.settings import get_gemini_client, get_gemini_model
import json
import logging


class OutlineGraphState(TypedDict):
    """State schema for the outline generation graph."""
    selected_refined_topic: str
    tone: str
    research_materials: List[Dict[str, Any]]
    research_summary: str
    outline_data: Dict[str, Any]
    episode_outline: Dict[str, Any]


class OutlineArchitectAgent(BaseLangGraphAgent):
    """Agent that creates a structured outline for the podcast episode using LangGraph."""

    def __init__(self):
        super().__init__(
            name="OutlineArchitectAgent",
            description="Creates structured outlines for podcast episodes based on research"
        )
        self.llm = get_gemini_client(strict=True)
        self.model = get_gemini_model()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state graph for outline generation."""
        # Define the state graph
        workflow = StateGraph(OutlineGraphState)
        
        # Add nodes
        workflow.add_node("extract_research", self._extract_research_node)
        workflow.add_node("generate_outline", self._generate_outline_node)
        workflow.add_node("validate_outline", self._validate_outline_node)
        
        # Add edges connecting nodes in sequence
        workflow.set_entry_point("extract_research")
        workflow.add_edge("extract_research", "generate_outline")
        workflow.add_edge("generate_outline", "validate_outline")
        workflow.add_edge("validate_outline", END)
        
        # Compile graph with MemorySaver checkpointer
        checkpointer = MemorySaver()
        return workflow.compile(checkpointer=checkpointer)

    def _extract_research_node(self, state: OutlineGraphState) -> OutlineGraphState:
        """Extract and process research materials into a summary."""
        self.logger.info("Extracting research materials")
        
        research_materials = state.get("research_materials", [])
        
        # Prepare research summary (use up to 5 items)
        if research_materials:
            research_summary = "\n".join([
                f"- {item.get('content', '')} [Source: {item.get('url', 'N/A')}]" 
                for item in research_materials[:5]
            ])
        else:
            research_summary = "No research available."
        
        state["research_summary"] = research_summary
        self.logger.info(f"Extracted {len(research_materials[:5])} research items")
        
        return state

    def _generate_outline_node(self, state: OutlineGraphState) -> OutlineGraphState:
        """Generate outline by calling Gemini API."""
        self.logger.info(f"Generating outline for: {state.get('selected_refined_topic')}")
        
        topic = state.get("selected_refined_topic", "Unknown Topic")
        tone = state.get("tone", "professional")
        research_summary = state.get("research_summary", "No research available.")
        
        prompt = f"""
        Create a compelling podcast episode outline based on the research below.

        TOPIC: {topic}
        TONE: {tone}

        RESEARCH SUMMARY:
        {research_summary}

        Create a structured outline with:
        1. INTRODUCTION: Hook the listener and introduce the topic
        2. MAIN SECTIONS: 3 main talking points with sub-points
        3. CONCLUSION: Summarize key takeaways and provide a call-to-action

        Format the response as JSON with:
        - "title": engaging episode title
        - "introduction": main introduction points
        - "main_sections": list of sections, each with "title" and "key_points"
        - "conclusion": concluding points

        Ensure the outline flows logically and maintains the {tone} tone throughout.
        """
        
        try:
            response = self.llm.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            content = response.text
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            
            outline_data = json.loads(content)
            state["outline_data"] = outline_data
            self.logger.info("Successfully generated outline data")
            
        except Exception as e:
            self.logger.error(f"Error generating outline: {str(e)}")
            # Create minimal valid outline on error
            state["outline_data"] = {
                "title": topic,
                "introduction": "Introduction placeholder",
                "main_sections": [{"title": "Main Topic", "key_points": ["Key point 1"]}],
                "conclusion": "Conclusion placeholder"
            }
        
        return state

    def _validate_outline_node(self, state: OutlineGraphState) -> OutlineGraphState:
        """Validate and convert outline data to EpisodeOutline structure."""
        self.logger.info("Validating outline structure")
        
        outline_data = state.get("outline_data", {})
        topic = state.get("selected_refined_topic", "Unknown Topic")
        
        # Convert to EpisodeOutline structure
        main_sections = []
        for s in outline_data.get("main_sections", []):
            section = {
                "title": s.get("title", "Main Section"),
                "key_points": s.get("key_points", []),
                "estimated_duration": s.get("estimated_duration")
            }
            main_sections.append(section)
        
        episode_outline = {
            "title": outline_data.get("title", topic),
            "introduction": outline_data.get("introduction", ""),
            "main_sections": main_sections,
            "conclusion": outline_data.get("conclusion", ""),
            "total_estimated_duration": outline_data.get("total_estimated_duration")
        }
        
        state["episode_outline"] = episode_outline
        self.logger.info(f"Validated outline with {len(main_sections)} main sections")
        
        return state

    def _state_to_graph_input(self, state: PodcastProductionState) -> OutlineGraphState:
        """Convert PodcastProductionState to graph input format."""
        # Serialize research materials to dicts
        research_materials = [
            material.model_dump() for material in (state.research_materials or [])
        ]
        
        return OutlineGraphState(
            selected_refined_topic=state.selected_refined_topic or "Unknown Topic",
            tone=state.tone,
            research_materials=research_materials,
            research_summary="",
            outline_data={},
            episode_outline={}
        )

    def _graph_output_to_state(
        self, 
        output: Dict[str, Any], 
        original: PodcastProductionState
    ) -> PodcastProductionState:
        """Merge graph output back into PodcastProductionState."""
        # Extract the episode_outline from graph output
        episode_outline_dict = output.get("episode_outline", {})
        
        if episode_outline_dict:
            # Convert main_sections dicts to Section objects
            main_sections = [
                Section(**section) for section in episode_outline_dict.get("main_sections", [])
            ]
            
            # Handle introduction and conclusion - convert dict/list to string if needed
            introduction = episode_outline_dict.get("introduction", "")
            if isinstance(introduction, dict):
                # If it's a dict, extract the text content (e.g., 'hook' field)
                introduction = introduction.get("hook", "") or introduction.get("text", "") or str(introduction)
            elif isinstance(introduction, list):
                # If it's a list, join the items
                introduction = "\n".join(str(item) for item in introduction)
            
            conclusion = episode_outline_dict.get("conclusion", "")
            if isinstance(conclusion, dict):
                # If it's a dict, extract the text content (e.g., 'summary' field)
                conclusion = conclusion.get("summary", "") or conclusion.get("text", "") or str(conclusion)
            elif isinstance(conclusion, list):
                # If it's a list, join the items
                conclusion = "\n".join(str(item) for item in conclusion)
            
            # Create EpisodeOutline object
            episode_outline = EpisodeOutline(
                title=episode_outline_dict.get("title", original.selected_refined_topic),
                introduction=introduction,
                main_sections=main_sections,
                conclusion=conclusion,
                total_estimated_duration=episode_outline_dict.get("total_estimated_duration")
            )
            
            # Update the original state
            original.episode_outline = episode_outline
            original.update_timestamp()
        
        # Validate state before returning
        try:
            original.model_validate(original.model_dump())
        except Exception as e:
            self.logger.error(f"State validation failed: {str(e)}")
            # Ensure minimal valid outline if validation fails
            if not original.episode_outline:
                original.episode_outline = EpisodeOutline(
                    title=original.selected_refined_topic or "Untitled",
                    introduction="Introduction placeholder",
                    main_sections=[Section(title="Main Topic", key_points=["Key point"])],
                    conclusion="Conclusion placeholder"
                )
        
        return original

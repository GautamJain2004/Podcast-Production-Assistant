import json
from agents.base_adk_agent import BaseADKAgent
from google.genai import Client
from schemas.state_models import PodcastProductionState
from config.settings import get_gemini_model

# No external tools needed here; kept as-is but imports adjusted for consistency

class TopicRefinementAgent(BaseADKAgent):
    """Agent that refines a broad topic into specific, compelling angles."""

    def __init__(self, gemini_client: Client):
        super().__init__(
            name="TopicRefinementAgent",
            description="Refines broad podcast topics into specific, engaging angles",
            gemini_client=gemini_client
        )

    def execute(self, state: PodcastProductionState) -> PodcastProductionState:
        """
        Execute topic refinement on the given state.
        
        Args:
            state: Current podcast production state
            
        Returns:
            Updated state with refined topic angles and selected topic
        """
        self.logger.info(f"Refining topic: {state.initial_topic}")

        prompt = f"""
        You are a podcast content strategist. Your task is to take a broad topic and generate 3 specific, compelling angles that would make for an engaging podcast episode.

        Original Topic: {state.initial_topic}
        Desired Tone: {state.tone}

        Generate 3 specific episode angles that are:
        1. Focused and actionable
        2. Relevant and timely
        3. Engaging for listeners
        4. Aligned with the {state.tone} tone

        Format your response as a JSON object with:
        - "angles": list of angle descriptions (3 items)
        - "recommended_angle": the most promising angle for a podcast

        Be specific and avoid vague topics.
        """

        try:
            model_name = get_gemini_model()
            response = self.gemini_client.models.generate_content(
                model=model_name,
                contents=prompt
            )

            # Parse the response to extract angles
            content = response.text
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]

            refinement_data = json.loads(content)

            # Update state with proper schema
            angles = refinement_data.get("angles", [])
            recommended = refinement_data.get("recommended_angle", state.initial_topic)
            
            # Extract title strings from angles if they're dicts
            state.topic_angles = [
                angle.get("title", str(angle)) if isinstance(angle, dict) else str(angle)
                for angle in angles
            ]
            
            # Extract title from recommended angle if it's a dict
            if isinstance(recommended, dict):
                state.selected_refined_topic = recommended.get("title", str(recommended))
            else:
                state.selected_refined_topic = str(recommended)

            self.logger.info(f"Generated {len(state.topic_angles)} angles, selected: {state.selected_refined_topic}")

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response: {str(e)}")
            # Fallback to using the initial topic
            state.topic_angles = [state.initial_topic]
            state.selected_refined_topic = state.initial_topic
            self.logger.warning("Using fallback values due to JSON parsing error")
            
        except Exception as e:
            self.logger.error(f"Error in topic refinement: {str(e)}")
            # Ensure state has valid values even on error
            state.topic_angles = [state.initial_topic]
            state.selected_refined_topic = state.initial_topic
            self.logger.warning("Using fallback values due to execution error")

        # Validate state before returning
        try:
            state.model_validate(state.model_dump())
        except Exception as e:
            self.logger.error(f"State validation failed: {str(e)}")
            # Ensure minimal valid state
            if not state.topic_angles:
                state.topic_angles = [state.initial_topic]
            if not state.selected_refined_topic:
                state.selected_refined_topic = state.initial_topic

        # Update timestamp before returning
        state.update_timestamp()
        return state

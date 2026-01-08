from agents.base_adk_agent import BaseADKAgent
from google.genai import Client
from schemas.state_models import PodcastProductionState
from config.settings import get_gemini_client, get_gemini_model
import logging

class ShowNotesSpecialistAgent(BaseADKAgent):
    """Agent that creates comprehensive show notes with all sources."""

    def __init__(self, gemini_client: Client = None):
        if gemini_client is None:
            gemini_client = get_gemini_client()
        super().__init__(
            name="ShowNotesSpecialistAgent",
            description="Creates detailed show notes with timestamps and source links",
            gemini_client=gemini_client
        )

    def execute(self, state: PodcastProductionState) -> PodcastProductionState:
        self.logger.info("Generating show notes")

        prompt = f"""
        Create comprehensive show notes for this podcast episode.

        EPISODE TITLE: {getattr(state.episode_outline, 'title', state.selected_refined_topic)}
        FULL SCRIPT: {state.final_script}
        ALL SOURCES: {state.all_sources}

        Create show notes that include:
        1. Brief episode summary
        2. Key topics covered (with approximate timestamps if possible)
        3. All relevant links and resources mentioned
        4. Key takeaways
        5. Call to action (subscribe, follow, etc.)

        Format the show notes in Markdown and make sure ALL source URLs are included.
        Group similar links together and provide context for each.

        Return only the markdown content.
        """

        try:
            model_name = get_gemini_model()
            response = self.gemini_client.models.generate_content(
                model=model_name,
                contents=prompt
            )

            # Update state
            state.show_notes = response.text

            self.logger.info(f"Show notes generated successfully ({len(state.show_notes)} characters)")

        except Exception as e:
            self.logger.error(f"Error generating show notes: {str(e)}")
            state.show_notes = f"# Show Notes\n\nPlaceholder for {getattr(state.episode_outline, 'title', state.selected_refined_topic)}"
            raise

        return state

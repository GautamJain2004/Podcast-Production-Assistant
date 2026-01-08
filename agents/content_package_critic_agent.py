from agents.base_adk_agent import BaseADKAgent
from google.genai import Client
from schemas.state_models import PodcastProductionState, QualityReport
from config.settings import get_gemini_client, get_gemini_model
from tools.mcp_client import execute_tool_sync
import json
import logging

class ContentPackageCriticAgent(BaseADKAgent):
    """Final agent that reviews the complete content package for quality and consistency."""

    def __init__(self, gemini_client: Client = None):
        if gemini_client is None:
            gemini_client = get_gemini_client()
        super().__init__(
            name="ContentPackageCriticAgent",
            description="Performs final quality check on all podcast content assets",
            gemini_client=gemini_client
        )

    def execute(self, state: PodcastProductionState) -> PodcastProductionState:
        self.logger.info("Performing final quality check")

        # Use audio duration tool to estimate length (via MCP)
        try:
            duration_result = execute_tool_sync("audio_duration_calculator", {"script_text": state.final_script})
            estimated_duration = round(float(duration_result.get("duration_minutes", 0.0)), 1) if isinstance(duration_result, dict) else float(duration_result or 0.0)
        except Exception as e:
            self.logger.warning(f"Audio duration tool failed, falling back to simple estimate: {e}")
            word_count = len(state.final_script.split() if state.final_script else [])
            estimated_duration = round(word_count / 150, 1)

        state.estimated_duration_min = estimated_duration

        prompt = f"""
        Perform a comprehensive quality check on this complete podcast content package.

        EPISODE: {getattr(state.episode_outline, 'title', state.selected_refined_topic)}
        TONE: {state.tone}
        ESTIMATED DURATION: {estimated_duration} minutes

        COMPONENTS TO REVIEW:
        1. SCRIPT: {state.final_script[:1000]}... [truncated]
        2. SHOW NOTES: {state.show_notes[:1000]}... [truncated]
        3. SOCIAL POSTS: {state.social_posts}
        4. FACT CHECK REPORT: {getattr(state, 'fact_check_report', None)}

        Check for:
        - Consistency in tone and messaging across all assets
        - Factual accuracy based on the fact-check report
        - Engagement and appeal of social media posts
        - Completeness of show notes and sources
        - Overall coherence and quality

        Provide a final review with:
        - "overall_score": number from 1-10
        - "strengths": list of strengths
        - "improvements": list of areas for improvement
        - "recommendations": list of specific recommendations

        Return as JSON.
        """

        try:
            model_name = get_gemini_model()
            response = self.gemini_client.models.generate_content(
                model=model_name,
                contents=prompt
            )

            content = response.text
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]

            quality_data = json.loads(content)

            # Create proper QualityReport object
            state.quality_report = QualityReport(
                overall_score=quality_data.get("overall_score", 7),
                strengths=quality_data.get("strengths", []),
                improvements=quality_data.get("improvements", []),
                recommendations=quality_data.get("recommendations", [])
            )

            self.logger.info(f"Quality check complete. Score: {state.quality_report.overall_score}/10")

        except Exception as e:
            self.logger.error(f"Error in quality check: {str(e)}")
            state.quality_report = QualityReport(
                overall_score=5,
                strengths=["Basic structure complete"],
                improvements=["Quality check failed"],
                recommendations=["Review manually"]
            )
            raise

        return state

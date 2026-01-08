# utils/state_helpers.py
import logging
from typing import Dict, Any
from schemas.state_models import PodcastProductionState
from utils.pydantic_compat import model_to_dict

class StateHelpers:
    """
    Utility functions for working with and validating the podcast production state.
    """

    def __init__(self):
        self.logger = logging.getLogger("podcast_production.state_helpers")

    def validate_state_progression(self, state: PodcastProductionState, expected_stage: str) -> bool:
        """
        Validate that the state has progressed to the expected stage.
        Returns True if valid, False otherwise.
        """
        stage_validators = {
            "refinement": self._validate_refinement_stage,
            "research": self._validate_research_stage,
            "outline": self._validate_outline_stage,
            "script": self._validate_script_stage,
            "validation": self._validate_validation_stage,
            "show_notes": self._validate_show_notes_stage,
            "social_media": self._validate_social_media_stage,
            "complete": self._validate_complete_stage
        }

        validator = stage_validators.get(expected_stage)
        if not validator:
            self.logger.warning(f"Unknown stage validator: {expected_stage}")
            return True  # Don't block unknown stages

        return validator(state)

    def _validate_refinement_stage(self, state: PodcastProductionState) -> bool:
        if not state.selected_refined_topic or state.selected_refined_topic == state.initial_topic:
            self.logger.warning("Topic refinement may not have occurred properly")
            return False
        return True

    def _validate_research_stage(self, state: PodcastProductionState) -> bool:
        if not state.research_materials:
            self.logger.error("No research materials found")
            return False

        if len(state.research_materials) < 2:
            self.logger.warning("Very few research materials found")

        return True

    def _validate_outline_stage(self, state: PodcastProductionState) -> bool:
        if not state.episode_outline:
            self.logger.error("No episode outline found")
            return False

        try:
            main_sections = state.episode_outline.main_sections
            if not main_sections:
                self.logger.error("Episode outline has no main sections")
                return False
        except Exception:
            self.logger.error("Episode outline structure invalid")
            return False

        return True

    def _validate_script_stage(self, state: PodcastProductionState) -> bool:
        if not state.final_script or len(state.final_script) < 100:
            self.logger.error("Script is too short or missing")
            return False
        return True

    def _validate_validation_stage(self, state: PodcastProductionState) -> bool:
        if not state.fact_check_report:
            self.logger.warning("No fact-check report found")
            return True  # Not critical, just warning
        return True

    def _validate_show_notes_stage(self, state: PodcastProductionState) -> bool:
        if not state.show_notes or len(state.show_notes) < 50:
            self.logger.error("Show notes are too short or missing")
            return False
        return True

    def _validate_social_media_stage(self, state: PodcastProductionState) -> bool:
        if not state.social_posts:
            self.logger.error("No social media posts found")
            return False

        if not any(len(posts) > 0 for posts in state.social_posts.values()):
            self.logger.error("Social media posts are empty")
            return False

        return True

    def _validate_complete_stage(self, state: PodcastProductionState) -> bool:
        checks = [
            self._validate_script_stage(state),
            self._validate_show_notes_stage(state),
            self._validate_social_media_stage(state)
        ]
        return all(checks)

    def get_state_summary(self, state: PodcastProductionState) -> Dict[str, Any]:
        """Get a summary of the current state for logging and debugging."""
        try:
            state_dict = model_to_dict(state)
        except Exception:
            state_dict = {}

        return {
            "topic": state_dict.get("initial_topic", getattr(state, "initial_topic", None)),
            "refined_topic": state_dict.get("selected_refined_topic", getattr(state, "selected_refined_topic", None)),
            "tone": state_dict.get("tone", getattr(state, "tone", None)),
            "research_items": len(state.research_materials) if state.research_materials else 0,
            "sources": len(state.all_sources) if state.all_sources else 0,
            "has_outline": bool(state.episode_outline),
            "script_length": len(state.final_script) if state.final_script else 0,
            "has_show_notes": bool(state.show_notes),
            "has_social_posts": bool(state.social_posts),
            "fact_check_claims": getattr(getattr(state, "fact_check_report", None), "claims_checked", 0),
            "estimated_duration": getattr(state, 'estimated_duration_min', None),
            "quality_score": getattr(getattr(state, "quality_report", None), "overall_score", None)
        }

    def create_initial_state(self, topic: str, tone: str = "conversational") -> PodcastProductionState:
        """Create a properly initialized state object."""
        from schemas.state_models import PodcastProductionState as PPS
        return PPS(
            initial_topic=topic,
            tone=tone,
            topic_angles=[],
            selected_refined_topic=topic,
            research_materials=[],
            all_sources=[],
            final_script="",
            show_notes="",
            social_posts={},
            estimated_duration_min=0.0
        )

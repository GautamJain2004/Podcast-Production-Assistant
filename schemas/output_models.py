# schemas/output_models.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from .state_models import ResearchMaterial, FactCheckReport, QualityReport

class SocialMediaPosts(BaseModel):
    """Structured model for social media posts."""
    twitter: List[str] = Field(default_factory=list)
    linkedin: List[str] = Field(default_factory=list)
    instagram: List[str] = Field(default_factory=list)
    facebook: List[str] = Field(default_factory=list)
    youtube: List[str] = Field(default_factory=list)

class Metadata(BaseModel):
    """Metadata for the podcast episode."""
    topic: str = Field(..., description="Original topic")
    refined_topic: str = Field(..., description="Refined specific topic")
    tone: str = Field(..., description="Content tone")
    estimated_duration_min: float = Field(..., description="Estimated duration")
    word_count: int = Field(..., description="Script word count")
    generated_at: datetime = Field(default_factory=datetime.now)
    version: str = Field(default="1.0")

class PodcastContentPackage(BaseModel):
    """
    Comprehensive structured output model for the final podcast content package.
    """

    metadata: Metadata = Field(...)
    script: str = Field(...)
    show_notes: str = Field(...)
    social_media_posts: SocialMediaPosts = Field(default_factory=SocialMediaPosts)
    research_materials: List[ResearchMaterial] = Field(default_factory=list)
    all_sources: List[str] = Field(default_factory=list)
    citations_data: Optional[Dict[str, Any]] = Field(None, description="Citation tracking data")
    fact_check_report: Optional[FactCheckReport] = Field(None)
    quality_report: Optional[QualityReport] = Field(None)
    topic_angles: List[str] = Field(default_factory=list)
    content_stats: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_state(cls, state: "PodcastProductionState") -> "PodcastContentPackage":
        """Create a content package from the production state."""
        word_count = len((state.final_script or "").split())
        metadata = Metadata(
            topic=state.initial_topic,
            refined_topic=state.selected_refined_topic or state.initial_topic,
            tone=state.tone,
            estimated_duration_min=state.estimated_duration_min or 0.0,
            word_count=word_count,
            generated_at=datetime.now()
        )

        social_posts = SocialMediaPosts(
            twitter=state.social_posts.get("twitter", []) if state.social_posts else [],
            linkedin=state.social_posts.get("linkedin", []) if state.social_posts else [],
            instagram=state.social_posts.get("instagram", []) if state.social_posts else [],
            facebook=state.social_posts.get("facebook", []) if state.social_posts else [],
            youtube=state.social_posts.get("youtube", []) if state.social_posts else []
        )

        return cls(
            metadata=metadata,
            script=state.final_script or "",
            show_notes=state.show_notes or "",
            social_media_posts=social_posts,
            research_materials=state.research_materials or [],
            all_sources=state.all_sources or [],
            citations_data=state.citations_data if hasattr(state, "citations_data") else None,
            fact_check_report=state.fact_check_report,
            quality_report=state.quality_report,
            topic_angles=state.topic_angles or [],
            content_stats=state.get_content_stats() if hasattr(state, "get_content_stats") else {}
        )

    def to_markdown_files(self) -> Dict[str, str]:
        """Return file contents for script and show notes (keys are filenames)."""
        files: Dict[str, str] = {}

        topic = self.metadata.refined_topic or self.metadata.topic or "untitled"
        generated_at = self.metadata.generated_at.strftime("%Y-%m-%d %H:%M")

        files["script.md"] = f"# {topic}\n\n## Podcast Script\n\n{self.script}\n\n---\n*Generated on {generated_at}*\n*Estimated duration: {self.metadata.estimated_duration_min} minutes*\n"

        files["show_notes.md"] = f"# Show Notes: {topic}\n\n## Episode Summary\n\n{self.show_notes}\n\n## Sources & References\n\n" + ("\n".join([f"{i+1}. {s}" for i, s in enumerate(self.all_sources)]) if self.all_sources else "No sources referenced.") + f"\n\n---\n*Quality Score: {self.quality_report.overall_score if self.quality_report else 'N/A'}/10*\n"

        return files

    def to_consolidated_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict of the package (uses model_dump when possible)."""
        return self.model_dump(mode="json")

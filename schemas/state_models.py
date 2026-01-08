# schemas/state_models.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime

class ResearchMaterial(BaseModel):
    """Model for individual research items gathered by the Topic Researcher Agent."""
    query: str = Field(..., description="Search query used to find this material")
    title: str = Field(..., description="Title of the research result")
    snippet: str = Field(..., description="Short snippet or summary")
    url: str = Field(..., description="Source URL")
    content: str = Field(..., description="Processed key points and insights")
    source: str = Field(default="web", description="Source type (web, youtube, arxiv, pubmed)")
    citation_id: Optional[str] = Field(None, description="Unique citation identifier")

class Section(BaseModel):
    """Model for individual sections in the podcast outline."""
    title: str = Field(..., description="Section title")
    key_points: List[str] = Field(default_factory=list, description="List of key points for this section")
    estimated_duration: Optional[float] = Field(None, description="Estimated duration in minutes")

class EpisodeOutline(BaseModel):
    """Model for the structured podcast episode outline."""
    title: str = Field(..., description="Episode title")
    introduction: str = Field(..., description="Introduction content")
    main_sections: List[Section] = Field(default_factory=list, description="Main content sections")
    conclusion: str = Field(..., description="Conclusion content")
    total_estimated_duration: Optional[float] = Field(None, description="Total estimated duration")

class FactCheckItem(BaseModel):
    """Model for individual fact-check results."""
    claim: str = Field(..., description="The factual claim being verified")
    verified: bool = Field(..., description="Whether the claim was verified")
    confidence: str = Field(..., description="Confidence level: high/medium/low")
    supporting_evidence: Optional[str] = Field(None, description="Evidence supporting verification")
    source_urls: List[str] = Field(default_factory=list, description="URLs supporting the claim")

class FactCheckReport(BaseModel):
    """Model for the comprehensive fact-checking report."""
    claims_checked: int = Field(0, description="Total number of claims checked")
    verified_claims: int = Field(0, description="Number of verified claims")
    verification_rate: float = Field(0.0, description="Percentage of verified claims")
    details: List[FactCheckItem] = Field(default_factory=list, description="Detailed fact-check results")

    @model_validator(mode="before")
    def compute_verification_rate(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure verification_rate is calculated if claims_checked and verified_claims are provided.
        This runs before model construction so omitted verification_rate is filled in.
        """
        claims = v.get("claims_checked", 0)
        verified = v.get("verified_claims", 0)
        if "verification_rate" not in v:
            v["verification_rate"] = round((verified / claims) * 100, 1) if claims else 0.0
        return v

class QualityReport(BaseModel):
    """Model for the final quality assessment report."""
    overall_score: float = Field(..., ge=0, le=10, description="Overall quality score (0-10)")
    strengths: List[str] = Field(default_factory=list, description="List of strengths identified")
    improvements: List[str] = Field(default_factory=list, description="List of areas for improvement")
    recommendations: List[str] = Field(default_factory=list, description="Specific recommendations")
    consistency_score: Optional[float] = Field(None, description="Consistency score across assets")
    factual_accuracy_score: Optional[float] = Field(None, description="Factual accuracy score")

class PodcastProductionState(BaseModel):
    """
    Main state model shared between all agents in the podcast production workflow.
    This state accumulates all intermediate outputs and final results.
    """
    # Input parameters
    initial_topic: str = Field(..., description="Original topic provided by user")
    tone: str = Field(default="professional", description="Content tone/style")

    # Topic Refinement outputs
    topic_angles: List[str] = Field(default_factory=list, description="Generated topic angles")
    selected_refined_topic: str = Field("", description="Selected specific topic angle")

    # Research outputs
    research_materials: List[ResearchMaterial] = Field(default_factory=list, description="Gathered research materials")
    all_sources: List[str] = Field(default_factory=list, description="All source URLs collected")

    # Outline outputs (strongly typed)
    episode_outline: Optional[EpisodeOutline] = Field(None, description="Structured episode outline")

    # Script outputs
    final_script: str = Field("", description="Final podcast script")

    # Fact-checking outputs
    fact_check_report: Optional[FactCheckReport] = Field(None, description="Fact-checking results")

    # Show notes outputs
    show_notes: str = Field("", description="Formatted show notes")

    # Social media outputs
    social_posts: Dict[str, List[str]] = Field(default_factory=dict, description="Social media posts by platform")

    # Final review outputs
    quality_report: Optional[QualityReport] = Field(None, description="Final quality assessment")
    estimated_duration_min: float = Field(0.0, description="Estimated audio duration in minutes")

    # Citation tracking
    citations_data: Optional[Dict[str, Any]] = Field(None, description="Citation manager data")
    used_citation_ids: List[str] = Field(default_factory=list, description="Citation IDs actually used in script")

    # System metadata
    created_at: datetime = Field(default_factory=datetime.now, description="State creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()

    def get_research_summary(self) -> str:
        """Get a summary of research materials (first 5 items)."""
        if not self.research_materials:
            return "No research materials available"

        parts = []
        for i, material in enumerate(self.research_materials[:5], 1):
            parts.append(f"{i}. {material.title}\n   Source: {material.url}\n   Key: {material.content[:120]}...\n")
        return "Research Summary:\n\n" + "\n".join(parts)

    def get_content_stats(self) -> Dict[str, Any]:
        """Get statistics about the generated content."""
        stats: Dict[str, Any] = {
            "research_items": len(self.research_materials),
            "sources_count": len(self.all_sources),
            "script_length_chars": len(self.final_script or ""),
            "show_notes_length_chars": len(self.show_notes or ""),
            "social_posts_count": sum(len(posts) for posts in self.social_posts.values()) if self.social_posts else 0,
            "estimated_duration_min": self.estimated_duration_min
        }

        if self.episode_outline:
            stats["outline_sections"] = len(self.episode_outline.main_sections or [])

        if self.fact_check_report:
            stats["claims_checked"] = self.fact_check_report.claims_checked
            stats["verified_claims"] = self.fact_check_report.verified_claims
            stats["verification_rate"] = self.fact_check_report.verification_rate

        return stats

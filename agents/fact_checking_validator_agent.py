from agents.base_adk_agent import BaseADKAgent
from google.genai import Client
from schemas.state_models import PodcastProductionState, FactCheckReport, FactCheckItem
from config.settings import get_gemini_client, get_gemini_model
from tools.mcp_client import execute_tool_sync
import json
import logging

class FactCheckingValidatorAgent(BaseADKAgent):
    """Agent that validates facts in the script against research sources."""

    def __init__(self, gemini_client: Client = None):
        if gemini_client is None:
            gemini_client = get_gemini_client()
        super().__init__(
            name="FactCheckingValidatorAgent",
            description="Validates factual claims in podcast scripts against sources",
            gemini_client=gemini_client
        )

    def execute(self, state: PodcastProductionState) -> PodcastProductionState:
        self.logger.info("Validating facts in the script")

        prompt = f"""
        Analyze this podcast script and identify the 3 MOST IMPORTANT factual claims that need verification.

        SCRIPT:
        {state.final_script}

        EXISTING SOURCES:
        {state.all_sources}

        SELECTION CRITERIA - Prioritize claims that are:
        1. **Specific and measurable** (contains numbers, percentages, statistics, or concrete data)
        2. **Central to the episode's argument** (key points, not minor details)
        3. **Potentially controversial or surprising** (claims that listeners might question)
        4. **Verifiable** (can be checked against reliable sources, not opinions or subjective statements)
        
        AVOID selecting:
        - Vague or general statements ("X is popular", "Y is growing")
        - Obvious facts that don't need verification ("The sky is blue")
        - Subjective opinions or feelings ("seems like", "feels like")
        - Design intentions or purposes ("designed for", "meant to")
        
        EXAMPLES OF GOOD CLAIMS:
        ✅ "AI diagnostic tools have achieved 95% accuracy in detecting lung cancer from X-rays"
        ✅ "Studies show that 60% of physicians report burnout due to administrative tasks"
        ✅ "The FDA approved 3 AI-powered medical devices in 2024"
        
        EXAMPLES OF BAD CLAIMS:
        ❌ "AI is becoming more popular in healthcare" (too vague)
        ❌ "Many doctors feel overwhelmed" (subjective, no data)
        ❌ "The system is designed to help patients" (design intent, not fact)

        Return a JSON list where each item has:
        - "claim": the specific factual claim from the script (quote it exactly)
        - "needs_verification": boolean indicating if this needs external verification
        - "confidence": "high"/"medium"/"low" based on existing sources
        
        CONFIDENCE GUIDELINES:
        - "high": Claim is directly supported by credible sources in the existing research
        - "medium": Claim is reasonable and generally supported, or partially supported by sources
        - "low": Claim lacks supporting evidence or contradicts available information
        
        Be balanced in your assessment - if a claim is reasonable and has some supporting context,
        assign "medium" confidence rather than defaulting to "low".
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

            claims_analysis = json.loads(content)

            # Build FactCheckReport details
            details = []
            verified_count = 0
            for item in claims_analysis:
                claim = item.get("claim", "")
                confidence = item.get("confidence", "low")
                needs_verification = bool(item.get("needs_verification", True))

                # Optionally attempt a web search to fetch supporting URLs for this claim
                supporting_urls = []
                if needs_verification:
                    try:
                        results = execute_tool_sync("web_search", {"query": claim, "num_results": 3})
                        for r in (results or [])[:3]:
                            url = r.get("url") or r.get("link")
                            if url:
                                supporting_urls.append(url)
                    except Exception as e:
                        self.logger.debug(f"Web search for claim failed: {e}")

                # Mark as verified if confidence is medium or high
                is_verified = confidence in ["high", "medium"]
                if is_verified:
                    verified_count += 1

                details.append(FactCheckItem(
                    claim=claim,
                    verified=is_verified,
                    confidence=confidence,
                    supporting_evidence=None,
                    source_urls=supporting_urls
                ))

            state.fact_check_report = FactCheckReport(
                claims_checked=len(details),
                verified_claims=verified_count,
                details=details
            )

            self.logger.info(f"Fact-checking complete: {verified_count}/{len(details)} high-confidence claims")

        except Exception as e:
            self.logger.error(f"Error in fact-checking: {str(e)}")
            state.fact_check_report = FactCheckReport(
                claims_checked=0,
                verified_claims=0,
                details=[]
            )
            raise

        return state

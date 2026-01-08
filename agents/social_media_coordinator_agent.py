from agents.base_adk_agent import BaseADKAgent
from google.genai import Client
from schemas.state_models import PodcastProductionState
from config.settings import get_gemini_client, get_gemini_model
import json
import logging

class SocialMediaCoordinatorAgent(BaseADKAgent):
    """Agent that creates social media promotional content."""

    def __init__(self, gemini_client: Client = None):
        if gemini_client is None:
            gemini_client = get_gemini_client()
        super().__init__(
            name="SocialMediaCoordinatorAgent",
            description="Creates engaging social media posts for podcast promotion",
            gemini_client=gemini_client
        )

    def execute(self, state: PodcastProductionState) -> PodcastProductionState:
        self.logger.info("Creating social media posts")

        topics = [s.title for s in (state.episode_outline.main_sections or [])] if getattr(state, "episode_outline", None) else []

        prompt = f"""
        Create social media promotional content for this podcast episode.

        EPISODE TITLE: {getattr(state.episode_outline, 'title', state.selected_refined_topic)}
        KEY TOPICS: {topics}
        TONE: {state.tone}

        Create 3 different social media posts:
        1. Teaser post (1-2 days before episode release)
        2. Launch announcement (day of release)
        3. Key insight highlight (quote or interesting fact)

        For each post, create variations for:
        - Twitter/X (280 characters max)
        - LinkedIn (more professional tone)

        Include relevant hashtags and emojis where appropriate.

        Return as JSON with platform as keys and posts as arrays.
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

            social_posts = json.loads(content)

            # Extract text content from posts if they're dicts
            cleaned_posts = {}
            for platform, posts in social_posts.items():
                cleaned_posts[platform] = []
                for post in posts:
                    if isinstance(post, dict):
                        # Extract the 'content' or 'text' field from dict
                        text = post.get('content', '') or post.get('text', '') or str(post)
                        cleaned_posts[platform].append(text)
                    else:
                        cleaned_posts[platform].append(str(post))
            
            # Update state
            state.social_posts = cleaned_posts

            total_posts = sum(len(posts) for posts in cleaned_posts.values())
            self.logger.info(f"Generated {total_posts} social media posts across {len(cleaned_posts)} platforms")

        except Exception as e:
            self.logger.error(f"Error creating social media posts: {str(e)}")
            state.social_posts = {"twitter": ["Post placeholder"], "linkedin": ["Post placeholder"]}
            raise

        return state

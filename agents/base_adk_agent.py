# agents/base_adk_agent.py
"""Base class for Google ADK agents in the podcast production system."""

from google.adk.agents import Agent as GoogleADKAgent
from google.genai import Client
from schemas.state_models import PodcastProductionState
from pydantic import ConfigDict
import logging


class BaseADKAgent(GoogleADKAgent):
    """
    Base class for Google ADK agents in the podcast production system.
    
    This class provides a common interface for all Google ADK-based agents,
    ensuring they can work with PodcastProductionState and integrate with
    the A2A communication system.
    """
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, name: str, description: str, gemini_client: Client):
        """
        Initialize the base ADK agent.
        
        Args:
            name: Agent name for identification
            description: Agent description for documentation
            gemini_client: Configured Google Gemini client for LLM calls
        """
        super().__init__(name=name, description=description)
        object.__setattr__(self, 'gemini_client', gemini_client)
        object.__setattr__(self, 'logger', logging.getLogger(f"agents.{name}"))
    
    def execute(self, state: PodcastProductionState) -> PodcastProductionState:
        """
        Execute the agent's logic on the given state.
        
        This method should be overridden by subclasses to implement
        specific agent behavior.
        
        Args:
            state: Current podcast production state
            
        Returns:
            Updated podcast production state
            
        Raises:
            NotImplementedError: If not overridden by subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement the execute method"
        )

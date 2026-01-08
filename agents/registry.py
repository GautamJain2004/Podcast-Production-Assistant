"""
AgentRegistry: Unified registry and factory for ADK and LangGraph agents.

This module provides a centralized registry for managing both Google ADK and
LangGraph agents, along with their wrappers for A2A communication.
"""

from typing import Dict, List, Optional, Any
import logging

from google.genai import Client

from .base_adk_agent import BaseADKAgent
from .base_langgraph_agent import BaseLangGraphAgent
from adk_adapter.adapter import ADKAgentWrapper
from langgraph_adapter.adapter import LangGraphAgentWrapper

logger = logging.getLogger("agents.registry")


class AgentRegistry:
    """
    Unified registry for managing ADK and LangGraph agents.
    
    This class provides a centralized way to:
    - Register agents of different types (ADK, LangGraph)
    - Build all agents with proper initialization
    - Create wrapped versions for A2A communication
    - Maintain pipeline ordering for workflow execution
    """
    
    def __init__(self, pipeline_order: List[str], gemini_client: Client, callback: Optional[Any] = None):
        """
        Initialize the agent registry.
        
        Args:
            pipeline_order: Ordered list of agent names defining execution sequence
            gemini_client: Configured Google Gemini client for ADK agents
            callback: Optional callback instance for monitoring agent execution
        """
        self.pipeline_order = pipeline_order
        self.gemini_client = gemini_client
        self.callback = callback
        self.logger = logging.getLogger("agents.registry")
        
        # Storage for agent classes and instances
        self._adk_agent_classes: Dict[str, type] = {}
        self._langgraph_agent_classes: Dict[str, type] = {}
        self._agent_instances: Dict[str, Any] = {}
        self._wrapped_agents: Dict[str, Any] = {}
        
        self.logger.info(f"AgentRegistry initialized with pipeline: {pipeline_order}")
    
    def register_adk_agent(self, name: str, agent_class: type) -> None:
        """
        Register a Google ADK agent class.
        
        Args:
            name: Unique identifier for the agent
            agent_class: Agent class (must inherit from BaseADKAgent)
        """
        if not issubclass(agent_class, BaseADKAgent):
            raise TypeError(f"Agent class {agent_class.__name__} must inherit from BaseADKAgent")
        
        self._adk_agent_classes[name] = agent_class
        self.logger.debug(f"Registered ADK agent: {name}")
    
    def register_langgraph_agent(self, name: str, agent_class: type) -> None:
        """
        Register a LangGraph agent class.
        
        Args:
            name: Unique identifier for the agent
            agent_class: Agent class (must inherit from BaseLangGraphAgent)
        """
        if not issubclass(agent_class, BaseLangGraphAgent):
            raise TypeError(f"Agent class {agent_class.__name__} must inherit from BaseLangGraphAgent")
        
        self._langgraph_agent_classes[name] = agent_class
        self.logger.debug(f"Registered LangGraph agent: {name}")
    
    def build_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Build all registered agents and create their wrappers.
        
        This method:
        1. Instantiates all registered agent classes
        2. Creates ADKAgentWrapper for ADK agents
        3. Creates LangGraphAgentWrapper for LangGraph agents
        4. Returns organized dictionary of agents and wrappers
        
        Returns:
            Dictionary with keys:
                - 'agents': Dict mapping agent names to instances
                - 'wrapped_adk': Dict mapping ADK agent names to wrappers
                - 'wrapped_langgraph': Dict mapping LangGraph agent names to wrappers
                - 'all_wrapped': Dict mapping all agent names to wrappers
        """
        self.logger.info("Building all agents...")
        
        # Build ADK agents
        for name, agent_class in self._adk_agent_classes.items():
            try:
                instance = agent_class(gemini_client=self.gemini_client)
                self._agent_instances[name] = instance
                
                # Create wrapper for A2A communication
                wrapper = ADKAgentWrapper(
                    agent_instance=instance,
                    name=name,
                    broker_pipeline=self.pipeline_order,
                    callback=self.callback
                )
                self._wrapped_agents[name] = wrapper
                
                self.logger.info(f"Built ADK agent: {name}")
            except Exception as e:
                self.logger.error(f"Failed to build ADK agent {name}: {e}")
                raise
        
        # Build LangGraph agents
        for name, agent_class in self._langgraph_agent_classes.items():
            try:
                instance = agent_class()
                self._agent_instances[name] = instance
                
                # Create wrapper for A2A communication
                wrapper = LangGraphAgentWrapper(
                    agent_instance=instance,
                    name=name,
                    broker_pipeline=self.pipeline_order,
                    callback=self.callback
                )
                self._wrapped_agents[name] = wrapper
                
                self.logger.info(f"Built LangGraph agent: {name}")
            except Exception as e:
                self.logger.error(f"Failed to build LangGraph agent {name}: {e}")
                raise
        
        # Organize results
        wrapped_adk = {
            name: wrapper for name, wrapper in self._wrapped_agents.items()
            if name in self._adk_agent_classes
        }
        
        wrapped_langgraph = {
            name: wrapper for name, wrapper in self._wrapped_agents.items()
            if name in self._langgraph_agent_classes
        }
        
        self.logger.info(
            f"Built {len(self._agent_instances)} agents: "
            f"{len(wrapped_adk)} ADK, {len(wrapped_langgraph)} LangGraph"
        )
        
        return {
            'agents': self._agent_instances,
            'wrapped_adk': wrapped_adk,
            'wrapped_langgraph': wrapped_langgraph,
            'all_wrapped': self._wrapped_agents
        }
    
    def get_agent(self, name: str) -> Optional[Any]:
        """
        Get an agent instance by name.
        
        Args:
            name: Agent identifier
            
        Returns:
            Agent instance or None if not found
        """
        return self._agent_instances.get(name)
    
    def get_wrapped_agent(self, name: str) -> Optional[Any]:
        """
        Get a wrapped agent by name.
        
        Args:
            name: Agent identifier
            
        Returns:
            Wrapped agent instance or None if not found
        """
        return self._wrapped_agents.get(name)

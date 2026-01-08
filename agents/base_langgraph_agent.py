# agents/base_langgraph_agent.py
"""Base class for LangGraph agents in the podcast production system."""

from langgraph.graph import StateGraph
from schemas.state_models import PodcastProductionState
from typing import Dict, Any
import logging


class BaseLangGraphAgent:
    """
    Base class for LangGraph agents in the podcast production system.
    
    This class provides a common interface for all LangGraph-based agents,
    ensuring they can work with PodcastProductionState and integrate with
    the A2A communication system.
    """
    
    def __init__(self, name: str, description: str):
        """
        Initialize the base LangGraph agent.
        
        Args:
            name: Agent name for identification
            description: Agent description for documentation
        """
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"agents.{name}")
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph state graph for this agent.
        
        This method must be overridden by subclasses to define the
        agent's specific workflow as a state graph.
        
        Returns:
            Compiled StateGraph instance
            
        Raises:
            NotImplementedError: If not overridden by subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement the _build_graph method"
        )
    
    def execute(self, state: PodcastProductionState) -> PodcastProductionState:
        """
        Execute the LangGraph workflow on the given state.
        
        This method converts the PodcastProductionState to a graph-compatible
        format, invokes the graph, and converts the result back to
        PodcastProductionState.
        
        Args:
            state: Current podcast production state
            
        Returns:
            Updated podcast production state
        """
        self.logger.info(f"Executing {self.name} with LangGraph")
        
        # Convert PodcastProductionState to graph-compatible dict
        graph_state = self._state_to_graph_input(state)
        
        # Run the graph with config including thread_id for checkpointer
        try:
            import uuid
            config = {"configurable": {"thread_id": str(uuid.uuid4())}}
            result = self.graph.invoke(graph_state, config=config)
            self.logger.info(f"{self.name} graph execution completed")
        except Exception as e:
            self.logger.error(f"Error executing {self.name} graph: {e}")
            raise
        
        # Convert back to PodcastProductionState
        return self._graph_output_to_state(result, state)
    
    def _state_to_graph_input(self, state: PodcastProductionState) -> Dict[str, Any]:
        """
        Convert PodcastProductionState to graph input format.
        
        By default, this serializes the entire state to a dictionary.
        Subclasses can override this to provide custom conversion logic.
        
        Args:
            state: Current podcast production state
            
        Returns:
            Dictionary representation suitable for graph input
        """
        return state.model_dump()
    
    def _graph_output_to_state(
        self, 
        output: Dict[str, Any], 
        original: PodcastProductionState
    ) -> PodcastProductionState:
        """
        Merge graph output back into PodcastProductionState.
        
        This method takes the graph's output dictionary and merges it
        with the original state, creating a new PodcastProductionState
        with updated fields.
        
        Args:
            output: Dictionary output from graph execution
            original: Original podcast production state
            
        Returns:
            Updated podcast production state
        """
        # Merge original state with graph output
        updated_data = {**original.model_dump(), **output}
        
        # Create new state instance with merged data
        return PodcastProductionState(**updated_data)

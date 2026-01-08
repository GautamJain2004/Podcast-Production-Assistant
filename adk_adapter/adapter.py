"""
ADKAgentWrapper: wraps internal agents and exposes ADK-compatible handlers.
Integrates with the a2a_broker for A2A interoperability with Google ADK agents.
"""

from typing import Any, Dict, Optional
import logging

# Broker helpers
from a2a_broker.broker import get_global_broker

# Use canonical A2A message serialization helpers
from .a2a_message import state_to_message, message_to_state
from schemas.state_models import PodcastProductionState

logger = logging.getLogger("adk_adapter.adapter")
logger.addHandler(logging.NullHandler())


class ADKAgentWrapper:
    """
    Wrap an internal Google ADK agent so it can be called via A2A messages.
    The wrapper will:
      - Accept A2A messages (dict), convert to PodcastProductionState
      - Execute the wrapped agent's .execute(state) method
      - Return A2A message with updated state
      - Publish results to the a2a_broker for cross-framework routing
    
    This wrapper is designed for Google ADK agents that implement the execute(state) pattern.
    """

    def __init__(self, agent_instance: Any, name: Optional[str] = None, broker_pipeline: Optional[list] = None, callback: Optional[Any] = None):
        """
        Initialize the ADK agent wrapper.
        
        Args:
            agent_instance: The Google ADK agent instance to wrap (must have execute method)
            name: Optional name for the agent (defaults to agent's name attribute or class name)
            broker_pipeline: Optional pipeline order for broker auto-forwarding
            callback: Optional callback instance for monitoring agent execution
        """
        self.agent = agent_instance
        self.name = name or getattr(agent_instance, "name", agent_instance.__class__.__name__)
        self.logger = logging.getLogger(f"adk_adapter.{self.name}")
        self.broker = get_global_broker(pipeline_order=broker_pipeline)
        self.callback = callback
        self._register_with_broker = True  # default: register wrapper with broker

    def handle_a2a(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        A2A message handler: receives A2A message dict, runs agent.execute and returns updated message.
        
        This method:
        1. Deserializes the A2A message to PodcastProductionState
        2. Calls the wrapped Google ADK agent's execute(state) method
        3. Serializes the updated state back to an A2A message
        4. Publishes the result to the broker for pipeline routing
        
        Args:
            message: A2A message dict with 'type' and 'payload' fields
            
        Returns:
            Updated A2A message dict with new state, or error message on failure
        """
        try:
            self.logger.info(f"[{self.name}] Received A2A message")
            
            # Deserialize message to state
            state: PodcastProductionState = message_to_state(message)
            self.logger.debug(f"[{self.name}] State deserialized: initial_topic={state.initial_topic}")
            
            # Call on_agent_start callback
            if self.callback and hasattr(self.callback, 'on_agent_start'):
                try:
                    self.callback.on_agent_start(self.agent, state, framework="ADK")
                except Exception as e:
                    self.logger.warning(f"Callback on_agent_start failed: {e}")
            
            # Execute the Google ADK agent
            try:
                new_state = self.agent.execute(state)
            except Exception as agent_error:
                # Call on_agent_error callback
                if self.callback and hasattr(self.callback, 'on_agent_error'):
                    try:
                        self.callback.on_agent_error(self.agent, state, agent_error)
                    except Exception as e:
                        self.logger.warning(f"Callback on_agent_error failed: {e}")
                raise
            
            # Call on_agent_end callback
            if self.callback and hasattr(self.callback, 'on_agent_end'):
                try:
                    self.callback.on_agent_end(self.agent, new_state)
                except Exception as e:
                    self.logger.warning(f"Callback on_agent_end failed: {e}")
            
            # Serialize updated state to message
            out_msg = state_to_message(new_state)
            
            # Determine next topic in pipeline
            next_topic = None
            if isinstance(message, dict) and message.get("next"):
                # Explicit next routing provided
                next_topic = message.get("next")
                self.logger.debug(f"[{self.name}] Using explicit next topic from message: '{next_topic}'")
            elif self.broker.pipeline_order:
                # Use pipeline auto-forwarding
                self.logger.debug(f"[{self.name}] Pipeline order: {self.broker.pipeline_order}")
                try:
                    idx = self.broker.pipeline_order.index(self.name)
                    self.logger.debug(f"[{self.name}] Found self at index {idx}")
                    if idx + 1 < len(self.broker.pipeline_order):
                        next_topic = self.broker.pipeline_order[idx + 1]
                        self.logger.debug(f"[{self.name}] Calculated next topic: '{next_topic}'")
                    else:
                        self.logger.debug(f"[{self.name}] At end of pipeline")
                except ValueError:
                    # Agent not in pipeline
                    self.logger.warning(f"[{self.name}] Not found in pipeline order: {self.broker.pipeline_order}")
            else:
                self.logger.debug(f"[{self.name}] No pipeline order configured on broker")

            # Publish to next topic if determined
            if next_topic:
                try:
                    self.broker.publish_sync(next_topic, out_msg)
                    self.logger.info(f"[{self.name}] Published updated state to next topic '{next_topic}'")
                except Exception as e:
                    self.logger.warning(f"[{self.name}] Broker publish to '{next_topic}' failed: {e}")
            else:
                self.logger.info(f"[{self.name}] No next topic, pipeline complete for this agent")

            return out_msg

        except Exception as e:
            self.logger.exception(f"[{self.name}] Error processing A2A message: {e}")
            return {"type": "error", "payload": {"agent": self.name, "error": str(e)}}


def register_wrappers_with_broker(wrapped_agents: Dict[str, ADKAgentWrapper]) -> None:
    """
    Register Google ADK agent wrappers with the A2A broker.
    Each wrapper subscribes to its named topic and will handle incoming messages.
    
    This enables Google ADK agents to participate in the A2A message-based workflow
    alongside LangGraph agents.
    
    Args:
        wrapped_agents: Dictionary mapping agent names to ADKAgentWrapper instances
    """
    broker = get_global_broker()
    broker.start_background_loop()
    
    for name, wrapper in wrapped_agents.items():
        try:
            # Subscribe wrapper to its named topic
            wrapper.broker.subscribe_sync(name, lambda msg, w=wrapper: w.handle_a2a(msg))
            logger.info(f"Registered Google ADK wrapper '{name}' with broker on topic '{name}'")
        except Exception as e:
            logger.error(f"Failed to register ADK wrapper '{name}' with broker: {e}")
            raise

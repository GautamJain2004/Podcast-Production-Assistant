"""
Entry script to launch Google ADK agents in broker-only mode.
This starts the A2A broker, builds Google ADK agent wrappers, and registers them with the broker.
The agents will listen for A2A messages on their respective topics.
"""

import os
import sys
import logging
import time

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import AgentRegistry, TopicRefinementAgent, TopicResearcherAgent
from config.settings import get_gemini_client
from a2a_broker.broker import get_global_broker

logger = logging.getLogger("adk_adapter.run_adk_app")


def main():
    """
    Main entry point for running Google ADK agents in broker-only mode.
    
    This function:
    1. Configures logging
    2. Defines the agent pipeline order
    3. Starts the A2A broker
    4. Builds Google ADK agent wrappers
    5. Registers wrappers with the broker
    6. Keeps the process running to handle messages
    """
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting Google ADK agents in broker-only mode")
    
    # Define pipeline order for agent execution
    pipeline = [
        "refinement",
        "researcher",
        "outline_architect",
        "script_writer",
        "fact_validator",
        "show_notes_specialist",
        "social_media_coordinator",
        "content_critic"
    ]
    
    # Initialize and start the A2A broker
    logger.info(f"Initializing A2A broker with pipeline: {pipeline}")
    broker = get_global_broker(pipeline_order=pipeline)
    broker.start_background_loop()
    
    # Get Gemini client for ADK agents
    gemini_client = get_gemini_client()
    
    # Create registry and register Google ADK agents
    logger.info("Building Google ADK agent wrappers via AgentRegistry")
    registry = AgentRegistry(pipeline_order=pipeline, gemini_client=gemini_client)
    registry.register_adk_agent("refinement", TopicRefinementAgent)
    registry.register_adk_agent("researcher", TopicResearcherAgent)
    
    # Build agents and get wrappers
    result = registry.build_all()
    wrapped_adk = result['wrapped_adk']
    
    # Register wrappers with broker (subscribes to topics)
    logger.info("Registering Google ADK agent wrappers with broker")
    for name, wrapper in wrapped_adk.items():
        broker.subscribe_sync(name, lambda msg, w=wrapper: w.handle_a2a(msg))
        logger.info(f"Registered ADK agent '{name}' with broker on topic '{name}'")
    
    logger.info(f"Google ADK agents registered and listening on broker topics")
    logger.info("Press Ctrl+C to stop")
    
    # Keep the process running to handle messages
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Google ADK agents")


if __name__ == "__main__":
    main()

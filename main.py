#!/usr/bin/env python3
"""
AI Podcast Production Suite - Main Entry Point (with A2A mode)

Run modes:
  - Default (in-process): runs agents sequentially in this process (legacy behavior)
  - A2A mode (--a2a): publishes initial state to the A2A broker on topic_refinement,
                     waits for the final content_critic message, and writes outputs.

Usage examples:
  python main.py "AI in Healthcare" --tone conversational
  python main.py "AI in Healthcare" --a2a --a2a-timeout 60
"""

import os
import sys
import logging
import time
from typing import Optional, Dict, Any
from threading import Event

# ensure repo root on path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Core imports
from schemas.state_models import PodcastProductionState
from callbacks.logging_callback import PodcastProductionCallback
from utils.file_writer import FileWriter
from utils.state_helpers import StateHelpers

# Agents
from agents import (
    AgentRegistry,
    TopicRefinementAgent,
    TopicResearcherAgent,
    OutlineArchitectAgent,
    ScriptWriterAgent,
    FactCheckingValidatorAgent,
    ShowNotesSpecialistAgent,
    SocialMediaCoordinatorAgent,
    ContentPackageCriticAgent,
)
from agents.enhanced_researcher_agent import EnhancedTopicResearcherAgent

# Pydantic output model
from schemas.output_models import PodcastContentPackage

# ADK / A2A broker helpers (optional)
try:
    from a2a_broker.broker import get_global_broker
    from adk_adapter.a2a_message import state_to_message, message_to_state
    A2A_AVAILABLE = True
except Exception:
    get_global_broker = None  # type: ignore
    state_to_message = None  # type: ignore
    message_to_state = None  # type: ignore
    A2A_AVAILABLE = False

# config/settings helpers
from config.settings import setup_logging, get_settings, setup_environment

logger = logging.getLogger("podcast_production.app")


class PodcastProductionApp:
    """
    Main application class orchestrating the podcast production workflow.
    Supports both in-process and A2A (brokered) execution.
    """

    def __init__(self, log_level: str = "INFO", use_enhanced_research: bool = True, retry_mode: str = "default"):
        self.log_level = log_level
        self.use_enhanced_research = use_enhanced_research
        setup_logging()
        self.logger = logging.getLogger("podcast_production.app")
        self.logger.setLevel(getattr(logging, self.log_level.upper(), logging.INFO))

        # Initialize retry configuration
        from config.retry_config import initialize_retry_config
        initialize_retry_config(retry_mode)
        self.logger.info(f"🔄 Retry mode: {retry_mode}")

        self.initialize_agents()
        self.initialize_utilities()
        self.logger.info("🎙️ AI Podcast Production Suite initialized")
        if use_enhanced_research:
            self.logger.info("✨ Enhanced research enabled (YouTube + Academic papers + Parallel execution)")

    def initialize_agents(self) -> None:
        # Define pipeline order for agent execution
        pipeline_order = [
            "refinement",
            "researcher",
            "outline_architect",
            "script_writer",
            "fact_validator",
            "show_notes_specialist",
            "social_media_coordinator",
            "content_critic"
        ]
        
        # Get Gemini client for ADK agents
        from config.settings import get_gemini_client
        gemini_client = get_gemini_client()
        
        # Create callback for monitoring (will be passed to registry)
        self.callback = PodcastProductionCallback(log_level=self.log_level)
        
        # Create registry and register agents with callback
        self.registry = AgentRegistry(pipeline_order=pipeline_order, gemini_client=gemini_client, callback=self.callback)
        
        # Register ADK agents
        self.registry.register_adk_agent("refinement", TopicRefinementAgent)
        
        # Use enhanced researcher if enabled, otherwise use basic researcher
        if self.use_enhanced_research:
            self.registry.register_adk_agent("researcher", EnhancedTopicResearcherAgent)
        else:
            self.registry.register_adk_agent("researcher", TopicResearcherAgent)
        
        # Register LangGraph agents
        self.registry.register_langgraph_agent("outline_architect", OutlineArchitectAgent)
        self.registry.register_langgraph_agent("script_writer", ScriptWriterAgent)
        
        # Build all agents and get wrappers
        build_result = self.registry.build_all()
        
        # Store agents for in-process mode (backward compatibility)
        self.agents = build_result['agents'].copy()
        
        # Add remaining agents (not yet converted to ADK/LangGraph frameworks)
        # These agents still use the original implementation pattern
        self.agents["fact_validator"] = FactCheckingValidatorAgent()
        self.agents["show_notes_specialist"] = ShowNotesSpecialistAgent()
        self.agents["social_media_coordinator"] = SocialMediaCoordinatorAgent()
        self.agents["content_critic"] = ContentPackageCriticAgent()
        
        # Store wrapped agents for A2A mode
        self.wrapped_agents = build_result['all_wrapped']
        
        self.logger.info(f"Initialized {len(self.agents)} specialized agents via AgentRegistry")
        self.logger.info(f"Created {len(self.wrapped_agents)} wrapped agents for A2A mode")

    def initialize_utilities(self) -> None:
        self.file_writer = FileWriter()
        self.state_helpers = StateHelpers()
        # Callback is now initialized in initialize_agents() to be passed to registry
        self.logger.debug("Utilities initialized")

    def create_initial_state(self, topic: str, tone: str = "conversational") -> PodcastProductionState:
        self.logger.info(f"Creating initial state for topic: '{topic}' with tone: '{tone}'")
        state = self.state_helpers.create_initial_state(topic, tone)
        if not state.initial_topic or not state.tone:
            raise ValueError("Invalid initial state: topic and tone are required")
        return state

    # ---------- In-process pipeline (with rate limiting) ----------
    def execute_workflow_inprocess(self, state: PodcastProductionState) -> PodcastProductionState:
        ordering = [
            ("refinement", "refinement"),
            ("researcher", "research"),
            ("outline_architect", "outline"),
            ("script_writer", "script"),
            ("fact_validator", "validation"),
            ("show_notes_specialist", "show_notes"),
            ("social_media_coordinator", "social_media"),
            ("content_critic", "complete"),
        ]

        # Import rate limiter
        from utils.retry_handler import RateLimiter
        
        # Create rate limiter with 1 second delay between agent calls
        rate_limiter = RateLimiter(delay=1.0)
        
        curr = state
        for i, (key, stage) in enumerate(ordering):
            agent = self.agents.get(key)
            if not agent:
                self.logger.warning(f"Missing agent {key}, skipping")
                continue
            
            # Apply rate limiting (skip for first agent)
            if i > 0:
                with rate_limiter:
                    curr = self.execute_agent_safely(agent, curr, stage)
            else:
                curr = self.execute_agent_safely(agent, curr, stage)
            
            # After script writer, update citations based on actual usage
            if key == "script_writer" and curr.used_citation_ids and curr.citations_data:
                curr = self._update_citations_based_on_usage(curr)
        
        return curr
    
    def _update_citations_based_on_usage(self, state: PodcastProductionState) -> PodcastProductionState:
        """Update citation data to only include citations actually used in the script."""
        self.logger.info("Updating citations based on actual usage in script")
        
        if not state.citations_data or not state.used_citation_ids:
            return state
        
        used_ids_set = set(state.used_citation_ids)
        citations_list = state.citations_data.get('citations', [])
        
        # Mark citations as used and update counts
        for citation in citations_list:
            citation_id = citation.get('source_id', '')
            if f"[{citation_id}]" in used_ids_set:
                # This citation was actually used
                citation['quote_count'] = state.final_script.count(f"[{citation_id}]")
                if 'used_in_sections' not in citation:
                    citation['used_in_sections'] = []
                if 'script' not in citation['used_in_sections']:
                    citation['used_in_sections'].append('script')
            else:
                # This citation was NOT used - set count to 0
                citation['quote_count'] = 0
                citation['used_in_sections'] = []
        
        # Update counts
        used_count = sum(1 for c in citations_list if c.get('quote_count', 0) > 0)
        state.citations_data['used_citations'] = used_count
        
        # Update by_type counts to only include used citations
        by_type = {'web': 0, 'youtube': 0, 'arxiv': 0, 'pubmed': 0}
        for citation in citations_list:
            if citation.get('quote_count', 0) > 0:
                source_type = citation.get('source_type', 'web')
                if source_type in by_type:
                    by_type[source_type] += 1
        state.citations_data['by_type'] = by_type
        
        self.logger.info(f"Updated citations: {used_count} out of {len(citations_list)} actually used")
        self.logger.info(f"Citations by type: {by_type}")
        
        return state

    def execute_agent_safely(self, agent, state: PodcastProductionState, stage: str) -> PodcastProductionState:
        agent_name = agent.name
        try:
            if not self.state_helpers.validate_state_progression(state, stage):
                self.logger.warning(f"State validation warning for {agent_name}; continuing")
            self.callback.on_agent_start(agent, state)
            
            # Execute agent with retry logic (uses global config set during init)
            from utils.retry_handler import retry_with_backoff
            
            # Create retry wrapper for agent execution (uses global retry config)
            @retry_with_backoff(
                on_retry=lambda e, attempt, delay: self.logger.warning(
                    f"🔄 Retrying {agent_name} after error: {e}"
                )
            )
            def execute_with_retry():
                return agent.execute(state)
            
            new_state = execute_with_retry()
            
            try:
                new_state.update_timestamp()
            except Exception:
                pass
            self.callback.on_agent_end(agent, new_state)
            self.logger.debug(f"State after {agent_name}: {self.state_helpers.get_state_summary(new_state)}")
            return new_state
        except Exception as e:
            self.logger.error(f"Agent {agent_name} failed: {e}", exc_info=True)
            self.callback.on_agent_error(agent, state, e)
            raise

    # ---------- A2A workflow ----------
    def _register_wrapped_agents_with_broker(self) -> None:
        """
        Register all wrapped agents with the broker for A2A communication.
        This enables both ADK and LangGraph agents to participate in the A2A workflow.
        """
        if not hasattr(self, 'wrapped_agents') or not self.wrapped_agents:
            self.logger.warning("No wrapped agents available for A2A registration")
            return
        
        broker = get_global_broker()
        
        for name, wrapper in self.wrapped_agents.items():
            try:
                # Subscribe wrapper to its named topic
                broker.subscribe_sync(name, lambda msg, w=wrapper: w.handle_a2a(msg))
                self.logger.info(f"Registered wrapped agent '{name}' with broker on topic '{name}'")
            except Exception as e:
                self.logger.error(f"Failed to register wrapped agent '{name}' with broker: {e}")
                raise
    
    def publish_initial_state_to_broker(self, state: PodcastProductionState) -> None:
        """
        Publish the initial state to the broker on topic 'topic_refinement'.
        Requires a2a_broker and adk_adapter.a2a_message helpers to be available.
        Also registers wrapped agents with the broker for A2A communication.
        """
        if not A2A_AVAILABLE:
            raise RuntimeError("A2A mode not available: a2a_broker or adk_adapter not installed")

        broker = get_global_broker()
        broker.start_background_loop()
        
        # Register wrapped agents with broker
        self._register_wrapped_agents_with_broker()
        
        msg = state_to_message(state)
        # optionally include a 'next' field
        msg["next"] = "refinement"
        self.logger.info("Publishing initial state to broker topic 'refinement'")
        broker.publish_sync("refinement", msg)

    def wait_for_final_state_from_broker(self, timeout: int = 60) -> PodcastProductionState:
        """
        Subscribe to 'content_critic' and wait for a final state message.
        Returns a PodcastProductionState reconstructed from payload.
        """
        if not A2A_AVAILABLE:
            raise RuntimeError("A2A mode not available: a2a_broker or adk_adapter not installed")

        broker = get_global_broker()
        broker.start_background_loop()
        done = Event()
        final_payload: Dict[str, Any] = {}

        def _on_final(msg):
            nonlocal final_payload
            try:
                # msg expected to be {'type': 'state_update', 'payload': {...}}
                final_payload = msg.get("payload") if isinstance(msg, dict) else {}
                self.logger.info("Received final message on content_critic topic")
            except Exception as e:
                self.logger.warning(f"Received a final message but failed to parse: {e}")
                final_payload = {}
            finally:
                done.set()

        self.logger.info("Subscribing to broker topic 'content_critic' and waiting for final package")
        broker.subscribe_sync("content_critic", _on_final)

        # block until event set or timeout
        finished = done.wait(timeout=timeout)
        if not finished:
            raise TimeoutError(f"Timed out waiting for final package after {timeout} seconds")

        if not final_payload:
            raise RuntimeError("Final payload empty or invalid")

        # Reconstruct PodcastProductionState from payload
        try:
            state = PodcastProductionState(**final_payload)
            return state
        except Exception as e:
            self.logger.error(f"Failed to reconstruct PodcastProductionState from payload: {e}", exc_info=True)
            # As fallback, try to extract fields manually
            minimal = PodcastProductionState(
                initial_topic=final_payload.get("initial_topic", ""),
                tone=final_payload.get("tone", "conversational"),
                selected_refined_topic=final_payload.get("selected_refined_topic", final_payload.get("initial_topic", ""))
            )
            # try to attach script/show_notes/social etc if present
            if "final_script" in final_payload:
                minimal.final_script = final_payload.get("final_script", "")
            if "show_notes" in final_payload:
                minimal.show_notes = final_payload.get("show_notes", "")
            if "all_sources" in final_payload:
                minimal.all_sources = final_payload.get("all_sources", [])
            return minimal

    # ---------- Output generation ----------
    def generate_outputs_from_state(self, state: PodcastProductionState) -> str:
        """
        Build PodcastContentPackage.from_state(state) and write files via FileWriter.
        Returns output_dir.
        """
        package = PodcastContentPackage.from_state(state)
        outdir = self.file_writer.write_podcast_package(package)
        return outdir

    # ---------- High-level runners ----------
    def run_inprocess(self, topic: str, tone: str) -> PodcastProductionState:
        state = self.create_initial_state(topic, tone)
        self.callback.on_workflow_start(state)
        final_state = self.execute_workflow_inprocess(state)
        self.generate_outputs_from_state(final_state)
        self.callback.on_workflow_end(final_state)
        return final_state

    def run_a2a(self, topic: str, tone: str, timeout: int = 60) -> PodcastProductionState:
        if not A2A_AVAILABLE:
            raise RuntimeError("A2A mode unavailable: a2a_broker or adk_adapter not installed")

        state = self.create_initial_state(topic, tone)
        self.publish_initial_state_to_broker(state)
        final_state = self.wait_for_final_state_from_broker(timeout=timeout)
        # After receiving final_state, write outputs
        self.generate_outputs_from_state(final_state)
        return final_state


def main():
    import argparse

    parser = argparse.ArgumentParser(description="AI Podcast Production Suite")
    parser.add_argument("topic", help="Main topic for the podcast episode")
    parser.add_argument("--tone", default="conversational",
                        choices=["conversational", "formal", "humorous", "technical", "storytelling"],
                        help="Tone for the podcast content")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging level")
    parser.add_argument("--cleanup", action="store_true",
                        help="Clean up old output directories before starting")
    parser.add_argument("--a2a", action="store_true",
                        help="Publish initial state to the A2A broker and wait for final result (requires a2a_broker & adk_adapter)")
    parser.add_argument("--a2a-timeout", type=int, default=60,
                        help="Seconds to wait for final content when using --a2a")
    parser.add_argument("--strict", action="store_true",
                        help="Fail early if required environment variables are missing")
    parser.add_argument("--basic-research", action="store_true",
                        help="Use basic research mode (disable YouTube and academic search)")
    parser.add_argument("--retry-mode", default="default",
                        choices=["default", "aggressive", "conservative", "persistent"],
                        help="Retry configuration mode (default: balanced, aggressive: more retries, conservative: fewer retries, persistent: retry until success)")
    args = parser.parse_args()

    # Setup environment (optionally strict)
    try:
        setup_environment(strict=args.strict)
    except Exception as e:
        logger.warning(f"Environment setup warning: {e}")
        if args.strict:
            raise

    try:
        # Use enhanced research by default, unless --basic-research flag is set
        use_enhanced = not args.basic_research
        app = PodcastProductionApp(
            log_level=args.log_level, 
            use_enhanced_research=use_enhanced,
            retry_mode=args.retry_mode
        )
        app.logger.info("Starting run")

        if args.cleanup:
            try:
                app.file_writer.cleanup_old_outputs()
            except Exception as e:
                app.logger.warning(f"Cleanup failed: {e}")

        if args.a2a:
            app.logger.info("Running in A2A mode (publishing to broker)")
            final_state = app.run_a2a(args.topic, args.tone, timeout=args.a2a_timeout)
        else:
            app.logger.info("Running in in-process mode")
            final_state = app.run_inprocess(args.topic, args.tone)

        print("\n✅ Podcast production completed successfully!")
        print(f"📁 Outputs saved to: output/{app.file_writer._sanitize_filename(final_state.selected_refined_topic or args.topic)}/")
        quality = getattr(getattr(final_state, "quality_report", None), "overall_score", "N/A")
        print(f"⭐ Quality score: {quality}/10")

        return 0

    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        return 1
    except TimeoutError as e:
        print(f"\n⏱️ A2A timeout: {e}")
        logger.exception("A2A timeout")
        return 2
    except Exception as e:
        print(f"\n💥 Application error: {e}")
        logger.exception("Application error")
        return 1


if __name__ == "__main__":
    exit(main())

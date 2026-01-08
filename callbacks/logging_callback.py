# callbacks/logging_callback.py
import logging
import time
from typing import Dict, Any, TYPE_CHECKING
from schemas.state_models import PodcastProductionState
from utils.pydantic_compat import model_to_dict

if TYPE_CHECKING:
    from typing import Any as Agent
else:
    Agent = Any

# Configure module logger
LOG_PREVIEW_MAX = 300
STATE_SNAPSHOT_ITEMS = 12

class PodcastProductionCallback:
    """
    Comprehensive callback for monitoring podcast production workflow.
    Provides detailed logging at different levels for transparency and debugging.
    """

    def __init__(self, log_level: str = "INFO"):
        self.log_level = log_level
        self.agent_start_times: Dict[str, float] = {}
        self.setup_logger()

    def setup_logger(self):
        """Configure logging with different levels and formatting."""
        self.logger = logging.getLogger("podcast_production")
        # Prevent double logging in some environments
        self.logger.propagate = False

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        level = getattr(logging, self.log_level.upper(), logging.INFO)
        self.logger.setLevel(level)

    def on_agent_start(self, agent: Agent, state: PodcastProductionState, framework: str = "ADK") -> None:
        """Called when an agent starts execution."""
        self.agent_start_times[agent.name] = time.time()

        try:
            snapshot = self._get_state_snapshot(state)
            self.logger.info(f"🟢 AGENT_START: {agent.name} [Framework: {framework}] (topic={snapshot.get('initial_topic','N/A')}, refined={snapshot.get('selected_refined_topic','N/A')})")
            self.logger.debug(f"Agent {agent.name} ({framework}) starting state snapshot: {snapshot}")
        except Exception as e:
            self.logger.warning(f"AGENT_START logging failed: {e}")

    def on_agent_end(self, agent: Agent, state: PodcastProductionState) -> None:
        """Called when an agent completes execution."""
        start_time = self.agent_start_times.get(agent.name, time.time())
        duration = time.time() - start_time

        try:
            self.logger.info(f"🔵 AGENT_END: {agent.name} completed in {duration:.2f}s")
            self._log_agent_specific_outputs(agent.name, state)
            self._log_state_changes(agent.name, state)
            if agent.name in self.agent_start_times:
                del self.agent_start_times[agent.name]
        except Exception as e:
            self.logger.warning(f"AGENT_END logging failed: {e}")

    def on_agent_error(self, agent: Agent, state: PodcastProductionState, error: Exception) -> None:
        """Called when an agent encounters an error."""
        try:
            snapshot = self._get_state_snapshot(state)
            self.logger.error(f"🔴 AGENT_ERROR: {agent.name} failed: {type(error).__name__}: {error}", exc_info=True)
            self.logger.debug(f"State at error: {snapshot}")
        except Exception as e:
            self.logger.error(f"AGENT_ERROR logging failure: {e}", exc_info=True)

    def on_tool_call(self, tool_name: str, arguments: Dict[str, Any], agent_name: str = None) -> None:
        """Called when an agent calls a tool."""
        try:
            args_preview = self._summarize_text(str(arguments), 200)
            agent_prefix = f"{agent_name} -> " if agent_name else ""
            self.logger.info(f"🛠️ TOOL_CALL: {agent_prefix}{tool_name}")
            self.logger.debug(f"🛠️ TOOL_CALL: {agent_prefix}{tool_name}; arguments={args_preview}")
        except Exception:
            agent_prefix = f"{agent_name} -> " if agent_name else ""
            self.logger.debug(f"🛠️ TOOL_CALL: {agent_prefix}{tool_name} (arguments not previewable)")

    def on_tool_complete(self, tool_name: str, result: Any, agent_name: str = None) -> None:
        """Called when a tool returns a result."""
        try:
            result_summary = self._summarize_tool_result(result)
            agent_prefix = f"{agent_name} <= " if agent_name else ""
            self.logger.info(f"✅ TOOL_COMPLETE: {agent_prefix}{tool_name}")
            self.logger.debug(f"✅ TOOL_COMPLETE: {agent_prefix}{tool_name}; result={result_summary}")
        except Exception as e:
            agent_prefix = f"{agent_name} <= " if agent_name else ""
            self.logger.debug(f"TOOL_COMPLETE logging failed for {agent_prefix}{tool_name}: {e}")

    # Legacy methods for backward compatibility
    def on_tool_result(self, agent: Agent, tool_name: str, result: Any) -> None:
        """Called when a tool returns a result (legacy method)."""
        self.on_tool_complete(tool_name, result, agent.name if agent else None)

    def on_llm_call(self, agent: Agent, prompt: str) -> None:
        """Called when an agent makes an LLM call."""
        try:
            prompt_preview = self._summarize_text(prompt, LOG_PREVIEW_MAX)
            # Log full prompt only at DEBUG
            self.logger.debug(f"🤖 LLM_CALL: {agent.name} prompt_length={len(prompt)} prompt_preview={prompt_preview}")
        except Exception:
            self.logger.debug(f"🤖 LLM_CALL: {agent.name} (prompt not previewable)")

    def on_llm_result(self, agent: Agent, response: str) -> None:
        """Called when an agent receives an LLM response."""
        try:
            resp_preview = self._summarize_text(response, LOG_PREVIEW_MAX)
            self.logger.debug(f"🤖 LLM_RESULT: {agent.name} response_length={len(response) if response else 0} response_preview={resp_preview}")
        except Exception:
            self.logger.debug("🤖 LLM_RESULT: (response not previewable)")

    def on_state_update(self, old_state: PodcastProductionState, new_state: PodcastProductionState) -> None:
        """Called when the state is updated."""
        try:
            changes = self._detect_state_changes(old_state, new_state)
            if changes:
                self.logger.info("📝 STATE_UPDATE: State changed")
                self.logger.debug(f"State changes: {changes}")
        except Exception as e:
            self.logger.debug(f"on_state_update failed: {e}")

    def on_workflow_start(self, initial_state: PodcastProductionState) -> None:
        """Called when the workflow starts."""
        try:
            snapshot = self._get_state_snapshot(initial_state)
            self.logger.info(f"🚀 WORKFLOW_START: topic='{snapshot.get('initial_topic','N/A')}', tone='{snapshot.get('tone','N/A')}'")
            self.logger.debug(f"Initial state snapshot: {snapshot}")
        except Exception as e:
            self.logger.warning(f"WORKFLOW_START logging failed: {e}")

    def on_workflow_end(self, final_state: PodcastProductionState) -> None:
        """Called when the workflow completes successfully."""
        try:
            snapshot = self._get_final_outputs_summary(final_state)
            self.logger.info("🎉 WORKFLOW_END: Podcast production workflow completed successfully")
            self.logger.info(f"Summary: script_len={snapshot.get('script_length','N/A')} show_notes_len={snapshot.get('show_notes_length','N/A')} sources={snapshot.get('sources_count','N/A')} estimated_duration={snapshot.get('estimated_duration','N/A')} quality_score={snapshot.get('quality_score','N/A')}")
            self.logger.debug(f"Final outputs snapshot: {snapshot}")
        except Exception as e:
            self.logger.warning(f"WORKFLOW_END logging failed: {e}")

    def on_workflow_error(self, state: PodcastProductionState, error: Exception) -> None:
        """Called when the workflow encounters an error."""
        try:
            snapshot = self._get_state_snapshot(state)
            self.logger.error(f"💥 WORKFLOW_ERROR: {type(error).__name__}: {error}", exc_info=True)
            self.logger.debug(f"State at failure: {snapshot}")
        except Exception as e:
            self.logger.error(f"WORKFLOW_ERROR logging failed: {e}", exc_info=True)

    def _log_state_changes(self, agent_name: str, state: PodcastProductionState) -> None:
        """Log state changes made by the agent."""
        try:
            snapshot = self._get_state_snapshot(state)
            changed_fields = []
            
            # Track which fields have non-empty values
            for key, value in snapshot.items():
                if value and value != "N/A" and value != "None":
                    # Check if it's a meaningful change (not just metadata)
                    if not key.startswith("_") and key not in ["initial_topic", "tone"]:
                        changed_fields.append(key)
            
            if changed_fields:
                self.logger.debug(f"📝 STATE_CHANGES by {agent_name}: {', '.join(changed_fields[:5])}")
        except Exception as e:
            self.logger.debug(f"_log_state_changes failed: {e}")

    def _log_agent_specific_outputs(self, agent_name: str, state: PodcastProductionState) -> None:
        """Log agent-specific outputs at appropriate log levels."""
        try:
            if agent_name == "TopicRefinementAgent":
                angles_count = len(getattr(state, "topic_angles", []) or [])
                sel = getattr(state, "selected_refined_topic", None)
                self.logger.info(f"📊 Refinement results: {angles_count} angles, selected: {sel}")

            elif agent_name == "TopicResearcherAgent":
                research_count = len(getattr(state, "research_materials", []) or [])
                sources_count = len(getattr(state, "all_sources", []) or [])
                self.logger.info(f"🔍 Research completed: {research_count} items, {sources_count} sources")
                if research_count < 2:
                    self.logger.warning("⚠️ Low research material count - consider expanding search queries")

            elif agent_name == "OutlineArchitectAgent":
                title = getattr(getattr(state, "episode_outline", None), "title", "N/A")
                sections = len(getattr(getattr(state, "episode_outline", None), "main_sections", []) or [])
                self.logger.info(f"📝 Outline created: '{title}' with {sections} sections")

            elif agent_name == "ScriptWriterAgent":
                script_len = len(getattr(state, "final_script", "") or "")
                self.logger.info(f"📄 Script written: {script_len} characters")

            elif agent_name == "FactCheckingValidatorAgent":
                verified = getattr(getattr(state, "fact_check_report", None), "verified_claims", None)
                total = getattr(getattr(state, "fact_check_report", None), "claims_checked", None)
                self.logger.info(f"✅ Fact-checking: {verified}/{total} high-confidence claims")
                try:
                    if isinstance(verified, (int, float)) and isinstance(total, (int, float)) and verified < (total or 1) / 2:
                        self.logger.warning("⚠️ Low verification rate - consider manual review")
                except Exception:
                    pass

            elif agent_name == "ShowNotesSpecialistAgent":
                sn_len = len(getattr(state, "show_notes", "") or "")
                self.logger.info(f"📋 Show notes generated: {sn_len} characters")

            elif agent_name == "SocialMediaCoordinatorAgent":
                social = getattr(state, "social_posts", {}) or {}
                total_posts = sum(len(posts) for posts in social.values()) if isinstance(social, dict) else 0
                platforms = list(social.keys()) if isinstance(social, dict) else []
                self.logger.info(f"📱 Social media posts: {total_posts} across {len(platforms)} platforms")

            elif agent_name == "ContentPackageCriticAgent":
                score = getattr(getattr(state, "quality_report", None), "overall_score", None)
                self.logger.info(f"⭐ Quality assessment: {score}/10")
                try:
                    if score is not None and float(score) < 7.0:
                        self.logger.warning("⚠️ Low quality score - review recommendations")
                except Exception:
                    pass
        except Exception as e:
            self.logger.debug(f"_log_agent_specific_outputs failed: {e}")

    def _get_state_snapshot(self, state: PodcastProductionState) -> Dict[str, Any]:
        """Create a safe snapshot of the state for logging."""
        try:
            # Use Pydantic model_to_dict for safe conversion when available
            state_dict = model_to_dict(state) if state is not None else {}
        except Exception:
            # Fallback to shallow manual snapshot
            state_dict = {}
            try:
                state_dict["initial_topic"] = getattr(state, "initial_topic", None)
                state_dict["selected_refined_topic"] = getattr(state, "selected_refined_topic", None)
                state_dict["tone"] = getattr(state, "tone", None)
                state_dict["research_items"] = len(getattr(state, "research_materials", []) or [])
                state_dict["sources_count"] = len(getattr(state, "all_sources", []) or [])
            except Exception:
                pass

        # Trim large fields for readability
        for k in list(state_dict.keys()):
            if isinstance(state_dict[k], (list, dict)):
                state_dict[k] = f"{type(state_dict[k]).__name__}[{len(state_dict[k])}]"
            elif isinstance(state_dict[k], str) and len(state_dict[k]) > LOG_PREVIEW_MAX:
                state_dict[k] = state_dict[k][:LOG_PREVIEW_MAX] + "..."

        # keep snapshot small
        limited = {k: state_dict[k] for i, k in enumerate(state_dict) if i < STATE_SNAPSHOT_ITEMS}
        return limited

    def _summarize_tool_result(self, result: Any) -> str:
        """Create a summary of tool results for logging."""
        try:
            if isinstance(result, str):
                return self._summarize_text(result, 150)
            if isinstance(result, list):
                return f"List[{len(result)}]"
            if isinstance(result, dict):
                keys = list(result.keys())
                preview = {k: (str(result[k])[:80] + ("..." if len(str(result[k])) > 80 else "")) for k in keys[:6]}
                return f"Dict[{len(keys)}] keys={keys[:6]} preview={preview}"
            return str(type(result))
        except Exception as e:
            return f"unserializable_result: {e}"

    def _summarize_text(self, text: str, max_length: int) -> str:
        """Summarize long text for logging."""
        if not isinstance(text, str):
            return str(text)[:max_length]
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def _detect_state_changes(self, old_state: PodcastProductionState, new_state: PodcastProductionState) -> Dict[str, Any]:
        """Detect what changed between state versions (high level)."""
        changes = {}
        try:
            old = model_to_dict(old_state) if old_state is not None else {}
            new = model_to_dict(new_state) if new_state is not None else {}

            keys = set(list(old.keys()) + list(new.keys()))
            for k in keys:
                o = old.get(k)
                n = new.get(k)
                if o != n:
                    # small diff representation
                    if isinstance(n, (str, int, float, bool)) or n is None:
                        changes[k] = f"{o} -> {n}"
                    elif isinstance(n, list):
                        changes[k] = f"List length: {len(o) if isinstance(o, list) else 0} -> {len(n)}"
                    elif isinstance(n, dict):
                        changes[k] = f"Dict keys: {len(o) if isinstance(o, dict) else 0} -> {len(n)}"
                    else:
                        changes[k] = "Modified"
        except Exception as e:
            self.logger.debug(f"_detect_state_changes error: {e}")
        return changes

    def _get_final_outputs_summary(self, final_state: PodcastProductionState) -> Dict[str, Any]:
        """Create a summary of final outputs (safe access)."""
        try:
            script_len = len(getattr(final_state, "final_script", "") or "")
        except Exception:
            script_len = None
        try:
            show_notes_len = len(getattr(final_state, "show_notes", "") or "")
        except Exception:
            show_notes_len = None
        social = getattr(final_state, "social_posts", {}) or {}
        try:
            social_platforms = list(social.keys()) if isinstance(social, dict) else []
            social_count = sum(len(v) for v in social.values()) if isinstance(social, dict) else None
        except Exception:
            social_platforms = []
            social_count = None

        sources_count = len(getattr(final_state, "all_sources", []) or [])
        estimated_duration = getattr(final_state, "estimated_duration_min", None)
        quality_score = getattr(getattr(final_state, "quality_report", None), "overall_score", None)

        return {
            "script_length": script_len,
            "show_notes_length": show_notes_len,
            "social_platforms": social_platforms,
            "social_posts_count": social_count,
            "sources_count": sources_count,
            "estimated_duration": estimated_duration,
            "quality_score": quality_score
        }

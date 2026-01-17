"""Multi-Agent Coordinator - Orchestrates parallel agents with context sharing.

Eliminates redundant codebase analysis by coordinating specialized agents
that work in parallel and share context between stages.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from devflow.agents.base import (
    AgentCapability,
    ImplementationContext,
)
from devflow.agents.base import MultiAgentCoordinator as BaseCoordinator
from devflow.agents.base import (
    ReviewContext,
    ValidationContext,
    WorkflowContext,
)
from devflow.core.agent_context import AgentContext, ContextManager
from devflow.core.mission_control import AgentStatus, LiveMissionControl, MissionControl
from devflow.exceptions import AgentError, WorkflowError

logger = logging.getLogger(__name__)


class ParallelAgentCoordinator:
    """Coordinates multiple agents working in parallel with context sharing."""

    def __init__(
        self,
        base_coordinator: BaseCoordinator,
        issue_number: int,
        enable_mission_control: bool = True,
    ):
        """Initialize the parallel coordinator."""
        self.base_coordinator = base_coordinator
        self.issue_number = issue_number
        self.context_manager = ContextManager(issue_number)

        # Mission control for beautiful UX
        self.mission_control = MissionControl(issue_number) if enable_mission_control else None
        self.live_display: Optional[LiveMissionControl] = None

        # Specialized agent pools
        self._exploration_agents = []
        self._implementation_agents = []
        self._review_agents = []

        self._organize_agents()

    def _organize_agents(self) -> None:
        """Organize agents by capability for specialized coordination."""
        for agent in self.base_coordinator.agents:
            capabilities = agent.capabilities

            if AgentCapability.ANALYSIS in capabilities:
                self._exploration_agents.append(agent)
            if AgentCapability.IMPLEMENTATION in capabilities:
                self._implementation_agents.append(agent)
            if AgentCapability.REVIEW in capabilities:
                self._review_agents.append(agent)

    def start_mission_control(self) -> None:
        """Start the mission control display."""
        if self.mission_control:
            # Register agents in mission control
            for i, agent in enumerate(self._exploration_agents):
                self.mission_control.register_agent(
                    f"explore_{i}", "exploration", f"Explorer {i+1}", "🔍"
                )

            for i, agent in enumerate(self._implementation_agents):
                self.mission_control.register_agent(
                    f"impl_{i}", "implementation", f"Builder {i+1}", "⚙️"
                )

            for i, agent in enumerate(self._review_agents):
                self.mission_control.register_agent(f"review_{i}", "review", f"Reviewer {i+1}", "👁️")

            self.live_display = LiveMissionControl(self.mission_control)
            self.live_display.__enter__()

    def stop_mission_control(self) -> None:
        """Stop the mission control display."""
        if self.live_display:
            self.live_display.__exit__(None, None, None)
            if self.mission_control:
                self.mission_control.show_summary()

    async def parallel_validation(self, context: ValidationContext) -> Dict[str, Any]:
        """Run validation with parallel exploration and context building."""
        if not self._exploration_agents:
            raise AgentError("No exploration agents available for validation")

        # Start mission control
        self.start_mission_control()

        try:
            # Phase 1: Parallel Exploration
            exploration_tasks = []
            for i, agent in enumerate(self._exploration_agents[:2]):  # Use up to 2 explorers
                agent_id = f"explore_{i}"

                if self.mission_control:
                    self.mission_control.start_agent(agent_id, "Analyzing codebase structure")

                task = self._run_exploration_agent(agent, context, agent_id)
                exploration_tasks.append(task)

            # Wait for exploration to complete
            exploration_results = await asyncio.gather(*exploration_tasks, return_exceptions=True)

            # Build shared context from exploration
            combined_context = self._merge_exploration_contexts(exploration_results)

            # Phase 2: Quick Validation Using Shared Context
            validation_agent = self._exploration_agents[0]  # Use first agent for validation

            if self.mission_control:
                self.mission_control.update_agent_progress(
                    "explore_0",
                    AgentStatus.COMPLETING,
                    90,
                    "Performing final validation with context",
                )

            # Run validation with pre-built context
            enhanced_context = self._enhance_validation_context(context, combined_context)
            validation_result = await self._run_validation_with_context(
                validation_agent, enhanced_context
            )

            return validation_result

        except Exception as e:
            logger.error(f"Parallel validation failed: {str(e)}")
            raise AgentError(f"Parallel validation failed: {str(e)}")

        finally:
            self.stop_mission_control()

    async def parallel_implementation(
        self, context: ImplementationContext, working_directory: str
    ) -> Dict[str, Any]:
        """Run implementation with parallel agents and context reuse."""

        # Start mission control
        if not self.live_display:
            self.start_mission_control()

        try:
            # Phase 1: Use context from validation
            context_summary = self.context_manager.get_context_summary("implementation")

            if context_summary != "No previous context available.":
                # Mark context reuse in mission control
                for i in range(len(self._implementation_agents)):
                    agent_id = f"impl_{i}"
                    if self.mission_control:
                        self.mission_control.mark_context_shared(agent_id, time_saved=45.0)

            # Phase 2: Parallel Implementation Strategy
            if len(self._implementation_agents) >= 2:
                # Split work between agents
                return await self._parallel_implementation_split(
                    context, working_directory, context_summary
                )
            else:
                # Single agent with context optimization
                return await self._single_implementation_optimized(
                    context, working_directory, context_summary
                )

        except Exception as e:
            logger.error(f"Parallel implementation failed: {str(e)}")
            raise AgentError(f"Parallel implementation failed: {str(e)}")

    async def parallel_review(self, context: ReviewContext) -> Dict[str, Any]:
        """Run code review with multiple reviewers in parallel."""

        try:
            if len(self._review_agents) < 2:
                # Fallback to single agent review
                return await self._single_agent_review(context)

            # Phase 1: Parallel Review Tasks
            review_tasks = []
            review_focuses = [
                ["correctness", "security"],
                ["maintainability", "performance"],
                ["testing", "documentation"],
            ]

            for i, (agent, focus) in enumerate(zip(self._review_agents[:3], review_focuses)):
                agent_id = f"review_{i}"

                if self.mission_control:
                    self.mission_control.start_agent(agent_id, f"Reviewing: {', '.join(focus)}")

                # Create focused review context
                focused_context = ReviewContext(
                    pull_request=context.pull_request,
                    changed_files=context.changed_files,
                    project_context=context.project_context,
                    maturity_level=context.maturity_level,
                    review_focus=focus,
                )

                task = self._run_focused_review(agent, focused_context, agent_id, focus)
                review_tasks.append(task)

            # Wait for all reviews
            review_results = await asyncio.gather(*review_tasks, return_exceptions=True)

            # Phase 2: Merge Review Results
            return self._merge_review_results(review_results)

        except Exception as e:
            logger.error(f"Parallel review failed: {str(e)}")
            raise AgentError(f"Parallel review failed: {str(e)}")

    # Implementation methods
    async def _run_exploration_agent(
        self, agent, context: ValidationContext, agent_id: str
    ) -> AgentContext:
        """Run exploration agent to build context."""

        start_time = datetime.now()

        if self.mission_control:
            self.mission_control.update_agent_progress(
                agent_id, AgentStatus.ANALYZING, 25, "Exploring codebase structure"
            )

        try:
            # Run focused exploration
            result = agent.validate_issue(context)

            if self.mission_control:
                self.mission_control.update_agent_progress(
                    agent_id, AgentStatus.COMPLETED, 100, "Codebase analysis complete"
                )

            # Extract context from result
            execution_time = (datetime.now() - start_time).total_seconds()

            agent_context = self.context_manager.extract_context_from_transcript(
                result.message, agent.name, "validation", execution_time
            )

            # Save to context manager
            self.context_manager.save_context(agent_context)

            return agent_context

        except Exception as e:
            if self.mission_control:
                self.mission_control.update_agent_progress(
                    agent_id, AgentStatus.FAILED, 0, f"Failed: {str(e)[:30]}"
                )
            raise

    def _merge_exploration_contexts(self, results: List) -> str:
        """Merge exploration results into unified context."""
        valid_results = [r for r in results if isinstance(r, AgentContext)]

        if not valid_results:
            return "No exploration context available."

        # Combine insights
        all_files = set()
        all_insights = []

        for result in valid_results:
            all_files.update(result.files_analyzed)
            all_insights.extend(result.key_insights)

        return f"Analyzed {len(all_files)} files with {len(all_insights)} key insights from parallel exploration."

    def _enhance_validation_context(
        self, original_context: ValidationContext, exploration_context: str
    ) -> ValidationContext:
        """Enhance validation context with exploration results."""

        # Add exploration context to project context
        enhanced_project_context = original_context.project_context.copy()
        enhanced_project_context["exploration_results"] = exploration_context

        return ValidationContext(
            issue=original_context.issue,
            project_context=enhanced_project_context,
            maturity_level=original_context.maturity_level,
            previous_attempts=original_context.previous_attempts,
        )

    async def _run_validation_with_context(
        self, agent, context: ValidationContext
    ) -> Dict[str, Any]:
        """Run validation agent with pre-built context."""

        # This would use the regular validation but with enhanced prompting
        # that includes the exploration context to avoid redundant file reading

        result = agent.validate_issue(context)

        return {
            "success": result.success,
            "result": result.result,
            "message": result.message,
            "confidence": result.confidence,
            "context_reused": True,
        }

    async def _parallel_implementation_split(
        self, context: ImplementationContext, working_directory: str, context_summary: str
    ) -> Dict[str, Any]:
        """Split implementation across multiple agents."""

        # Agent 1: Core implementation
        # Agent 2: Tests and documentation

        impl_agent = self._implementation_agents[0]
        test_agent = (
            self._implementation_agents[1] if len(self._implementation_agents) > 1 else impl_agent
        )

        # Start both agents
        if self.mission_control:
            self.mission_control.start_agent("impl_0", "Implementing core functionality")
            self.mission_control.start_agent("impl_1", "Writing tests and documentation")

        try:
            # For now, run sequentially but with context optimization
            # TODO: Implement true parallel split

            enhanced_context = self._add_context_to_implementation(context, context_summary)
            result = impl_agent.implement_changes(enhanced_context)

            if self.mission_control:
                self.mission_control.update_agent_progress(
                    "impl_0", AgentStatus.COMPLETED, 100, "Implementation complete"
                )

            return {
                "success": result.success,
                "result": result.result,
                "message": result.message,
                "context_reused": True,
            }

        except Exception as e:
            if self.mission_control:
                self.mission_control.update_agent_progress(
                    "impl_0", AgentStatus.FAILED, 0, f"Failed: {str(e)[:30]}"
                )
            raise

    async def _single_implementation_optimized(
        self, context: ImplementationContext, working_directory: str, context_summary: str
    ) -> Dict[str, Any]:
        """Single agent implementation optimized with context."""

        agent = self._implementation_agents[0]

        if self.mission_control:
            self.mission_control.start_agent("impl_0", "Implementation with context reuse")

        try:
            enhanced_context = self._add_context_to_implementation(context, context_summary)
            result = agent.implement_changes(enhanced_context)

            if self.mission_control:
                self.mission_control.update_agent_progress(
                    "impl_0", AgentStatus.COMPLETED, 100, "Implementation complete"
                )

            return {
                "success": result.success,
                "result": result.result,
                "message": result.message,
                "context_reused": True,
            }

        except Exception as e:
            if self.mission_control:
                self.mission_control.update_agent_progress(
                    "impl_0", AgentStatus.FAILED, 0, f"Failed: {str(e)[:30]}"
                )
            raise

    def _add_context_to_implementation(
        self, context: ImplementationContext, context_summary: str
    ) -> ImplementationContext:
        """Add context summary to implementation context."""

        enhanced_project_context = context.project_context.copy()
        enhanced_project_context["previous_analysis"] = context_summary

        return ImplementationContext(
            issue=context.issue,
            working_directory=context.working_directory,
            project_context=enhanced_project_context,
            validation_result=context.validation_result,
            previous_iterations=context.previous_iterations,
            constraints=context.constraints,
        )

    async def _run_focused_review(
        self, agent, context: ReviewContext, agent_id: str, focus_areas: List[str]
    ) -> Dict[str, Any]:
        """Run focused review on specific areas."""

        if self.mission_control:
            self.mission_control.update_agent_progress(
                agent_id, AgentStatus.ANALYZING, 50, f"Reviewing {', '.join(focus_areas)}"
            )

        try:
            result = agent.review_code(context)

            if self.mission_control:
                self.mission_control.update_agent_progress(
                    agent_id,
                    AgentStatus.COMPLETED,
                    100,
                    f"Review complete: {', '.join(focus_areas)}",
                )

            return {
                "agent": agent.name,
                "focus": focus_areas,
                "result": result,
                "success": result.success,
            }

        except Exception as e:
            if self.mission_control:
                self.mission_control.update_agent_progress(
                    agent_id, AgentStatus.FAILED, 0, f"Review failed: {str(e)[:20]}"
                )
            raise

    def _merge_review_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge parallel review results."""

        valid_results = [r for r in results if isinstance(r, dict) and r.get("success")]

        if not valid_results:
            return {"success": False, "message": "All reviews failed"}

        # TODO: Implement sophisticated review merging logic
        # For now, use the first successful result
        return valid_results[0]["result"].__dict__

    async def _single_agent_review(self, context: ReviewContext) -> Dict[str, Any]:
        """Fallback to single agent review."""
        agent = self._review_agents[0]

        if self.mission_control:
            self.mission_control.start_agent("review_0", "Comprehensive code review")

        result = agent.review_code(context)

        if self.mission_control:
            self.mission_control.update_agent_progress(
                "review_0", AgentStatus.COMPLETED, 100, "Review complete"
            )

        return result.__dict__

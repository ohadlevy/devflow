"""DevFlow Workflow Engine - Core orchestration logic.

This module contains the main workflow engine that orchestrates the complete
development lifecycle automation, extracted and enhanced from the original
embedded pipeline system.
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from devflow.adapters.base import (
    Issue,
    IssueState as AdapterIssueState,
    PlatformAdapter,
    PullRequest,
    PullRequestState,
    Review,
    ReviewDecision
)
from devflow.agents.base import (
    AgentCapability,
    AgentProvider,
    ImplementationContext,
    ImplementationResponse,
    ImplementationResult,
    MultiAgentCoordinator,
    ReviewContext,
    ReviewResponse,
    ValidationContext,
    ValidationResponse,
    ValidationResult,
    WorkflowContext
)
from devflow.core.config import ProjectConfig
from devflow.exceptions import (
    AgentError,
    PlatformError,
    StateError,
    ValidationError,
    WorkflowError
)

# Rich console for beautiful output
console = Console()

# Configure logging
logger = logging.getLogger(__name__)


class WorkflowState(str, Enum):
    """Workflow states for issue processing."""
    PENDING = "pending"
    VALIDATING = "validating"
    VALIDATED = "validated"
    WORKTREE_CREATING = "worktree_creating"
    IMPLEMENTING = "implementing"
    IMPLEMENTED = "implemented"
    REVIEWING = "reviewing"
    NEEDS_FIXES = "needs_fixes"
    REVIEW_PASSED = "review_passed"
    FINALIZING = "finalizing"
    READY_FOR_HUMAN = "ready_for_human"
    COMPLETED = "completed"
    MERGED = "merged"

    # Error states
    VALIDATION_FAILED = "validation_failed"
    IMPLEMENTATION_FAILED = "implementation_failed"
    REVIEW_FAILED = "review_failed"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    NEEDS_HUMAN_INTERVENTION = "needs_human_intervention"


@dataclass
class WorkflowSession:
    """Represents a workflow processing session."""
    issue_id: str
    issue_number: int
    current_state: WorkflowState
    iteration_count: int
    max_iterations: int
    worktree_path: Optional[Path]
    branch_name: Optional[str]
    pr_number: Optional[int]
    session_transcript: str
    context_data: Dict[str, Any]
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'issue_id': self.issue_id,
            'issue_number': self.issue_number,
            'current_state': self.current_state.value,
            'iteration_count': self.iteration_count,
            'max_iterations': self.max_iterations,
            'worktree_path': str(self.worktree_path) if self.worktree_path else None,
            'branch_name': self.branch_name,
            'pr_number': self.pr_number,
            'session_transcript': self.session_transcript,
            'context_data': self.context_data,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowSession':
        """Create from dictionary."""
        return cls(
            issue_id=data['issue_id'],
            issue_number=data['issue_number'],
            current_state=WorkflowState(data['current_state']),
            iteration_count=data['iteration_count'],
            max_iterations=data['max_iterations'],
            worktree_path=Path(data['worktree_path']) if data.get('worktree_path') else None,
            branch_name=data.get('branch_name'),
            pr_number=data.get('pr_number'),
            session_transcript=data.get('session_transcript', ''),
            context_data=data.get('context_data', {}),
            created_at=data['created_at'],
            updated_at=data['updated_at']
        )


class WorkflowEngine:
    """Core workflow engine for DevFlow automation.

    This class orchestrates the complete development lifecycle automation,
    preserving and enhancing the sophisticated features from the original
    embedded pipeline system.
    """

    def __init__(
        self,
        config: ProjectConfig,
        platform_adapter: PlatformAdapter,
        agent_coordinator: MultiAgentCoordinator,
        state_manager: Optional['StateManager'] = None
    ) -> None:
        """Initialize the workflow engine.

        Args:
            config: Project configuration
            platform_adapter: Platform adapter for git/issue operations
            agent_coordinator: AI agent coordinator
            state_manager: State manager instance

        Raises:
            ValidationError: If configuration is invalid
        """
        self.config = config
        self.platform_adapter = platform_adapter
        self.agent_coordinator = agent_coordinator
        self.state_manager = state_manager  # Will be set later to avoid circular imports

        # Validate configuration
        config_errors = config.validate_complete()
        if config_errors:
            raise ValidationError(f"Invalid configuration: {'; '.join(config_errors)}")

        # Initialize permissions validation state
        self._permissions_validated = False

    def validate_environment(self) -> bool:
        """Validate environment and permissions.

        Returns:
            True if environment is valid

        Raises:
            ValidationError: If critical validation fails
        """
        console.print("\n[bold blue]Validating DevFlow environment...[/bold blue]")

        validation_results = []
        all_valid = True

        # Platform connection validation
        try:
            if self.platform_adapter.validate_connection():
                validation_results.append("✓ Platform connection")
            else:
                validation_results.append("✗ Platform connection failed")
                all_valid = False
        except Exception as e:
            validation_results.append(f"✗ Platform validation error: {str(e)}")
            all_valid = False

        # AI agent validation - check all available agents
        try:
            if not self.agent_coordinator.agents:
                validation_results.append("✗ No agents available")
                all_valid = False
            else:
                agents_validated = 0
                for agent_name, agent in self.agent_coordinator.agents.items():
                    try:
                        if agent.validate_connection():
                            validation_results.append(f"✓ {agent.display_name} agent connection")
                            agents_validated += 1
                        else:
                            validation_results.append(f"✗ {agent.display_name} agent not available")
                    except Exception as e:
                        validation_results.append(f"✗ {agent.display_name} agent error: {str(e)}")

                if agents_validated == 0:
                    all_valid = False

        except Exception as e:
            validation_results.append(f"✗ Agent validation error: {str(e)}")
            all_valid = False

        # Git environment validation
        try:
            result = subprocess.run(
                ['git', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                validation_results.append("✓ Git available")
            else:
                validation_results.append("✗ Git not available")
                all_valid = False
        except Exception:
            validation_results.append("✗ Git validation failed")
            all_valid = False

        # Display results
        for result in validation_results:
            console.print(f"  {result}")

        if all_valid:
            console.print("\n[green]✓ Environment validation passed[/green]")
            self._permissions_validated = True
        else:
            console.print("\n[red]✗ Environment validation failed[/red]")
            self._permissions_validated = False

        return all_valid

    def process_issue(
        self,
        issue_number: int,
        auto_mode: bool = False,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Process an issue through the complete workflow.

        Args:
            issue_number: Issue number to process
            auto_mode: Run in fully automated mode
            dry_run: Simulate without making changes

        Returns:
            Processing results

        Raises:
            WorkflowError: If processing fails
            ValidationError: If issue or configuration is invalid
        """
        if not self._permissions_validated:
            if not self.validate_environment():
                raise WorkflowError(
                    "Environment validation failed - fix issues before proceeding",
                    workflow_id=f"issue-{issue_number}"
                )

        console.print(f"\n[bold blue]Processing issue #{issue_number}[/bold blue]")
        console.print(f"Mode: {'Automated' if auto_mode else 'Interactive'}")

        if dry_run:
            console.print("[yellow]DRY RUN - No changes will be made[/yellow]")

        try:
            # Get or create workflow session
            session = self._get_or_create_session(issue_number)

            # Create workflow context
            context = self._create_workflow_context(session)

            # Execute workflow stages
            result = self._execute_workflow(session, context, auto_mode, dry_run)

            return result

        except Exception as e:
            logger.error(f"Workflow processing failed for issue #{issue_number}: {str(e)}")
            raise WorkflowError(
                f"Failed to process issue #{issue_number}: {str(e)}",
                workflow_id=f"issue-{issue_number}"
            ) from e

    def _get_or_create_session(self, issue_number: int) -> WorkflowSession:
        """Get existing workflow session or create new one.

        Args:
            issue_number: Issue number

        Returns:
            Workflow session

        Raises:
            PlatformError: If issue cannot be fetched
        """
        # Check if session exists in state manager
        if self.state_manager:
            existing_session = self.state_manager.get_workflow_session(issue_number)
            if existing_session:
                return existing_session

        # Fetch issue from platform
        try:
            issue = self.platform_adapter.get_issue(
                self.config.repo_owner,
                self.config.repo_name,
                issue_number
            )
        except Exception as e:
            raise PlatformError(
                f"Failed to fetch issue #{issue_number}",
                platform=self.platform_adapter.name
            ) from e

        # Create new session
        now = datetime.now().isoformat()

        session = WorkflowSession(
            issue_id=issue.id,
            issue_number=issue_number,
            current_state=WorkflowState.PENDING,
            iteration_count=0,
            max_iterations=self.config.workflows.implementation_max_iterations,
            worktree_path=None,
            branch_name=None,
            pr_number=None,
            session_transcript="",
            context_data={
                'issue_title': issue.title,
                'issue_body': issue.body,
                'issue_labels': issue.labels,
                'issue_url': issue.url
            },
            created_at=now,
            updated_at=now
        )

        # Save session
        if self.state_manager:
            self.state_manager.save_workflow_session(session)

        return session

    def _create_workflow_context(self, session: WorkflowSession) -> WorkflowContext:
        """Create workflow context from session.

        Args:
            session: Workflow session

        Returns:
            Workflow context
        """
        return WorkflowContext(
            project_name=self.config.project_name,
            repository_url=f"https://github.com/{self.config.repo_owner}/{self.config.repo_name}",
            base_branch=self.config.base_branch,
            working_directory=str(session.worktree_path) if session.worktree_path else str(self.config.project_root),
            issue=Issue(
                id=session.issue_id,
                number=session.issue_number,
                title=session.context_data.get('issue_title', ''),
                body=session.context_data.get('issue_body', ''),
                state=AdapterIssueState.OPEN,  # Assume open for processing
                labels=session.context_data.get('issue_labels', []),
                assignees=[],  # TODO: Get from session data
                author='',  # TODO: Get from session data
                created_at=session.created_at,  # TODO: Parse datetime
                updated_at=session.updated_at,  # TODO: Parse datetime
                url=session.context_data.get('issue_url', ''),
                platform_data=session.context_data
            ),
            previous_iterations=self._get_previous_iterations(session),
            maturity_level=self.config.maturity_level.value,
            custom_settings=self.config.get_effective_settings()
        )

    def _get_previous_iterations(self, session: WorkflowSession) -> List[Dict[str, Any]]:
        """Get previous iteration data from session.

        Args:
            session: Workflow session

        Returns:
            List of previous iterations
        """
        # TODO: Implement iteration tracking
        return []

    def _execute_workflow(
        self,
        session: WorkflowSession,
        context: WorkflowContext,
        auto_mode: bool,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute workflow stages based on current state.

        Args:
            session: Workflow session
            context: Workflow context
            auto_mode: Automated mode
            dry_run: Dry run mode

        Returns:
            Execution results
        """
        result = {
            'success': False,
            'session_id': session.issue_id,
            'issue_number': session.issue_number,
            'stages_completed': [],
            'current_state': session.current_state.value,
            'error': None,
            'pull_request': None
        }

        try:
            # Execute based on current state
            while True:
                console.print(f"\n[cyan]Current stage: {session.current_state.value}[/cyan]")

                # Check for terminal states
                if session.current_state in [
                    WorkflowState.COMPLETED,
                    WorkflowState.MERGED,
                    WorkflowState.MAX_ITERATIONS_REACHED,
                    WorkflowState.NEEDS_HUMAN_INTERVENTION
                ]:
                    break

                # Execute stage
                stage_result = self._execute_stage(session, context, auto_mode, dry_run)

                if stage_result['success']:
                    result['stages_completed'].append(session.current_state.value)

                    # Update session state
                    if stage_result.get('next_state'):
                        session.current_state = WorkflowState(stage_result['next_state'])
                        session.updated_at = datetime.now().isoformat()

                        if self.state_manager:
                            self.state_manager.save_workflow_session(session)
                else:
                    result['error'] = stage_result.get('error')
                    break

                # In interactive mode, ask for continuation
                if not auto_mode and not dry_run:
                    if not self._confirm_continue(session.current_state):
                        break

            # Final result
            result['success'] = session.current_state in [
                WorkflowState.COMPLETED,
                WorkflowState.MERGED,
                WorkflowState.READY_FOR_HUMAN
            ]
            result['current_state'] = session.current_state.value

            return result

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Workflow execution failed: {str(e)}")
            return result

    def _execute_stage(
        self,
        session: WorkflowSession,
        context: WorkflowContext,
        auto_mode: bool,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute a specific workflow stage.

        Args:
            session: Workflow session
            context: Workflow context
            auto_mode: Automated mode
            dry_run: Dry run mode

        Returns:
            Stage execution result
        """
        stage_handlers = {
            WorkflowState.PENDING: self._stage_validation,
            WorkflowState.VALIDATED: self._stage_worktree_creation,
            WorkflowState.IMPLEMENTING: self._stage_implementation,
            WorkflowState.IMPLEMENTED: self._stage_review,
            WorkflowState.NEEDS_FIXES: self._stage_fix_implementation,
            WorkflowState.REVIEW_PASSED: self._stage_finalization,
        }

        handler = stage_handlers.get(session.current_state)
        if not handler:
            return {
                'success': False,
                'error': f"No handler for stage: {session.current_state.value}"
            }

        return handler(session, context, auto_mode, dry_run)

    def _stage_validation(
        self,
        session: WorkflowSession,
        context: WorkflowContext,
        auto_mode: bool,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute validation stage.

        Args:
            session: Workflow session
            context: Workflow context
            auto_mode: Automated mode
            dry_run: Dry run mode

        Returns:
            Stage result
        """
        console.print("\n[bold]🔍 Stage: Issue Validation[/bold]")

        if dry_run:
            return {
                'success': True,
                'next_state': WorkflowState.VALIDATED.value,
                'validation_result': 'simulated_validation'
            }

        try:
            # Get validation agent
            validator = self.agent_coordinator.select_best_agent(
                capability=AgentCapability.VALIDATION,
                preferences=[self.config.agents.primary]
            )

            if not validator:
                raise AgentError("No validation agent available")

            # Create validation context
            validation_context = ValidationContext(
                issue=context.issue,
                project_context={
                    'maturity_level': context.maturity_level,
                    'platform': self.config.platforms.primary,
                    'configuration': context.custom_settings
                },
                maturity_level=context.maturity_level,
                previous_attempts=context.previous_iterations
            )

            # Run validation
            console.print("Running AI validation...")
            validation_response = validator.validate_issue(validation_context)

            # Store validation transcript
            session.session_transcript += f"\n=== VALIDATION ===\n{validation_response.message}\n"

            # Handle validation result
            if validation_response.result == ValidationResult.VALID:
                console.print("[green]✓ Issue validation passed[/green]")

                # Add validation label to issue
                if not dry_run:
                    self.platform_adapter.add_labels_to_issue(
                        self.config.repo_owner,
                        self.config.repo_name,
                        session.issue_number,
                        ["validated", "ready-for-implementation"]
                    )

                return {
                    'success': True,
                    'next_state': WorkflowState.VALIDATED.value,
                    'validation_result': validation_response.dict()
                }

            elif validation_response.result == ValidationResult.NEEDS_CLARIFICATION:
                # Post clarification comment
                if not auto_mode and not dry_run:
                    self._post_validation_comment(session, validation_response)

                return {
                    'success': False,
                    'error': 'Issue needs clarification',
                    'validation_result': validation_response.dict()
                }

            else:
                return {
                    'success': False,
                    'error': f'Validation failed: {validation_response.result}',
                    'validation_result': validation_response.dict()
                }

        except Exception as e:
            logger.error(f"Validation stage failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _stage_worktree_creation(
        self,
        session: WorkflowSession,
        context: WorkflowContext,
        auto_mode: bool,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute worktree creation stage.

        Args:
            session: Workflow session
            context: Workflow context
            auto_mode: Automated mode
            dry_run: Dry run mode

        Returns:
            Stage result
        """
        console.print("\n[bold]🌿 Stage: Worktree Creation[/bold]")

        if dry_run:
            return {
                'success': True,
                'next_state': WorkflowState.IMPLEMENTING.value,
                'worktree_path': '/tmp/mock-worktree',
                'branch_name': f'issue-{session.issue_number}'
            }

        try:
            # Generate branch name
            branch_name = f"issue-{session.issue_number}"

            # TODO: Implement actual Git worktree creation via GitProvider
            # For now, simulate the process
            console.print(f"Creating worktree for branch: {branch_name}")

            # Update session with worktree info
            session.branch_name = branch_name
            session.worktree_path = Path(f"/tmp/devflow-worktree-{session.issue_number}")

            console.print(f"[green]✓ Worktree created at: {session.worktree_path}[/green]")

            return {
                'success': True,
                'next_state': WorkflowState.IMPLEMENTING.value,
                'worktree_path': str(session.worktree_path),
                'branch_name': branch_name
            }

        except Exception as e:
            logger.error(f"Worktree creation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _stage_implementation(
        self,
        session: WorkflowSession,
        context: WorkflowContext,
        auto_mode: bool,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute implementation stage.

        Args:
            session: Workflow session
            context: Workflow context
            auto_mode: Automated mode
            dry_run: Dry run mode

        Returns:
            Stage result
        """
        console.print("\n[bold]⚙️ Stage: Code Implementation[/bold]")

        if dry_run:
            return {
                'success': True,
                'next_state': WorkflowState.IMPLEMENTED.value,
                'files_changed': ['src/example.py', 'tests/test_example.py'],
                'commits': ['feat: implement feature #123']
            }

        try:
            # Get implementation agent
            implementer = self.agent_coordinator.select_best_agent(
                capability=AgentCapability.IMPLEMENTATION,
                preferences=[self.config.agents.primary]
            )

            if not implementer:
                raise AgentError("No implementation agent available")

            # Create implementation context
            impl_context = ImplementationContext(
                issue=context.issue,
                working_directory=str(session.worktree_path),
                project_context={
                    'maturity_level': context.maturity_level,
                    'configuration': context.custom_settings,
                    'previous_transcript': session.session_transcript
                },
                validation_result={},  # TODO: Get from session
                previous_iterations=context.previous_iterations,
                constraints={
                    'max_iterations': session.max_iterations,
                    'current_iteration': session.iteration_count
                }
            )

            # Run implementation
            console.print(f"Running AI implementation (iteration {session.iteration_count + 1})...")
            impl_response = implementer.implement_changes(impl_context)

            # Update session transcript
            session.session_transcript += f"\n=== IMPLEMENTATION ===\n{impl_response.message}\n"

            # Handle implementation result
            if impl_response.result == ImplementationResult.SUCCESS:
                console.print("[green]✓ Implementation completed successfully[/green]")

                session.iteration_count += 1

                return {
                    'success': True,
                    'next_state': WorkflowState.IMPLEMENTED.value,
                    'implementation_result': impl_response.dict()
                }

            elif impl_response.result == ImplementationResult.PARTIAL:
                console.print("[yellow]⚠ Implementation partially completed[/yellow]")

                # TODO: Handle partial implementation
                return {
                    'success': True,
                    'next_state': WorkflowState.IMPLEMENTED.value,
                    'implementation_result': impl_response.dict()
                }

            else:
                return {
                    'success': False,
                    'error': f'Implementation failed: {impl_response.result}',
                    'implementation_result': impl_response.dict()
                }

        except Exception as e:
            logger.error(f"Implementation stage failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _stage_review(
        self,
        session: WorkflowSession,
        context: WorkflowContext,
        auto_mode: bool,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute code review stage.

        Args:
            session: Workflow session
            context: Workflow context
            auto_mode: Automated mode
            dry_run: Dry run mode

        Returns:
            Stage result
        """
        console.print("\n[bold]👁️ Stage: Code Review[/bold]")

        if dry_run:
            return {
                'success': True,
                'next_state': WorkflowState.REVIEW_PASSED.value,
                'review_decision': 'approve'
            }

        try:
            # Create pull request if not exists
            if not session.pr_number:
                pr = self._create_pull_request(session, context)
                session.pr_number = pr.number

            # Get changed files
            changed_files = self.platform_adapter.get_pull_request_files(
                self.config.repo_owner,
                self.config.repo_name,
                session.pr_number
            )

            # Create review context
            review_context = ReviewContext(
                pull_request=PullRequest(  # TODO: Get actual PR data
                    id=str(session.pr_number),
                    number=session.pr_number,
                    title=f"Fix issue #{session.issue_number}",
                    body="AI-generated implementation",
                    state=PullRequestState.OPEN,
                    source_branch=session.branch_name,
                    target_branch=self.config.base_branch,
                    author="devflow-bot",
                    reviewers=[],
                    labels=[],
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                    mergeable=True,
                    url=f"https://github.com/{self.config.repo_owner}/{self.config.repo_name}/pull/{session.pr_number}",
                    platform_data={}
                ),
                changed_files=changed_files,
                project_context={
                    'maturity_level': context.maturity_level,
                    'configuration': context.custom_settings
                },
                maturity_level=context.maturity_level,
                review_focus=['correctness', 'maintainability', 'security']
            )

            # Coordinate multi-agent review
            console.print("Running AI code review...")
            review_responses = self.agent_coordinator.coordinate_review(
                review_context,
                reviewer_names=self.config.agents.review_sources
            )

            # Merge review feedback
            merged_decision = self._merge_review_feedback(review_responses)

            # Update session transcript
            for response in review_responses:
                session.session_transcript += f"\n=== REVIEW ({response.decision}) ===\n{response.message}\n"

            if merged_decision == ReviewDecision.APPROVE:
                console.print("[green]✓ Code review passed[/green]")
                return {
                    'success': True,
                    'next_state': WorkflowState.REVIEW_PASSED.value,
                    'review_responses': [r.dict() for r in review_responses]
                }
            else:
                console.print("[yellow]⚠ Code review requires fixes[/yellow]")
                return {
                    'success': True,
                    'next_state': WorkflowState.NEEDS_FIXES.value,
                    'review_responses': [r.dict() for r in review_responses]
                }

        except Exception as e:
            logger.error(f"Review stage failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _stage_fix_implementation(
        self,
        session: WorkflowSession,
        context: WorkflowContext,
        auto_mode: bool,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute fix implementation stage.

        Args:
            session: Workflow session
            context: Workflow context
            auto_mode: Automated mode
            dry_run: Dry run mode

        Returns:
            Stage result
        """
        console.print("\n[bold]🔧 Stage: Fix Implementation[/bold]")

        # Check iteration limit
        if session.iteration_count >= session.max_iterations:
            console.print(f"[red]✗ Maximum iterations ({session.max_iterations}) reached[/red]")
            session.current_state = WorkflowState.MAX_ITERATIONS_REACHED
            return {
                'success': False,
                'error': 'Maximum iterations reached',
                'next_state': WorkflowState.MAX_ITERATIONS_REACHED.value
            }

        # Increment iteration and go back to implementation
        session.iteration_count += 1

        return {
            'success': True,
            'next_state': WorkflowState.IMPLEMENTING.value
        }

    def _stage_finalization(
        self,
        session: WorkflowSession,
        context: WorkflowContext,
        auto_mode: bool,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Execute finalization stage.

        Args:
            session: Workflow session
            context: Workflow context
            auto_mode: Automated mode
            dry_run: Dry run mode

        Returns:
            Stage result
        """
        console.print("\n[bold]🏁 Stage: Finalization[/bold]")

        if dry_run:
            return {
                'success': True,
                'next_state': WorkflowState.READY_FOR_HUMAN.value
            }

        try:
            # TODO: Implement finalization steps:
            # 1. Squash commits
            # 2. Update PR description
            # 3. Run final checks
            # 4. Mark as ready for human review

            console.print("[green]✓ Issue ready for human review[/green]")

            return {
                'success': True,
                'next_state': WorkflowState.READY_FOR_HUMAN.value,
                'pr_url': f"https://github.com/{self.config.repo_owner}/{self.config.repo_name}/pull/{session.pr_number}"
            }

        except Exception as e:
            logger.error(f"Finalization stage failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _create_pull_request(self, session: WorkflowSession, context: WorkflowContext) -> PullRequest:
        """Create pull request for the issue.

        Args:
            session: Workflow session
            context: Workflow context

        Returns:
            Created pull request

        Raises:
            PlatformError: If PR creation fails
        """
        try:
            pr = self.platform_adapter.create_pull_request(
                owner=self.config.repo_owner,
                repo=self.config.repo_name,
                title=f"Fix issue #{session.issue_number}: {context.issue.title}",
                body=f"Automated fix for issue #{session.issue_number}\n\n{context.issue.body}",
                source_branch=session.branch_name,
                target_branch=self.config.base_branch
            )

            console.print(f"[green]✓ Created pull request #{pr.number}[/green]")
            return pr

        except Exception as e:
            raise PlatformError(
                f"Failed to create pull request: {str(e)}",
                platform=self.platform_adapter.name
            ) from e

    def _merge_review_feedback(self, review_responses: List[ReviewResponse]) -> ReviewDecision:
        """Merge feedback from multiple reviewers.

        Args:
            review_responses: List of review responses

        Returns:
            Merged review decision
        """
        if not review_responses:
            return ReviewDecision.COMMENT

        # Priority: REQUEST_CHANGES > APPROVE > COMMENT
        decisions = [response.decision for response in review_responses]

        if ReviewDecision.REQUEST_CHANGES in decisions:
            return ReviewDecision.REQUEST_CHANGES
        elif ReviewDecision.APPROVE in decisions:
            return ReviewDecision.APPROVE
        else:
            return ReviewDecision.COMMENT

    def _post_validation_comment(
        self,
        session: WorkflowSession,
        validation_response: ValidationResponse
    ) -> None:
        """Post validation comment to issue.

        Args:
            session: Workflow session
            validation_response: Validation response
        """
        comment_body = f"""## 🤖 Automated Validation Analysis

{validation_response.message}

"""
        if validation_response.clarifications_needed:
            comment_body += "### ❓ Clarifications Needed\n\n"
            for clarification in validation_response.clarifications_needed:
                comment_body += f"- {clarification}\n"

        if validation_response.suggestions:
            comment_body += "### 💡 Suggestions\n\n"
            for suggestion in validation_response.suggestions:
                comment_body += f"- {suggestion}\n"

        try:
            self.platform_adapter.add_issue_comment(
                self.config.repo_owner,
                self.config.repo_name,
                session.issue_number,
                comment_body
            )
            console.print("[green]✓ Validation comment posted[/green]")
        except Exception as e:
            logger.error(f"Failed to post validation comment: {str(e)}")

    def _confirm_continue(self, current_state: WorkflowState) -> bool:
        """Ask user for confirmation to continue.

        Args:
            current_state: Current workflow state

        Returns:
            True if user wants to continue
        """
        console.print(f"\n[yellow]Completed stage: {current_state.value}[/yellow]")
        response = console.input("Continue to next stage? [Y/n]: ").strip().lower()
        return response != 'n'

    def get_workflow_status(self, issue_number: int) -> Optional[Dict[str, Any]]:
        """Get workflow status for an issue.

        Args:
            issue_number: Issue number

        Returns:
            Workflow status or None if not found
        """
        if not self.state_manager:
            return None

        session = self.state_manager.get_workflow_session(issue_number)
        if not session:
            return None

        return {
            'issue_number': session.issue_number,
            'current_state': session.current_state.value,
            'iteration_count': session.iteration_count,
            'max_iterations': session.max_iterations,
            'pr_number': session.pr_number,
            'created_at': session.created_at,
            'updated_at': session.updated_at
        }

    def cleanup_workflow(self, issue_number: int, force: bool = False) -> bool:
        """Clean up workflow resources for an issue.

        Args:
            issue_number: Issue number
            force: Force cleanup even if workflow is active

        Returns:
            True if cleanup successful
        """
        try:
            if self.state_manager:
                session = self.state_manager.get_workflow_session(issue_number)
                if session:
                    # TODO: Clean up worktree
                    # TODO: Clean up temporary files
                    self.state_manager.delete_workflow_session(issue_number)
                    console.print(f"[green]✓ Cleaned up workflow for issue #{issue_number}[/green]")
                    return True

            return False

        except Exception as e:
            logger.error(f"Workflow cleanup failed: {str(e)}")
            return False
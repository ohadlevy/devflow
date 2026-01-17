"""Enhanced state management for DevFlow workflows.

This module provides sophisticated state persistence and tracking capabilities,
extracted and enhanced from the original embedded pipeline system.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Union

from platformdirs import user_data_dir
from pydantic import BaseModel, Field, validator

from devflow.core.config import ProjectConfig
from devflow.core.workflow_engine import WorkflowSession, WorkflowState
from devflow.exceptions import StateError, ValidationError

# Configure logging
logger = logging.getLogger(__name__)


class GlobalStatistics(BaseModel):
    """Global pipeline statistics."""

    total_workflows: int = 0
    active_workflows: int = 0
    completed_workflows: int = 0
    failed_workflows: int = 0
    total_iterations: int = 0
    avg_iterations_per_workflow: float = 0.0
    success_rate: float = 0.0
    last_calculated: str = Field(default_factory=lambda: datetime.now().isoformat())

    def calculate_derived_metrics(self) -> None:
        """Calculate derived metrics from base counters."""
        total_processed = self.completed_workflows + self.failed_workflows

        if total_processed > 0:
            self.success_rate = self.completed_workflows / total_processed
        else:
            self.success_rate = 0.0

        if self.completed_workflows > 0:
            self.avg_iterations_per_workflow = self.total_iterations / self.completed_workflows
        else:
            self.avg_iterations_per_workflow = 0.0

        self.last_calculated = datetime.now().isoformat()


class WorkflowHistory(BaseModel):
    """Represents a single workflow history entry."""

    timestamp: str
    state: str
    stage: Optional[str] = None
    iteration: int = 0
    agent_used: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("timestamp")
    def validate_timestamp(cls, v):
        """Validate timestamp format."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Invalid timestamp format")
        return v


class WorkflowError(BaseModel):
    """Represents a workflow error."""

    timestamp: str
    error_type: str
    error_message: str
    stage: Optional[str] = None
    iteration: int = 0
    agent_used: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    recovered: bool = False


class PipelineState(BaseModel):
    """Complete pipeline state structure."""

    version: str = "2.0"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())
    project_config: Optional[Dict[str, Any]] = None
    workflows: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    global_stats: GlobalStatistics = Field(default_factory=GlobalStatistics)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def update_timestamp(self) -> None:
        """Update the last_updated timestamp."""
        self.last_updated = datetime.now().isoformat()


class StateManager:
    """Enhanced state manager for DevFlow workflows.

    Provides sophisticated state persistence, tracking, and analytics
    with thread-safe operations and robust error handling.
    """

    def __init__(
        self, config: Optional[ProjectConfig] = None, state_file: Optional[Path] = None
    ) -> None:
        """Initialize the state manager.

        Args:
            config: Project configuration
            state_file: Custom state file path (optional)

        Raises:
            StateError: If state initialization fails
        """
        self.config = config
        self.state_file = state_file or self._get_default_state_file()

        # Thread safety
        self._lock = Lock()

        # Ensure state directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Load or initialize state
        self._state = self._load_state()

        # Store config in state if provided
        if config:
            self._state.project_config = config.get_effective_settings()
            self._save_state()

    def _get_default_state_file(self) -> Path:
        """Get default state file path.

        Returns:
            Default state file path
        """
        if self.config and self.config.state_file_path:
            return self.config.state_file_path

        # Use user data directory
        data_dir = Path(user_data_dir("devflow", appauthor=False))
        return data_dir / "pipeline_state.json"

    def _load_state(self) -> PipelineState:
        """Load state from file.

        Returns:
            Pipeline state

        Raises:
            StateError: If state loading fails critically
        """
        if not self.state_file.exists():
            logger.info("No existing state file found, initializing new state")
            return PipelineState()

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle legacy state format migration
            if data.get("version", "1.0") == "1.0":
                logger.info("Migrating legacy state format")
                return self._migrate_legacy_state(data)

            return PipelineState(**data)

        except json.JSONDecodeError as e:
            logger.error(f"Corrupted state file: {e}")
            backup_path = self.state_file.with_suffix(".json.backup")
            self.state_file.rename(backup_path)
            logger.info(f"Corrupted state backed up to: {backup_path}")
            return PipelineState()

        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            raise StateError(f"State loading failed: {str(e)}") from e

    def _migrate_legacy_state(self, legacy_data: Dict[str, Any]) -> PipelineState:
        """Migrate legacy state format to new format.

        Args:
            legacy_data: Legacy state data

        Returns:
            Migrated pipeline state
        """
        logger.info("Migrating legacy state format...")

        new_state = PipelineState()
        new_state.created_at = legacy_data.get("last_updated", datetime.now().isoformat())

        # Migrate issues to workflows
        legacy_issues = legacy_data.get("issues", {})
        for issue_key, issue_data in legacy_issues.items():
            try:
                # Convert legacy issue to workflow session
                session = WorkflowSession(
                    issue_id=f"issue-{issue_data['issue_number']}",
                    issue_number=issue_data["issue_number"],
                    current_state=WorkflowState(issue_data.get("state", "pending")),
                    iteration_count=issue_data.get("iteration_count", 0),
                    max_iterations=issue_data.get("max_iterations", 3),
                    worktree_path=(
                        Path(issue_data["worktree_path"])
                        if issue_data.get("worktree_path")
                        else None
                    ),
                    branch_name=issue_data.get("branch_name"),
                    pr_number=issue_data.get("pr_number"),
                    session_transcript=issue_data.get("validation_transcript", "") or "",
                    context_data={
                        "issue_title": issue_data.get("title", ""),
                        "issue_labels": issue_data.get("labels", []),
                        "legacy_history": issue_data.get("history", []),
                        "legacy_errors": issue_data.get("errors", []),
                    },
                    created_at=issue_data.get("created_at", datetime.now().isoformat()),
                    updated_at=datetime.now().isoformat(),
                )

                new_state.workflows[f"issue-{issue_data['issue_number']}"] = session.to_dict()

            except Exception as e:
                logger.warning(f"Failed to migrate issue {issue_key}: {e}")
                continue

        # Migrate global stats
        legacy_stats = legacy_data.get("global_stats", {})
        new_state.global_stats = GlobalStatistics(
            total_workflows=legacy_stats.get("total_issues", 0),
            completed_workflows=legacy_stats.get("completed", 0),
            failed_workflows=legacy_stats.get("failed", 0),
            active_workflows=legacy_stats.get("in_progress", 0),
        )
        new_state.global_stats.calculate_derived_metrics()

        logger.info(f"Migrated {len(new_state.workflows)} workflows from legacy format")
        return new_state

    def _save_state(self) -> None:
        """Save state to file with thread safety.

        Raises:
            StateError: If saving fails
        """
        with self._lock:
            try:
                self._state.update_timestamp()

                # Create atomic write by writing to temp file first
                temp_file = self.state_file.with_suffix(".tmp")

                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(self._state.dict(), f, indent=2, ensure_ascii=False, sort_keys=True)

                # Atomic replace
                temp_file.replace(self.state_file)

            except Exception as e:
                logger.error(f"Failed to save state: {e}")
                raise StateError(f"State saving failed: {str(e)}") from e

    def save_workflow_session(self, session: WorkflowSession) -> None:
        """Save workflow session to state.

        Args:
            session: Workflow session to save

        Raises:
            StateError: If saving fails
        """
        with self._lock:
            try:
                workflow_id = f"issue-{session.issue_number}"
                self._state.workflows[workflow_id] = session.to_dict()
                self._update_global_stats()
                self._save_state()

                logger.debug(f"Saved workflow session: {workflow_id}")

            except Exception as e:
                raise StateError(f"Failed to save workflow session: {str(e)}") from e

    def get_workflow_session(self, issue_number: int) -> Optional[WorkflowSession]:
        """Get workflow session by issue number.

        Args:
            issue_number: Issue number

        Returns:
            Workflow session or None if not found
        """
        with self._lock:
            workflow_id = f"issue-{issue_number}"
            workflow_data = self._state.workflows.get(workflow_id)

            if not workflow_data:
                return None

            try:
                return WorkflowSession.from_dict(workflow_data)
            except Exception as e:
                logger.error(f"Failed to deserialize workflow session {workflow_id}: {e}")
                return None

    def delete_workflow_session(self, issue_number: int) -> bool:
        """Delete workflow session.

        Args:
            issue_number: Issue number

        Returns:
            True if session was deleted
        """
        with self._lock:
            workflow_id = f"issue-{issue_number}"

            if workflow_id in self._state.workflows:
                del self._state.workflows[workflow_id]
                self._update_global_stats()
                self._save_state()
                logger.info(f"Deleted workflow session: {workflow_id}")
                return True

            return False

    def list_workflow_sessions(
        self, state_filter: Optional[WorkflowState] = None, limit: Optional[int] = None
    ) -> List[WorkflowSession]:
        """List workflow sessions with optional filtering.

        Args:
            state_filter: Filter by workflow state
            limit: Maximum number of sessions to return

        Returns:
            List of workflow sessions
        """
        with self._lock:
            sessions = []

            for workflow_data in self._state.workflows.values():
                try:
                    session = WorkflowSession.from_dict(workflow_data)

                    if state_filter and session.current_state != state_filter:
                        continue

                    sessions.append(session)

                except Exception as e:
                    logger.warning(f"Failed to deserialize workflow: {e}")
                    continue

            # Sort by updated timestamp (most recent first)
            sessions.sort(key=lambda s: s.updated_at, reverse=True)

            if limit:
                sessions = sessions[:limit]

            return sessions

    def add_workflow_history(
        self,
        issue_number: int,
        state: WorkflowState,
        stage: Optional[str] = None,
        iteration: int = 0,
        agent_used: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        error: Optional[str] = None,
        **metadata,
    ) -> None:
        """Add history entry to workflow.

        Args:
            issue_number: Issue number
            state: Workflow state
            stage: Stage description
            iteration: Current iteration
            agent_used: Agent that was used
            duration_seconds: Duration of this stage
            error: Error message if any
            **metadata: Additional metadata
        """
        with self._lock:
            workflow_id = f"issue-{issue_number}"

            if workflow_id not in self._state.workflows:
                logger.warning(f"Cannot add history to non-existent workflow: {workflow_id}")
                return

            workflow_data = self._state.workflows[workflow_id]

            if "history" not in workflow_data["context_data"]:
                workflow_data["context_data"]["history"] = []

            history_entry = WorkflowHistory(
                timestamp=datetime.now().isoformat(),
                state=state.value,
                stage=stage,
                iteration=iteration,
                agent_used=agent_used,
                duration_seconds=duration_seconds,
                error=error,
                metadata=metadata,
            )

            workflow_data["context_data"]["history"].append(history_entry.dict())
            self._save_state()

    def add_workflow_error(
        self,
        issue_number: int,
        error_type: str,
        error_message: str,
        stage: Optional[str] = None,
        iteration: int = 0,
        agent_used: Optional[str] = None,
        **context,
    ) -> None:
        """Add error to workflow.

        Args:
            issue_number: Issue number
            error_type: Type of error
            error_message: Error message
            stage: Stage where error occurred
            iteration: Current iteration
            agent_used: Agent that was used
            **context: Additional error context
        """
        with self._lock:
            workflow_id = f"issue-{issue_number}"

            if workflow_id not in self._state.workflows:
                logger.warning(f"Cannot add error to non-existent workflow: {workflow_id}")
                return

            workflow_data = self._state.workflows[workflow_id]

            if "errors" not in workflow_data["context_data"]:
                workflow_data["context_data"]["errors"] = []

            error_entry = WorkflowError(
                timestamp=datetime.now().isoformat(),
                error_type=error_type,
                error_message=error_message,
                stage=stage,
                iteration=iteration,
                agent_used=agent_used,
                context=context,
            )

            workflow_data["context_data"]["errors"].append(error_entry.dict())
            self._save_state()

    def get_workflow_history(self, issue_number: int) -> List[WorkflowHistory]:
        """Get workflow history.

        Args:
            issue_number: Issue number

        Returns:
            List of history entries
        """
        with self._lock:
            workflow_id = f"issue-{issue_number}"
            workflow_data = self._state.workflows.get(workflow_id, {})

            history_data = workflow_data.get("context_data", {}).get("history", [])

            try:
                return [WorkflowHistory(**entry) for entry in history_data]
            except Exception as e:
                logger.error(f"Failed to deserialize workflow history: {e}")
                return []

    def get_workflow_errors(self, issue_number: int) -> List[WorkflowError]:
        """Get workflow errors.

        Args:
            issue_number: Issue number

        Returns:
            List of error entries
        """
        with self._lock:
            workflow_id = f"issue-{issue_number}"
            workflow_data = self._state.workflows.get(workflow_id, {})

            error_data = workflow_data.get("context_data", {}).get("errors", [])

            try:
                return [WorkflowError(**entry) for entry in error_data]
            except Exception as e:
                logger.error(f"Failed to deserialize workflow errors: {e}")
                return []

    def _update_global_stats(self) -> None:
        """Update global statistics based on current workflows."""
        stats = GlobalStatistics()

        total_iterations = 0

        for workflow_data in self._state.workflows.values():
            try:
                state = WorkflowState(workflow_data["current_state"])
                iteration_count = workflow_data.get("iteration_count", 0)

                stats.total_workflows += 1
                total_iterations += iteration_count

                if state in [WorkflowState.COMPLETED, WorkflowState.MERGED]:
                    stats.completed_workflows += 1
                elif state in [
                    WorkflowState.VALIDATION_FAILED,
                    WorkflowState.IMPLEMENTATION_FAILED,
                    WorkflowState.REVIEW_FAILED,
                    WorkflowState.MAX_ITERATIONS_REACHED,
                    WorkflowState.NEEDS_HUMAN_INTERVENTION,
                ]:
                    stats.failed_workflows += 1
                else:
                    stats.active_workflows += 1

            except Exception as e:
                logger.warning(f"Failed to process workflow for stats: {e}")
                continue

        stats.total_iterations = total_iterations
        stats.calculate_derived_metrics()

        self._state.global_stats = stats

    def get_global_statistics(self) -> GlobalStatistics:
        """Get global statistics.

        Returns:
            Global statistics
        """
        with self._lock:
            self._update_global_stats()
            return self._state.global_stats.copy(deep=True)

    def get_workflow_analytics(self, days_back: int = 30) -> Dict[str, Any]:
        """Get workflow analytics for the specified period.

        Args:
            days_back: Number of days to analyze

        Returns:
            Analytics data
        """
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=days_back)
        cutoff_iso = cutoff_date.isoformat()

        with self._lock:
            analytics = {
                "period_days": days_back,
                "workflows_created": 0,
                "workflows_completed": 0,
                "avg_completion_time_hours": 0.0,
                "state_distribution": {},
                "error_types": {},
                "agent_usage": {},
                "success_rate_by_iteration": {},
            }

            completion_times = []
            state_counts = {}
            error_types = {}
            agent_usage = {}
            iteration_success = {}

            for workflow_data in self._state.workflows.values():
                try:
                    created_at = workflow_data.get("created_at", "")

                    if created_at < cutoff_iso:
                        continue

                    analytics["workflows_created"] += 1

                    state = workflow_data["current_state"]
                    state_counts[state] = state_counts.get(state, 0) + 1

                    if state in ["completed", "merged"]:
                        analytics["workflows_completed"] += 1

                        # Calculate completion time
                        try:
                            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            updated = datetime.fromisoformat(
                                workflow_data.get("updated_at", created_at).replace("Z", "+00:00")
                            )
                            completion_hours = (updated - created).total_seconds() / 3600
                            completion_times.append(completion_hours)
                        except Exception:
                            pass

                    # Analyze errors
                    errors = workflow_data.get("context_data", {}).get("errors", [])
                    for error in errors:
                        error_type = error.get("error_type", "unknown")
                        error_types[error_type] = error_types.get(error_type, 0) + 1

                    # Analyze agent usage
                    history = workflow_data.get("context_data", {}).get("history", [])
                    for entry in history:
                        agent = entry.get("agent_used")
                        if agent:
                            agent_usage[agent] = agent_usage.get(agent, 0) + 1

                    # Track success rate by iteration
                    iteration = workflow_data.get("iteration_count", 1)
                    if iteration not in iteration_success:
                        iteration_success[iteration] = {"total": 0, "successful": 0}

                    iteration_success[iteration]["total"] += 1
                    if state in ["completed", "merged"]:
                        iteration_success[iteration]["successful"] += 1

                except Exception as e:
                    logger.warning(f"Failed to process workflow for analytics: {e}")
                    continue

            # Calculate averages
            if completion_times:
                analytics["avg_completion_time_hours"] = sum(completion_times) / len(
                    completion_times
                )

            analytics["state_distribution"] = state_counts
            analytics["error_types"] = error_types
            analytics["agent_usage"] = agent_usage

            # Calculate success rates by iteration
            for iteration, data in iteration_success.items():
                if data["total"] > 0:
                    success_rate = data["successful"] / data["total"]
                    analytics["success_rate_by_iteration"][iteration] = {
                        "success_rate": success_rate,
                        "total_workflows": data["total"],
                        "successful_workflows": data["successful"],
                    }

            return analytics

    def export_state(self, export_path: Path, include_transcripts: bool = False) -> None:
        """Export state to file.

        Args:
            export_path: Path to export file
            include_transcripts: Whether to include session transcripts

        Raises:
            StateError: If export fails
        """
        try:
            with self._lock:
                export_data = self._state.dict()

                # Optionally exclude transcripts to reduce file size
                if not include_transcripts:
                    for workflow_data in export_data.get("workflows", {}).values():
                        workflow_data["session_transcript"] = "[EXCLUDED]"

                with open(export_path, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"State exported to: {export_path}")

        except Exception as e:
            raise StateError(f"Failed to export state: {str(e)}") from e

    def cleanup_completed_workflows(self, days_old: int = 30) -> int:
        """Clean up old completed workflows.

        Args:
            days_old: Remove workflows older than this many days

        Returns:
            Number of workflows cleaned up

        Raises:
            StateError: If cleanup fails
        """
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=days_old)
        cutoff_iso = cutoff_date.isoformat()

        with self._lock:
            workflows_to_remove = []

            for workflow_id, workflow_data in self._state.workflows.items():
                try:
                    state = workflow_data["current_state"]
                    updated_at = workflow_data.get("updated_at", "")

                    if state in ["completed", "merged"] and updated_at < cutoff_iso:
                        workflows_to_remove.append(workflow_id)

                except Exception as e:
                    logger.warning(f"Failed to process workflow {workflow_id} for cleanup: {e}")
                    continue

            # Remove identified workflows
            for workflow_id in workflows_to_remove:
                del self._state.workflows[workflow_id]

            if workflows_to_remove:
                self._update_global_stats()
                self._save_state()
                logger.info(f"Cleaned up {len(workflows_to_remove)} completed workflows")

            return len(workflows_to_remove)

    def validate_state_integrity(self) -> Dict[str, Any]:
        """Validate state file integrity.

        Returns:
            Validation results
        """
        results = {
            "valid": True,
            "issues": [],
            "warnings": [],
            "statistics": {"total_workflows": 0, "valid_workflows": 0, "corrupted_workflows": 0},
        }

        with self._lock:
            try:
                # Check state structure
                if not isinstance(self._state.dict(), dict):
                    results["issues"].append("State is not a valid dictionary")
                    results["valid"] = False

                # Check individual workflows
                for workflow_id, workflow_data in self._state.workflows.items():
                    results["statistics"]["total_workflows"] += 1

                    try:
                        # Try to deserialize workflow
                        WorkflowSession.from_dict(workflow_data)
                        results["statistics"]["valid_workflows"] += 1

                    except Exception as e:
                        results["statistics"]["corrupted_workflows"] += 1
                        results["warnings"].append(f"Workflow {workflow_id}: {str(e)}")

                # Check for orphaned references
                # TODO: Add more integrity checks as needed

            except Exception as e:
                results["issues"].append(f"State integrity check failed: {str(e)}")
                results["valid"] = False

        return results

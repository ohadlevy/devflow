"""Unit tests for workflow engine."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from devflow.adapters.base import Issue, IssueState
from devflow.agents.base import (
    ImplementationResponse,
    ImplementationResult,
    ReviewDecision,
    ReviewResponse,
    ValidationResponse,
    ValidationResult,
)
from devflow.core.config import (
    AgentConfig,
    PlatformConfig,
    ProjectConfig,
    ProjectMaturity,
    WorkflowConfig,
)
from devflow.core.state_manager import GlobalStatistics
from devflow.core.workflow_engine import WorkflowEngine, WorkflowSession, WorkflowState
from devflow.exceptions import WorkflowError


class TestWorkflowEngine:
    """Test WorkflowEngine functionality."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return ProjectConfig(
            project_name="test-workflow",
            project_root=Path.cwd(),
            repo_owner="test-owner",
            repo_name="test-repo",
            base_branch="main",
            maturity_level=ProjectMaturity.EARLY_STAGE,
            platforms=PlatformConfig(primary="github"),
            workflows=WorkflowConfig(max_iterations=3),
            agents=AgentConfig(primary="mock"),
        )

    @pytest.fixture
    def mock_platform_adapter(self):
        """Create mock platform adapter."""
        adapter = Mock()
        adapter.name = "mock_platform"
        adapter.validate_connection.return_value = True
        return adapter

    @pytest.fixture
    def mock_agent_coordinator(self):
        """Create mock agent coordinator."""
        coordinator = Mock()
        coordinator.validate_connection.return_value = True
        coordinator.agents = {"mock": Mock()}
        return coordinator

    @pytest.fixture
    def mock_state_manager(self):
        """Create mock state manager."""
        manager = Mock()
        manager.load_session.return_value = None
        manager.save_session.return_value = None
        return manager

    @pytest.fixture
    def workflow_engine(
        self, config, mock_platform_adapter, mock_agent_coordinator, mock_state_manager
    ):
        """Create workflow engine."""
        return WorkflowEngine(
            config=config,
            platform_adapter=mock_platform_adapter,
            agent_coordinator=mock_agent_coordinator,
            state_manager=mock_state_manager,
        )

    @pytest.fixture
    def mock_issue(self):
        """Create mock issue."""
        return Issue(
            id="test-issue-123",
            number=123,
            title="Test Issue",
            body="Test issue body",
            state=IssueState.OPEN,
            labels=["bug"],
            assignees=[],
            author="test-author",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            url="https://github.com/test-owner/test-repo/issues/123",
            platform_data={},
        )

    def test_workflow_engine_initialization(self, workflow_engine, config):
        """Test workflow engine initializes properly."""
        assert workflow_engine.config == config
        assert workflow_engine.platform_adapter is not None
        assert workflow_engine.agent_coordinator is not None
        assert workflow_engine.state_manager is not None

    def test_validate_environment_success(self, workflow_engine):
        """Test successful environment validation."""
        result = workflow_engine.validate_environment()
        assert result is True

    def test_validate_environment_platform_failure(self, workflow_engine):
        """Test environment validation with platform failure."""
        workflow_engine.platform_adapter.validate_connection.return_value = False

        result = workflow_engine.validate_environment()
        assert result is False

    def test_validate_environment_agent_failure(self, workflow_engine):
        """Test environment validation with agent failure."""
        workflow_engine.agent_coordinator.validate_connection.return_value = False

        result = workflow_engine.validate_environment()
        assert result is False

    def test_get_or_create_session_new(self, workflow_engine, mock_issue):
        """Test creating new session."""
        workflow_engine.platform_adapter.get_issue.return_value = mock_issue

        session = workflow_engine._get_or_create_session(123)

        assert session.issue_number == 123
        assert session.current_state == WorkflowState.PENDING
        assert session.iteration_count == 0
        assert session.context_data["issue_title"] == "Test Issue"

    def test_get_or_create_session_existing(self, workflow_engine, mock_state_manager):
        """Test loading existing session."""
        existing_session = WorkflowSession(
            issue_id="test-issue-123",
            issue_number=123,
            current_state=WorkflowState.IMPLEMENTING,
            iteration_count=1,
            max_iterations=3,
            worktree_path="/tmp/test",
            branch_name="devflow/issue-123",
            pr_number=None,
            session_transcript="Previous transcript",
            context_data={"issue_title": "Test Issue"},
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        mock_state_manager.load_session.return_value = existing_session

        session = workflow_engine._get_or_create_session(123)

        assert session.issue_number == 123
        assert session.current_state == WorkflowState.IMPLEMENTING
        assert session.iteration_count == 1

    def test_create_workflow_context(self, workflow_engine, mock_issue):
        """Test workflow context creation."""
        session = WorkflowSession(
            issue_id="test-issue-123",
            issue_number=123,
            current_state=WorkflowState.PENDING,
            iteration_count=0,
            max_iterations=3,
            worktree_path=None,
            branch_name=None,
            pr_number=None,
            session_transcript="",
            context_data={
                "issue_title": "Test Issue",
                "issue_body": "Test issue body",
                "issue_labels": ["bug"],
                "issue_url": "https://github.com/test-owner/test-repo/issues/123",
            },
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        context = workflow_engine._create_workflow_context(session)

        assert context.project_name == "test-workflow"
        assert context.issue.number == 123
        assert context.issue.title == "Test Issue"
        assert context.maturity_level == "early_stage"

    @patch("devflow.core.workflow_engine.datetime")
    def test_process_issue_dry_run(self, mock_datetime, workflow_engine, mock_issue):
        """Test issue processing in dry-run mode."""
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T00:00:00"
        workflow_engine.platform_adapter.get_issue.return_value = mock_issue

        # Mock validation response
        validation_response = ValidationResponse(
            success=True,
            result=ValidationResult.VALID,
            confidence=0.8,
            message="Issue is valid",
            estimated_complexity="SIMPLE",
            suggested_labels=["automated"],
        )

        # Mock agent selection
        mock_agent = Mock()
        mock_agent.validate_issue.return_value = validation_response
        workflow_engine.agent_coordinator.select_best_agent.return_value = mock_agent

        result = workflow_engine.process_issue(issue_number=123, auto_mode=True, dry_run=True)

        assert result["success"] is True
        assert result["issue_number"] == 123
        assert "stages_completed" in result

    def test_process_issue_validation_failure(self, workflow_engine, mock_issue):
        """Test issue processing with validation failure."""
        workflow_engine.platform_adapter.get_issue.return_value = mock_issue

        # Mock failed validation
        validation_response = ValidationResponse(
            success=True,
            result=ValidationResult.INVALID,
            confidence=0.9,
            message="Issue lacks detail",
            estimated_complexity="UNKNOWN",
            suggested_labels=["needs-more-info"],
        )

        mock_agent = Mock()
        mock_agent.validate_issue.return_value = validation_response
        workflow_engine.agent_coordinator.select_best_agent.return_value = mock_agent

        result = workflow_engine.process_issue(issue_number=123, auto_mode=True, dry_run=True)

        assert result["success"] is False
        assert "validation failed" in result["error"]

    def test_process_issue_implementation_success(self, workflow_engine, mock_issue):
        """Test successful issue implementation."""
        workflow_engine.platform_adapter.get_issue.return_value = mock_issue

        # Mock successful validation
        validation_response = ValidationResponse(
            success=True, result=ValidationResult.VALID, confidence=0.8, message="Issue is valid"
        )

        # Mock successful implementation
        implementation_response = ImplementationResponse(
            success=True,
            result=ImplementationResult.SUCCESS,
            confidence=0.9,
            message="Implementation completed",
            files_changed=["src/test.py", "tests/test_test.py"],
            tests_added=True,
        )

        mock_agent = Mock()
        mock_agent.validate_issue.return_value = validation_response
        mock_agent.implement_changes.return_value = implementation_response
        workflow_engine.agent_coordinator.select_best_agent.return_value = mock_agent

        result = workflow_engine.process_issue(issue_number=123, auto_mode=True, dry_run=True)

        assert result["success"] is True
        assert "implementation" in result["stages_completed"]

    def test_get_workflow_status_existing(self, workflow_engine, mock_state_manager):
        """Test getting status for existing workflow."""
        session = WorkflowSession(
            issue_id="test-issue-123",
            issue_number=123,
            current_state=WorkflowState.IMPLEMENTING,
            iteration_count=1,
            max_iterations=3,
            worktree_path="/tmp/test",
            branch_name="devflow/issue-123",
            pr_number=456,
            session_transcript="Test transcript",
            context_data={},
            created_at="2023-01-01T00:00:00",
            updated_at="2023-01-01T01:00:00",
        )

        mock_state_manager.load_session.return_value = session

        status = workflow_engine.get_workflow_status(123)

        assert status["issue_number"] == 123
        assert status["current_state"] == "implementing"
        assert status["iteration_count"] == 1
        assert status["pr_number"] == 456

    def test_get_workflow_status_nonexistent(self, workflow_engine):
        """Test getting status for nonexistent workflow."""
        status = workflow_engine.get_workflow_status(999)
        assert status is None

    def test_cleanup_workflow_success(self, workflow_engine, mock_state_manager):
        """Test successful workflow cleanup."""
        session = WorkflowSession(
            issue_id="test-issue-123",
            issue_number=123,
            current_state=WorkflowState.COMPLETED,
            iteration_count=2,
            max_iterations=3,
            worktree_path="/tmp/test",
            branch_name="devflow/issue-123",
            pr_number=None,
            session_transcript="",
            context_data={},
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        mock_state_manager.load_session.return_value = session
        mock_state_manager.cleanup_session.return_value = True

        result = workflow_engine.cleanup_workflow(123)
        assert result is True

    def test_cleanup_workflow_nonexistent(self, workflow_engine):
        """Test cleanup of nonexistent workflow."""
        result = workflow_engine.cleanup_workflow(999)
        assert result is False

    def test_get_statistics(self, workflow_engine, mock_state_manager):
        """Test getting workflow statistics."""
        mock_stats = GlobalStatistics(
            total_runs=10, successful_runs=8, failed_runs=2, average_processing_time=300.0
        )

        mock_state_manager.get_statistics.return_value = mock_stats

        stats = workflow_engine.get_statistics()

        assert stats.total_runs == 10
        assert stats.successful_runs == 8
        assert stats.failed_runs == 2
        assert stats.average_processing_time == 300.0

    def test_max_iterations_exceeded(self, workflow_engine, mock_issue, mock_state_manager):
        """Test handling of max iterations exceeded."""
        # Create session at max iterations
        session = WorkflowSession(
            issue_id="test-issue-123",
            issue_number=123,
            current_state=WorkflowState.IMPLEMENTING,
            iteration_count=3,  # At max
            max_iterations=3,
            worktree_path="/tmp/test",
            branch_name="devflow/issue-123",
            pr_number=None,
            session_transcript="Previous attempts",
            context_data={},
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        mock_state_manager.load_session.return_value = session
        workflow_engine.platform_adapter.get_issue.return_value = mock_issue

        result = workflow_engine.process_issue(issue_number=123, auto_mode=True, dry_run=True)

        assert result["success"] is False
        assert "maximum iterations" in result["error"]

    def test_workflow_error_handling(self, workflow_engine):
        """Test workflow error handling."""
        # Mock platform adapter failure
        workflow_engine.platform_adapter.get_issue.side_effect = Exception("Platform error")

        result = workflow_engine.process_issue(issue_number=123, auto_mode=True, dry_run=True)

        assert result["success"] is False
        assert "Platform error" in result["error"]

    @patch("devflow.core.workflow_engine.console")
    def test_validation_stage_streaming_progress(self, mock_console, workflow_engine, mock_issue):
        """Test validation stage with streaming progress indicators."""
        # Create session and context objects
        from datetime import datetime

        from devflow.agents.base import WorkflowContext
        from devflow.core.workflow_engine import WorkflowSession, WorkflowState

        session = WorkflowSession(
            issue_id="test-issue-123",
            issue_number=123,
            current_state=WorkflowState.VALIDATING,
            iteration_count=0,
            max_iterations=3,
            worktree_path=None,
            branch_name=None,
            pr_number=None,
            session_transcript="",
            context_data={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        context = WorkflowContext(
            project_name="test-project",
            repository_url="https://github.com/test/repo",
            base_branch="main",
            working_directory="/tmp/test",
            issue=mock_issue,
            maturity_level="early_stage",
        )

        # Mock agent coordinator to return an agent with streaming capability
        mock_agent = Mock()
        mock_agent.validate_issue_stream.return_value = iter(
            [
                "🔍 Starting issue analysis...",
                "📖 Reading project context and issue details...",
                "💭 Analyzing requirements... (10 lines processed)",
                "🎯 Evaluating issue requirements...",
                "⚙️ Assessing implementation feasibility...",
                "✅ Analysis complete, processing results...",
                "🎉 Validation passed - issue is ready for implementation",
                ValidationResponse(
                    success=True,
                    message="Validation completed successfully",
                    data={},
                    result=ValidationResult.VALID,
                    confidence=0.9,
                ),
            ]
        )

        workflow_engine.agent_coordinator.select_best_agent.return_value = mock_agent
        workflow_engine.platform_adapter.add_labels_to_issue = Mock()

        # Run validation stage
        result = workflow_engine._stage_validation(session, context, auto_mode=False, dry_run=False)

        # Verify that streaming messages were printed
        mock_console.print.assert_any_call("Running AI validation...")
        mock_console.print.assert_any_call("  🔍 Starting issue analysis...", style="dim")
        mock_console.print.assert_any_call(
            "  📖 Reading project context and issue details...", style="dim"
        )
        mock_console.print.assert_any_call(
            "  💭 Analyzing requirements... (10 lines processed)", style="dim"
        )
        mock_console.print.assert_any_call("  🎯 Evaluating issue requirements...", style="dim")
        mock_console.print.assert_any_call(
            "  ⚙️ Assessing implementation feasibility...", style="dim"
        )
        mock_console.print.assert_any_call(
            "  ✅ Analysis complete, processing results...", style="dim"
        )
        mock_console.print.assert_any_call(
            "  🎉 Validation passed - issue is ready for implementation", style="dim"
        )

        # Verify final validation success message
        mock_console.print.assert_any_call("[green]✓ Issue validation passed[/green]")

        # Verify result
        assert result["success"] is True
        assert result["next_state"] == WorkflowState.AWAITING_APPROVAL.value

    @patch("devflow.core.workflow_engine.console")
    def test_validation_stage_fallback_to_non_streaming(
        self, mock_console, workflow_engine, mock_issue
    ):
        """Test validation stage fallback to non-streaming when streaming not available."""
        # Create session and context objects
        from datetime import datetime

        from devflow.agents.base import WorkflowContext
        from devflow.core.workflow_engine import WorkflowSession, WorkflowState

        session = WorkflowSession(
            issue_id="test-issue-123",
            issue_number=123,
            current_state=WorkflowState.VALIDATING,
            iteration_count=0,
            max_iterations=3,
            worktree_path=None,
            branch_name=None,
            pr_number=None,
            session_transcript="",
            context_data={},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        context = WorkflowContext(
            project_name="test-project",
            repository_url="https://github.com/test/repo",
            base_branch="main",
            working_directory="/tmp/test",
            issue=mock_issue,
            maturity_level="early_stage",
        )

        # Mock agent coordinator to return an agent WITHOUT streaming capability
        mock_agent = Mock()
        # Remove the streaming method to simulate older agent
        (
            delattr(mock_agent, "validate_issue_stream")
            if hasattr(mock_agent, "validate_issue_stream")
            else None
        )

        mock_agent.validate_issue.return_value = ValidationResponse(
            success=True,
            message="Validation completed successfully",
            data={},
            result=ValidationResult.VALID,
            confidence=0.9,
        )

        workflow_engine.agent_coordinator.select_best_agent.return_value = mock_agent
        workflow_engine.platform_adapter.add_labels_to_issue = Mock()

        # Run validation stage
        result = workflow_engine._stage_validation(session, context, auto_mode=False, dry_run=False)

        # Verify that regular validation was used (no streaming messages)
        mock_console.print.assert_any_call("Running AI validation...")
        mock_console.print.assert_any_call("[green]✓ Issue validation passed[/green]")

        # Should not have any streaming progress messages
        streaming_calls = [
            call
            for call in mock_console.print.call_args_list
            if len(call[0]) > 0 and call[0][0].startswith("  ")
        ]
        assert len(streaming_calls) == 0

        # Verify result
        assert result["success"] is True


class TestWorkflowSession:
    """Test WorkflowSession data model."""

    def test_session_creation(self):
        """Test creating a workflow session."""
        session = WorkflowSession(
            issue_id="test-issue-123",
            issue_number=123,
            current_state=WorkflowState.PENDING,
            iteration_count=0,
            max_iterations=3,
            worktree_path=None,
            branch_name=None,
            pr_number=None,
            session_transcript="",
            context_data={},
            created_at="2023-01-01T00:00:00",
            updated_at="2023-01-01T00:00:00",
        )

        assert session.issue_number == 123
        assert session.current_state == WorkflowState.PENDING
        assert session.iteration_count == 0

    def test_session_state_transitions(self):
        """Test workflow state transitions."""
        session = WorkflowSession(
            issue_id="test-issue-123",
            issue_number=123,
            current_state=WorkflowState.PENDING,
            iteration_count=0,
            max_iterations=3,
            worktree_path=None,
            branch_name=None,
            pr_number=None,
            session_transcript="",
            context_data={},
            created_at="2023-01-01T00:00:00",
            updated_at="2023-01-01T00:00:00",
        )

        # Test state progression
        session.current_state = WorkflowState.VALIDATING
        assert session.current_state == WorkflowState.VALIDATING

        session.current_state = WorkflowState.IMPLEMENTING
        assert session.current_state == WorkflowState.IMPLEMENTING

        session.current_state = WorkflowState.COMPLETED
        assert session.current_state == WorkflowState.COMPLETED


class TestGlobalStatistics:
    """Test GlobalStatistics data model."""

    def test_statistics_creation(self):
        """Test creating global statistics."""
        stats = GlobalStatistics(
            total_runs=15, successful_runs=12, failed_runs=3, average_processing_time=450.0
        )

        assert stats.total_runs == 15
        assert stats.successful_runs == 12
        assert stats.failed_runs == 3
        assert stats.average_processing_time == 450.0

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        stats = GlobalStatistics(
            total_runs=10, successful_runs=8, failed_runs=2, average_processing_time=300.0
        )

        # Calculate success rate (not implemented in the model but could be)
        success_rate = stats.successful_runs / stats.total_runs
        assert success_rate == 0.8

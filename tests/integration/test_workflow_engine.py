"""Integration tests for the workflow engine."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from devflow.adapters.git.basic import BasicGitAdapter
from devflow.agents.base import MultiAgentCoordinator
from devflow.agents.mock import MockAgentProvider
from devflow.core.config import (
    AgentConfig,
    PlatformConfig,
    ProjectConfig,
    ProjectMaturity,
    WorkflowConfig,
)
from devflow.core.state_manager import StateManager
from devflow.core.workflow_engine import WorkflowEngine, WorkflowState


class TestWorkflowEngine:
    """Test workflow engine integration."""

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
            workflows=WorkflowConfig(),
            agents=AgentConfig(primary="mock", claude_model="claude-3.5-sonnet"),
        )

    @pytest.fixture
    def platform_adapter(self, config):
        """Create platform adapter."""
        adapter_config = {
            "repo_owner": config.repo_owner,
            "repo_name": config.repo_name,
            "project_root": str(config.project_root),
        }
        return BasicGitAdapter(adapter_config)

    @pytest.fixture
    def agent_coordinator(self):
        """Create agent coordinator."""
        mock_config = {"mock_mode": True, "simulate_failures": False}
        mock_agent = MockAgentProvider(mock_config)
        return MultiAgentCoordinator([mock_agent])

    @pytest.fixture
    def state_manager(self, config):
        """Create state manager."""
        return StateManager(config)

    @pytest.fixture
    def workflow_engine(self, config, platform_adapter, agent_coordinator, state_manager):
        """Create workflow engine."""
        return WorkflowEngine(
            config=config,
            platform_adapter=platform_adapter,
            agent_coordinator=agent_coordinator,
            state_manager=state_manager,
        )

    def test_workflow_engine_initialization(self, workflow_engine):
        """Test workflow engine initializes properly."""
        assert workflow_engine is not None
        assert workflow_engine.config.project_name == "test-workflow"
        assert workflow_engine.platform_adapter.name == "basic_git"
        assert len(workflow_engine.agent_coordinator.agents) == 1

    def test_environment_validation(self, workflow_engine):
        """Test environment validation."""
        # Should pass with mock components
        assert workflow_engine.validate_environment() is True

    def test_get_or_create_session(self, workflow_engine):
        """Test session creation."""
        issue_number = 123

        # Mock the platform adapter to return a test issue
        mock_issue = Mock()
        mock_issue.id = "test-issue-123"
        mock_issue.title = "Test Issue"
        mock_issue.body = "Test issue body"
        mock_issue.labels = ["bug"]
        mock_issue.url = "https://github.com/test-owner/test-repo/issues/123"

        workflow_engine.platform_adapter.get_issue = Mock(return_value=mock_issue)

        session = workflow_engine._get_or_create_session(issue_number)

        assert session.issue_number == issue_number
        assert session.current_state == WorkflowState.PENDING
        assert session.iteration_count == 0
        assert session.context_data["issue_title"] == "Test Issue"

    def test_workflow_context_creation(self, workflow_engine):
        """Test workflow context creation."""
        # Create a mock session
        from datetime import datetime

        from devflow.core.workflow_engine import WorkflowSession

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
    def test_process_issue_dry_run(self, mock_datetime, workflow_engine):
        """Test issue processing in dry-run mode."""
        # Mock datetime
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T00:00:00"

        # Mock the platform adapter
        mock_issue = Mock()
        mock_issue.id = "test-issue-456"
        mock_issue.title = "Test Dry Run Issue"
        mock_issue.body = "Test issue for dry run"
        mock_issue.labels = ["enhancement"]
        mock_issue.url = "https://github.com/test-owner/test-repo/issues/456"

        workflow_engine.platform_adapter.get_issue = Mock(return_value=mock_issue)

        # Process issue in dry-run mode
        result = workflow_engine.process_issue(issue_number=456, auto_mode=True, dry_run=True)

        assert result["success"] is True
        assert result["issue_number"] == 456
        assert "stages_completed" in result

    def test_workflow_status(self, workflow_engine):
        """Test getting workflow status."""
        # When no session exists, should return None
        status = workflow_engine.get_workflow_status(999)
        assert status is None

    def test_cleanup_workflow(self, workflow_engine):
        """Test workflow cleanup."""
        # Should handle non-existent workflow gracefully
        result = workflow_engine.cleanup_workflow(999)
        assert result is False

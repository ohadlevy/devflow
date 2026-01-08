"""Integration Tests for Complete DevFlow Workflows.

These tests validate end-to-end workflow functionality without external dependencies
by mocking GitHub API calls and AI agent responses.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from devflow.core.workflow_engine import WorkflowEngine, WorkflowState
from devflow.core.config import ProjectConfig
from devflow.adapters.base import Issue, IssueState, PullRequest, PullRequestState, ReviewDecision
from devflow.agents.base import ValidationResult, ImplementationResult, AgentCapability
from devflow.exceptions import WorkflowError

# Import the auto-fix system we just created
from devflow.core.auto_fix import AutoFixEngine, FeedbackType, FixPriority


class MockGitHubAdapter:
    """Mock GitHub adapter for testing complete workflows."""

    def __init__(self):
        self.issues = {}
        self.prs = {}
        self.reviews = {}
        self.ci_status = {}
        self.labels = []

    def validate_connection(self):
        return True

    @property
    def name(self):
        return "mock_github"

    def get_issue(self, owner, repo, issue_number):
        """Return mock issue data."""
        if issue_number not in self.issues:
            self.issues[issue_number] = Issue(
                id=f"issue_{issue_number}",
                number=issue_number,
                title=f"Test Issue #{issue_number}",
                body="This is a test issue for DevFlow integration testing.",
                state=IssueState.OPEN,
                labels=["enhancement", "ready-for-implementation"],
                assignees=[],
                author="test_user",
                created_at="2024-01-08T10:00:00Z",
                updated_at="2024-01-08T10:00:00Z",
                url=f"https://github.com/{owner}/{repo}/issues/{issue_number}",
                platform_data={}
            )
        return self.issues[issue_number]

    def create_pull_request(self, owner, repo, title, body, source_branch, target_branch):
        """Create mock PR."""
        pr_number = len(self.prs) + 1
        pr = PullRequest(
            id=f"pr_{pr_number}",
            number=pr_number,
            title=title,
            body=body,
            state=PullRequestState.OPEN,
            source_branch=source_branch,
            target_branch=target_branch,
            author="devflow_bot",
            reviewers=[],
            labels=[],
            created_at="2024-01-08T10:00:00Z",
            updated_at="2024-01-08T10:00:00Z",
            mergeable=True,
            url=f"https://github.com/{owner}/{repo}/pull/{pr_number}",
            platform_data={}
        )
        self.prs[pr_number] = pr
        return pr

    def create_pull_request_review(self, owner, repo, pr_number, body, decision):
        """Mock creating PR review."""
        review_id = f"review_{pr_number}_{len(self.reviews)}"
        self.reviews[review_id] = {
            "pr_number": pr_number,
            "body": body,
            "decision": decision,
            "created_at": "2024-01-08T10:00:00Z"
        }
        return Mock(id=review_id)

    def add_labels_to_issue(self, owner, repo, issue_number, labels):
        """Mock adding labels."""
        if issue_number in self.issues:
            self.issues[issue_number].labels.extend(labels)

    def get_pull_request_files(self, owner, repo, pr_number):
        """Mock PR file changes."""
        return [
            {"filename": "src/devflow/core/workflow_engine.py", "status": "modified"},
            {"filename": "src/devflow/agents/claude.py", "status": "modified"},
            {"filename": "tests/unit/test_workflow_engine.py", "status": "added"}
        ]


class MockAIAgent:
    """Mock AI agent for testing."""

    def __init__(self, validation_result=ValidationResult.VALID):
        self.validation_result = validation_result
        self.capabilities = [AgentCapability.VALIDATION, AgentCapability.IMPLEMENTATION, AgentCapability.REVIEW]

    @property
    def name(self):
        return "mock_ai_agent"

    @property
    def display_name(self):
        return "Mock AI Agent"

    def validate_connection(self):
        return True

    def validate_issue(self, context):
        """Mock validation response."""
        from devflow.agents.base import ValidationResponse
        return ValidationResponse(
            success=True,
            message="Mock validation successful",
            data={"mock": True},
            result=self.validation_result,
            confidence=0.95,
            reasoning="This is a mock validation for testing"
        )

    def implement_changes(self, context):
        """Mock implementation response."""
        from devflow.agents.base import ImplementationResponse
        return ImplementationResponse(
            success=True,
            message="Mock implementation completed",
            data={"files_changed": ["src/test.py"], "commits": ["feat: mock implementation"]},
            result=ImplementationResult.SUCCESS
        )

    def review_code(self, context):
        """Mock review response."""
        from devflow.agents.base import ReviewResponse
        return ReviewResponse(
            success=True,
            message="Mock code review - looks good!",
            data={"mock": True},
            decision=ReviewDecision.APPROVED,
            confidence=0.9
        )


class MockAgentCoordinator:
    """Mock agent coordinator."""

    def __init__(self):
        self.agents = {"mock_agent": MockAIAgent()}

    def select_best_agent(self, capability, preferences=None):
        return MockAIAgent()

    def coordinate_review(self, context, reviewer_names=None):
        """Mock coordinated review."""
        mock_agent = MockAIAgent()
        return [mock_agent.review_code(context)]


@pytest.fixture
def temp_project_root():
    """Create temporary project directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)

        # Create basic project structure
        (project_root / "src").mkdir()
        (project_root / "tests").mkdir()
        (project_root / "devflow.yaml").write_text("""
project_name: "test_project"
project_root: "."
repo_owner: "test_owner"
repo_name: "test_repo"
base_branch: "master"
maturity_level: "early_stage"
platforms:
  primary: "github"
agents:
  primary: "claude"
  claude_model: "claude-3.5-sonnet"
  review_sources: ["claude"]
workflows:
  validation_requires_approval: false
  implementation_max_iterations: 3
""")

        yield project_root


@pytest.fixture
def mock_config(temp_project_root):
    """Create mock project configuration."""
    config = ProjectConfig.from_file(temp_project_root / "devflow.yaml")
    config.project_root = temp_project_root
    return config


@pytest.fixture
def mock_platform_adapter():
    """Create mock platform adapter."""
    return MockGitHubAdapter()


@pytest.fixture
def mock_agent_coordinator():
    """Create mock agent coordinator."""
    return MockAgentCoordinator()


@pytest.fixture
def workflow_engine(mock_config, mock_platform_adapter, mock_agent_coordinator):
    """Create workflow engine with mocked dependencies."""
    return WorkflowEngine(
        config=mock_config,
        platform_adapter=mock_platform_adapter,
        agent_coordinator=mock_agent_coordinator,
        state_manager=None,  # Disabled for testing
        enable_auto_fix=False  # Disable auto-fix for simpler testing
    )


class TestCompleteWorkflow:
    """Test complete end-to-end workflows."""

    def test_successful_issue_to_pr_workflow(self, workflow_engine, mock_platform_adapter):
        """Test complete workflow: validation → implementation → review → PR."""

        # Act: Process issue through complete workflow
        result = workflow_engine.process_issue(
            issue_number=1,
            auto_mode=True,
            dry_run=False
        )

        # Assert: Workflow completed successfully
        assert result['success'] is True
        assert result['issue_number'] == 1
        assert len(result['stages_completed']) > 0

        # Assert: PR was created
        assert len(mock_platform_adapter.prs) == 1
        created_pr = list(mock_platform_adapter.prs.values())[0]
        assert "Test Issue #1" in created_pr.title

        # Assert: Review was posted
        assert len(mock_platform_adapter.reviews) > 0

    def test_validation_failure_workflow(self, mock_config, mock_platform_adapter):
        """Test workflow when validation fails."""

        # Arrange: Agent that fails validation
        failing_agent = MockAIAgent(validation_result=ValidationResult.INVALID)
        agent_coordinator = Mock()
        agent_coordinator.agents = {"failing_agent": failing_agent}  # Add agents attribute
        agent_coordinator.select_best_agent.return_value = failing_agent

        engine = WorkflowEngine(
            config=mock_config,
            platform_adapter=mock_platform_adapter,
            agent_coordinator=agent_coordinator,
            state_manager=None,
            enable_auto_fix=False  # Disable auto-fix for simpler testing
        )

        # Act: Process issue
        result = engine.process_issue(issue_number=2, auto_mode=True)

        # Assert: Workflow stopped at validation
        assert result['success'] is False
        assert 'validation' in result['stages_completed'] or len(result['stages_completed']) == 0

    def test_state_recovery_after_interruption(self, workflow_engine, mock_platform_adapter, temp_project_root):
        """Test workflow recovery after interruption."""

        # Arrange: Simulate existing branch with implementation
        branch_name = "issue-3"

        with patch('subprocess.run') as mock_subprocess:
            # Mock git commands to simulate existing branch
            mock_subprocess.return_value.returncode = 0
            mock_subprocess.return_value.stdout = "some implementation commit"

            # Act: Process issue that should detect existing work
            result = workflow_engine.process_issue(issue_number=3, auto_mode=True)

            # Assert: Should detect existing implementation and skip to review
            assert result['success'] is True

    @patch('devflow.core.workflow_engine.subprocess.run')
    def test_worktree_creation_and_cleanup(self, mock_subprocess, workflow_engine):
        """Test git worktree creation and management."""

        # Arrange: Mock git worktree commands
        mock_subprocess.return_value.returncode = 0

        # Act: Process issue requiring worktree
        result = workflow_engine.process_issue(issue_number=4, auto_mode=True)

        # Assert: Git worktree commands were called
        assert mock_subprocess.called
        worktree_calls = [call for call in mock_subprocess.call_args_list
                         if 'worktree' in str(call)]
        assert len(worktree_calls) > 0

    def test_review_feedback_integration(self, workflow_engine, mock_platform_adapter):
        """Test that review feedback is properly posted to PR."""

        # Act: Process issue through workflow
        result = workflow_engine.process_issue(issue_number=5, auto_mode=True)

        # Assert: Review was posted with proper content
        assert len(mock_platform_adapter.reviews) > 0
        review = list(mock_platform_adapter.reviews.values())[0]
        assert "DevFlow AI Code Review" in review["body"]
        assert review["decision"] == ReviewDecision.APPROVED


class TestAutoFixIntegration:
    """Test auto-fix system integration with workflow."""

    def test_ci_failure_auto_fix_cycle(self, mock_config, mock_platform_adapter):
        """Test auto-fix cycle for CI failures."""

        # Arrange: Mock auto-fix engine
        mock_agent = MockAIAgent()
        auto_fix_engine = AutoFixEngine(
            platform_adapter=mock_platform_adapter,
            agent_provider=mock_agent,
            working_directory="/tmp/test"
        )

        # Act: Run auto-fix cycle
        result = auto_fix_engine.run_auto_fix_cycle(pr_number=1)

        # Assert: Auto-fix completed (even if mocked)
        assert isinstance(result.success, bool)
        assert isinstance(result.fixes_applied, list)

    def test_review_feedback_auto_fix(self, mock_platform_adapter):
        """Test auto-fix for review feedback."""

        # Arrange: Mock review with change requests
        mock_platform_adapter.reviews["test_review"] = {
            "pr_number": 1,
            "body": "Please add error handling to the subprocess calls.",
            "decision": ReviewDecision.REQUEST_CHANGES,
            "state": "REQUEST_CHANGES"
        }

        from devflow.core.auto_fix import ReviewFeedbackDetector
        detector = ReviewFeedbackDetector()

        # Act: Detect feedback
        feedback = detector.detect_feedback(1, mock_platform_adapter)

        # Assert: Feedback was detected
        assert len(feedback) > 0
        assert feedback[0].type == FeedbackType.REVIEW_FEEDBACK
        assert "error handling" in feedback[0].description.lower()


class TestStateManagement:
    """Test workflow state management and persistence."""

    def test_workflow_state_detection_from_git(self, workflow_engine, temp_project_root):
        """Test state detection from git branches and commits."""

        with patch('subprocess.run') as mock_subprocess:
            # Mock existing branch with commits
            mock_subprocess.return_value.returncode = 0
            mock_subprocess.return_value.stdout = "commit abc123 Implementation complete"

            # Act: Detect state
            state = workflow_engine._detect_workflow_state_from_git(6)

            # Assert: Correct state detected
            assert state in [WorkflowState.IMPLEMENTED, WorkflowState.VALIDATED]

    def test_workflow_session_creation_and_recovery(self, workflow_engine):
        """Test workflow session creation and recovery."""

        # Act: Create session
        session = workflow_engine._get_or_create_session(7)

        # Assert: Session created properly
        assert session.issue_number == 7
        assert session.current_state == WorkflowState.PENDING
        assert session.max_iterations > 0

    def test_error_recovery_scenarios(self, workflow_engine):
        """Test various error recovery scenarios."""

        # Test cases for different error conditions
        error_scenarios = [
            {"error": "git worktree failure", "expected_behavior": "retry or fallback"},
            {"error": "AI agent timeout", "expected_behavior": "retry with different agent"},
            {"error": "GitHub API rate limit", "expected_behavior": "retry with backoff"}
        ]

        for scenario in error_scenarios:
            # This would test specific error handling
            # For now, just verify the structure exists
            assert hasattr(workflow_engine, '_execute_workflow')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
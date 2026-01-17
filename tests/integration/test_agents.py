"""Integration tests for AI agents."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from devflow.adapters.base import Issue, IssueState, PullRequest, PullRequestState
from devflow.agents.base import (
    AgentCapability,
    ImplementationContext,
    ImplementationResult,
    IssueSeverity,
    MultiAgentCoordinator,
    ReviewContext,
    ReviewDecision,
    ValidationContext,
    ValidationResult,
    WorkflowContext,
)
from devflow.agents.mock import MockAgentProvider
from devflow.exceptions import AgentError, ValidationError


class TestMockAgentProvider:
    """Test MockAgentProvider functionality."""

    @pytest.fixture
    def agent(self):
        """Create mock agent."""
        config = {"mock_mode": True, "simulate_failures": False}
        return MockAgentProvider(config)

    @pytest.fixture
    def failing_agent(self):
        """Create mock agent that simulates failures."""
        config = {"mock_mode": True, "simulate_failures": True}
        return MockAgentProvider(config)

    @pytest.fixture
    def mock_issue(self):
        """Create mock issue for testing."""
        return Issue(
            id="test-issue-123",
            number=123,
            title="Test Issue for AI Processing",
            body="This is a test issue with sufficient detail for the AI agent to analyze.",
            state=IssueState.OPEN,
            labels=["bug", "enhancement"],
            assignees=[],
            author="test-user",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            url="https://github.com/test/repo/issues/123",
            platform_data={"test": True},
        )

    @pytest.fixture
    def mock_pr(self):
        """Create mock pull request for testing."""
        return PullRequest(
            id="test-pr-456",
            number=456,
            title="Test Pull Request",
            body="Test PR for review",
            state=PullRequestState.OPEN,
            source_branch="feature/test",
            target_branch="main",
            author="test-user",
            reviewers=[],
            labels=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            mergeable=True,
            url="https://github.com/test/repo/pull/456",
            platform_data={"test": True},
        )

    def test_agent_initialization(self, agent):
        """Test agent initializes properly."""
        assert agent.name == "mock"
        assert agent.display_name == "Mock Agent"
        assert agent.mock_mode is True
        assert agent.simulate_failures is False

    def test_agent_capabilities(self, agent):
        """Test agent capabilities."""
        capabilities = agent.capabilities
        assert AgentCapability.VALIDATION in capabilities
        assert AgentCapability.IMPLEMENTATION in capabilities
        assert AgentCapability.REVIEW in capabilities
        assert AgentCapability.ANALYSIS in capabilities
        assert AgentCapability.DOCUMENTATION in capabilities

    def test_validate_connection(self, agent, failing_agent):
        """Test connection validation."""
        assert agent.validate_connection() is True
        assert failing_agent.validate_connection() is False

    def test_supports_capability(self, agent):
        """Test capability checking."""
        assert agent.supports_capability(AgentCapability.VALIDATION) is True
        assert agent.supports_capability(AgentCapability.IMPLEMENTATION) is True

    def test_max_context_size(self, agent):
        """Test context size property."""
        assert agent.max_context_size == 100000

    def test_validate_issue_success(self, agent, mock_issue):
        """Test successful issue validation."""
        context = ValidationContext(
            issue=mock_issue,
            project_context={"maturity_level": "early_stage"},
            maturity_level="early_stage",
            previous_attempts=[],
        )

        response = agent.validate_issue(context)

        assert response.success is True
        assert response.result == ValidationResult.VALID
        assert response.confidence == 0.8
        assert "Mock Validation Analysis" in response.message
        assert response.estimated_complexity in ["SIMPLE", "MEDIUM", "COMPLEX"]
        assert "automated" in response.suggested_labels

    def test_validate_issue_failure(self, failing_agent, mock_issue):
        """Test failed issue validation."""
        context = ValidationContext(
            issue=mock_issue,
            project_context={"maturity_level": "early_stage"},
            maturity_level="early_stage",
        )

        response = failing_agent.validate_issue(context)

        assert response.success is False
        assert response.result == ValidationResult.INVALID
        assert response.confidence == 0.0

    def test_implement_changes_success(self, agent, mock_issue):
        """Test successful implementation."""
        context = ImplementationContext(
            issue=mock_issue,
            working_directory="/tmp/test",
            project_context={"maturity_level": "early_stage"},
            validation_result={},
            previous_iterations=[],
            constraints={"max_iterations": 3, "current_iteration": 1},
        )

        response = agent.implement_changes(context)

        assert response.success is True
        assert response.result == ImplementationResult.SUCCESS
        assert response.confidence == 0.9
        assert len(response.files_changed) == 2
        assert "src/mock_feature.py" in response.files_changed
        assert response.tests_added is True

    def test_implement_changes_failure(self, failing_agent, mock_issue):
        """Test failed implementation."""
        context = ImplementationContext(
            issue=mock_issue,
            working_directory="/tmp/test",
            project_context={},
            validation_result={},
            previous_iterations=[],
        )

        response = failing_agent.implement_changes(context)

        assert response.success is False
        assert response.result == ImplementationResult.FAILED
        assert response.confidence == 0.0

    def test_review_code_success(self, agent, mock_pr):
        """Test successful code review."""
        changed_files = [
            {"filename": "src/test.py", "status": "modified"},
            {"filename": "tests/test_test.py", "status": "added"},
        ]

        context = ReviewContext(
            pull_request=mock_pr,
            changed_files=changed_files,
            project_context={"maturity_level": "early_stage"},
            maturity_level="early_stage",
            review_focus=["correctness", "maintainability"],
        )

        response = agent.review_code(context)

        assert response.success is True
        assert response.decision == ReviewDecision.APPROVE
        assert response.severity == IssueSeverity.INFO
        assert response.confidence == 0.8
        assert "Mock Code Review" in response.message

    def test_review_code_large_changeset(self, agent, mock_pr):
        """Test code review with large changeset."""
        # Create many changed files to trigger REQUEST_CHANGES
        changed_files = [{"filename": f"src/file_{i}.py", "status": "modified"} for i in range(15)]

        context = ReviewContext(
            pull_request=mock_pr,
            changed_files=changed_files,
            project_context={},
            maturity_level="early_stage",
        )

        response = agent.review_code(context)

        assert response.success is True
        assert response.decision == ReviewDecision.REQUEST_CHANGES
        assert response.severity == IssueSeverity.MEDIUM

    def test_analyze_codebase(self, agent):
        """Test codebase analysis."""
        context = WorkflowContext(
            project_name="test-project",
            repository_url="https://github.com/test/repo",
            base_branch="main",
            working_directory="/tmp/test",
        )

        result = agent.analyze_codebase(context)

        assert result["analysis_type"] == "mock"
        assert result["project_name"] == "test-project"
        assert result["mock"] is True
        assert "recommendations" in result
        assert "metrics" in result

    def test_generate_documentation(self, agent):
        """Test documentation generation."""
        context = WorkflowContext(
            project_name="test-project",
            repository_url="https://github.com/test/repo",
            base_branch="main",
            working_directory="/tmp/test",
        )

        result = agent.generate_documentation(context)

        assert result["documentation_type"] == "mock"
        assert result["project_name"] == "test-project"
        assert result["mock"] is True
        assert "README.md" in result["files_generated"]


class TestMultiAgentCoordinator:
    """Test MultiAgentCoordinator functionality."""

    @pytest.fixture
    def agents(self):
        """Create test agents."""
        agent1_config = {"mock_mode": True, "simulate_failures": False}
        agent2_config = {"mock_mode": True, "simulate_failures": False}

        agent1 = MockAgentProvider(agent1_config)
        agent2 = MockAgentProvider(agent2_config)

        # Give them different names for testing
        agent1.name = "mock-1"
        agent2.name = "mock-2"

        return [agent1, agent2]

    @pytest.fixture
    def coordinator(self, agents):
        """Create agent coordinator."""
        return MultiAgentCoordinator(agents)

    def test_coordinator_initialization(self, coordinator, agents):
        """Test coordinator initialization."""
        assert len(coordinator.agents) == 2
        assert "mock-1" in coordinator.agents
        assert "mock-2" in coordinator.agents

    def test_coordinator_empty_agents(self):
        """Test coordinator with no agents."""
        with pytest.raises(ValidationError):
            MultiAgentCoordinator([])

    def test_get_agent(self, coordinator):
        """Test getting agent by name."""
        agent = coordinator.get_agent("mock-1")
        assert agent is not None
        assert agent.name == "mock-1"

        missing_agent = coordinator.get_agent("nonexistent")
        assert missing_agent is None

    def test_get_agents_with_capability(self, coordinator):
        """Test getting agents by capability."""
        validation_agents = coordinator.get_agents_with_capability(AgentCapability.VALIDATION)
        assert len(validation_agents) == 2

        implementation_agents = coordinator.get_agents_with_capability(
            AgentCapability.IMPLEMENTATION
        )
        assert len(implementation_agents) == 2

    def test_select_best_agent(self, coordinator):
        """Test selecting best agent."""
        # Test by capability
        agent = coordinator.select_best_agent(AgentCapability.VALIDATION)
        assert agent is not None
        assert agent.supports_capability(AgentCapability.VALIDATION)

        # Test with preferences
        agent = coordinator.select_best_agent(
            AgentCapability.VALIDATION, preferences=["mock-2", "mock-1"]
        )
        assert agent.name == "mock-2"

        # Test with context size requirement
        agent = coordinator.select_best_agent(AgentCapability.VALIDATION, context_size=50000)
        assert agent is not None

    def test_coordinate_review(self, coordinator):
        """Test coordinating review with multiple agents."""
        # Create mock PR and context
        mock_pr = Mock()
        mock_pr.id = "test-pr"
        mock_pr.number = 123
        mock_pr.title = "Test PR"
        mock_pr.body = "Test"
        mock_pr.state = PullRequestState.OPEN
        mock_pr.source_branch = "feature"
        mock_pr.target_branch = "main"
        mock_pr.author = "test"
        mock_pr.reviewers = []
        mock_pr.labels = []
        mock_pr.created_at = datetime.now()
        mock_pr.updated_at = datetime.now()
        mock_pr.mergeable = True
        mock_pr.url = "https://test.com/pr/123"
        mock_pr.platform_data = {}

        context = ReviewContext(
            pull_request=mock_pr,
            changed_files=[{"filename": "test.py", "status": "modified"}],
            project_context={},
            maturity_level="early_stage",
        )

        responses = coordinator.coordinate_review(context)

        assert len(responses) == 2
        assert all(response.success for response in responses)

    def test_coordinate_review_with_specific_reviewers(self, coordinator):
        """Test coordinating review with specific reviewer names."""
        mock_pr = Mock()
        mock_pr.id = "test-pr"
        mock_pr.number = 123
        mock_pr.title = "Test PR"
        mock_pr.body = "Test"
        mock_pr.state = PullRequestState.OPEN
        mock_pr.source_branch = "feature"
        mock_pr.target_branch = "main"
        mock_pr.author = "test"
        mock_pr.reviewers = []
        mock_pr.labels = []
        mock_pr.created_at = datetime.now()
        mock_pr.updated_at = datetime.now()
        mock_pr.mergeable = True
        mock_pr.url = "https://test.com/pr/123"
        mock_pr.platform_data = {}

        context = ReviewContext(
            pull_request=mock_pr, changed_files=[], project_context={}, maturity_level="early_stage"
        )

        responses = coordinator.coordinate_review(context, reviewer_names=["mock-1"])

        assert len(responses) == 1

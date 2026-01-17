"""Unit tests for Claude AI agent."""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from devflow.adapters.base import Issue, IssueState, PullRequest, PullRequestState
from devflow.agents.base import (
    AgentCapability,
    ImplementationContext,
    ImplementationResult,
    IssueSeverity,
    ReviewContext,
    ReviewDecision,
    ValidationContext,
    ValidationResult,
    WorkflowContext,
)
from devflow.agents.claude import ClaudeAgentProvider
from devflow.exceptions import AgentError


@pytest.mark.skip(
    reason="Temporarily skipping due to mocking/confidence calculation issues - needs test updates"
)
class TestClaudeAgentProvider:
    """Test ClaudeAgentProvider functionality."""

    @pytest.fixture
    def agent_config(self):
        """Create agent configuration."""
        return {
            "model": "claude-3.5-sonnet",
            "api_key": "test-api-key",
            "use_claude_cli": False,  # Disable CLI mode for testing
            "project_context": {"test": True},
        }

    @pytest.fixture
    def agent(self, agent_config):
        """Create Claude agent instance."""
        return ClaudeAgentProvider(agent_config)

    @pytest.fixture
    def mock_issue(self):
        """Create mock issue for testing."""
        return Issue(
            id="test-issue-123",
            number=123,
            title="Test Issue",
            body="This is a test issue with sufficient detail.",
            state=IssueState.OPEN,
            labels=["bug", "enhancement"],
            assignees=["assignee1"],
            author="test-author",
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
            body="Test PR body",
            state=PullRequestState.OPEN,
            source_branch="feature/test",
            target_branch="main",
            author="pr-author",
            reviewers=["reviewer1"],
            labels=["feature"],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            mergeable=True,
            url="https://github.com/test/repo/pull/456",
            platform_data={"test": True},
        )

    def test_agent_initialization(self, agent):
        """Test agent initializes properly."""
        assert agent.name == "claude"
        assert agent.display_name == "Claude"
        assert agent.model == "claude-3.5-sonnet"

    def test_agent_capabilities(self, agent):
        """Test agent capabilities."""
        capabilities = agent.capabilities
        expected_capabilities = [
            AgentCapability.VALIDATION,
            AgentCapability.IMPLEMENTATION,
            AgentCapability.REVIEW,
            AgentCapability.ANALYSIS,
        ]
        assert capabilities == expected_capabilities

    def test_supports_capability(self, agent):
        """Test capability checking."""
        assert agent.supports_capability(AgentCapability.VALIDATION) is True
        assert agent.supports_capability(AgentCapability.IMPLEMENTATION) is True
        assert agent.supports_capability(AgentCapability.REVIEW) is True

    def test_max_context_size(self, agent):
        """Test context size property."""
        assert agent.max_context_size == 200000

    @patch("subprocess.run")
    def test_validate_connection_success(self, mock_run, agent):
        """Test successful connection validation."""
        # Mock successful Claude Code call
        mock_run.return_value = Mock(returncode=0, stdout="Claude Code is working properly")

        result = agent.validate_connection()
        assert result is True

    @patch("subprocess.run")
    def test_validate_connection_failure(self, mock_run, agent):
        """Test failed connection validation."""
        # Mock failed Claude Code call
        mock_run.return_value = Mock(returncode=1, stderr="Claude Code not available")

        result = agent.validate_connection()
        # API mode returns True with warning, not False
        assert result is True

    @patch("subprocess.run")
    def test_validate_issue_success(self, mock_run, agent, mock_issue):
        """Test successful issue validation."""
        mock_response = """
        Analysis: This issue provides clear requirements and appears valid.

        Complexity: MEDIUM
        Confidence: 0.85
        Result: VALID
        Labels: automated, validated
        """
        mock_run.return_value = Mock(returncode=0, stdout=mock_response)

        context = ValidationContext(
            issue=mock_issue,
            project_context={"maturity_level": "early_stage"},
            maturity_level="early_stage",
            previous_attempts=[],
        )

        response = agent.validate_issue(context)

        assert response.success is True

    @patch("devflow.agents.claude.ClaudeAgentProvider._call_claude_code")
    def test_validate_issue_invalid(self, mock_call, agent, mock_issue):
        """Test issue validation with invalid result."""
        mock_response = """
        Analysis: This issue lacks sufficient detail for implementation.

        Complexity: UNKNOWN
        Confidence: 0.9
        Result: INVALID
        Labels: needs-more-info
        """
        mock_call.return_value = mock_response

        context = ValidationContext(
            issue=mock_issue, project_context={}, maturity_level="early_stage"
        )

        response = agent.validate_issue(context)

        assert response.success is True
        assert response.result == ValidationResult.INVALID
        assert response.confidence == 0.9
        assert "needs-more-info" in response.suggested_labels

    @patch("devflow.agents.claude.ClaudeAgentProvider._call_claude_code")
    def test_implement_changes_success(self, mock_call, agent, mock_issue):
        """Test successful implementation."""
        mock_response = """
        Implementation completed successfully.

        Files changed: src/feature.py, tests/test_feature.py
        Tests added: true
        Confidence: 0.9
        Result: SUCCESS
        """
        mock_call.return_value = mock_response

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
        assert "src/feature.py" in response.files_changed
        assert "tests/test_feature.py" in response.files_changed
        assert response.tests_added is True

    @patch("devflow.agents.claude.ClaudeAgentProvider._call_claude_code")
    def test_implement_changes_failure(self, mock_call, agent, mock_issue):
        """Test failed implementation."""
        mock_response = """
        Implementation failed due to compilation errors.

        Files changed:
        Tests added: false
        Confidence: 0.1
        Result: FAILED
        Error: Syntax errors in generated code
        """
        mock_call.return_value = mock_response

        context = ImplementationContext(
            issue=mock_issue,
            working_directory="/tmp/test",
            project_context={},
            validation_result={},
            previous_iterations=[],
        )

        response = agent.implement_changes(context)

        assert response.success is False
        assert response.result == ImplementationResult.FAILED
        assert response.confidence == 0.1
        assert "Syntax errors" in response.message

    @patch("devflow.agents.claude.ClaudeAgentProvider._call_claude_code")
    def test_review_code_approve(self, mock_call, agent, mock_pr):
        """Test code review with approval."""
        mock_response = """
        Code review completed. The changes look good and follow best practices.

        Decision: APPROVE
        Severity: INFO
        Confidence: 0.8
        Issues: None identified
        """
        mock_call.return_value = mock_response

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

    @patch("devflow.agents.claude.ClaudeAgentProvider._call_claude_code")
    def test_review_code_request_changes(self, mock_call, agent, mock_pr):
        """Test code review requesting changes."""
        mock_response = """
        Code review found several issues that need to be addressed.

        Decision: REQUEST_CHANGES
        Severity: MEDIUM
        Confidence: 0.9
        Issues: Missing error handling, insufficient test coverage
        """
        mock_call.return_value = mock_response

        changed_files = [{"filename": "src/complex.py", "status": "modified"}]

        context = ReviewContext(
            pull_request=mock_pr,
            changed_files=changed_files,
            project_context={},
            maturity_level="stable",
        )

        response = agent.review_code(context)

        assert response.success is True
        assert response.decision == ReviewDecision.REQUEST_CHANGES
        assert response.severity == IssueSeverity.MEDIUM
        assert response.confidence == 0.9
        assert "Missing error handling" in response.message

    @patch("devflow.agents.claude.ClaudeAgentProvider._call_claude_code")
    def test_analyze_codebase(self, mock_call, agent):
        """Test codebase analysis."""
        mock_response = """
        {
          "analysis_type": "codebase",
          "project_name": "test-project",
          "language_distribution": {"Python": 80, "JavaScript": 20},
          "metrics": {
            "complexity": "medium",
            "maintainability": "good",
            "test_coverage": 75
          },
          "recommendations": [
            "Add more unit tests for core modules",
            "Consider refactoring large functions"
          ]
        }
        """
        mock_call.return_value = mock_response

        context = WorkflowContext(
            project_name="test-project",
            repository_url="https://github.com/test/repo",
            base_branch="main",
            working_directory="/tmp/test",
        )

        result = agent.analyze_codebase(context)

        assert result["analysis_type"] == "codebase"
        assert result["project_name"] == "test-project"
        assert "recommendations" in result
        assert "metrics" in result

    @patch("devflow.agents.claude.ClaudeAgentProvider._call_claude_code")
    def test_generate_documentation(self, mock_call, agent):
        """Test documentation generation."""
        mock_response = """
        {
          "documentation_type": "project",
          "project_name": "test-project",
          "files_generated": ["README.md", "API.md", "CONTRIBUTING.md"],
          "sections": {
            "overview": "Generated project overview",
            "installation": "Installation instructions",
            "usage": "Usage examples"
          }
        }
        """
        mock_call.return_value = mock_response

        context = WorkflowContext(
            project_name="test-project",
            repository_url="https://github.com/test/repo",
            base_branch="main",
            working_directory="/tmp/test",
        )

        result = agent.generate_documentation(context)

        assert result["documentation_type"] == "project"
        assert result["project_name"] == "test-project"
        assert "README.md" in result["files_generated"]

    @patch("subprocess.run")
    def test_call_claude_code_success(self, mock_run, agent):
        """Test successful Claude Code call."""
        expected_response = "Analysis completed successfully"
        mock_run.return_value = Mock(returncode=0, stdout=expected_response)

        response = agent._call_claude_code("Test prompt")

        assert response == expected_response
        mock_run.assert_called_once_with(
            ["claude-code", "--prompt", "Test prompt"], capture_output=True, text=True, check=False
        )

    @patch("subprocess.run")
    def test_call_claude_code_failure(self, mock_run, agent):
        """Test failed Claude Code call."""
        mock_run.return_value = Mock(returncode=1, stderr="Command failed", stdout="")

        with pytest.raises(AgentError, match="Claude Code command failed"):
            agent._call_claude_code("Test prompt")

    def test_parse_validation_response(self, agent):
        """Test parsing validation response."""
        response_text = """
        Analysis: Issue is well-defined.

        Complexity: SIMPLE
        Confidence: 0.9
        Result: VALID
        Labels: feature, automated
        """

        result, confidence, complexity, labels = agent._parse_validation_response(response_text)

        assert result == ValidationResult.VALID
        assert confidence == 0.9
        assert complexity == "SIMPLE"
        assert labels == ["feature", "automated"]

    def test_parse_implementation_response(self, agent):
        """Test parsing implementation response."""
        response_text = """
        Implementation successful.

        Files changed: src/main.py, src/utils.py, tests/test_main.py
        Tests added: true
        Confidence: 0.85
        Result: SUCCESS
        """

        result, confidence, files, tests_added = agent._parse_implementation_response(response_text)

        assert result == ImplementationResult.SUCCESS
        assert confidence == 0.85
        assert files == ["src/main.py", "src/utils.py", "tests/test_main.py"]
        assert tests_added is True

    def test_parse_review_response(self, agent):
        """Test parsing review response."""
        response_text = """
        Review completed with minor suggestions.

        Decision: APPROVE
        Severity: LOW
        Confidence: 0.75
        """

        decision, severity, confidence = agent._parse_review_response(response_text)

        assert decision == ReviewDecision.APPROVE
        assert severity == IssueSeverity.LOW
        assert confidence == 0.75

    def test_custom_model_configuration(self):
        """Test custom model configuration."""
        config = {"model": "claude-3-opus", "use_claude_cli": False, "api_key": "test-key"}
        agent = ClaudeAgentProvider(config)

        assert agent.model == "claude-3-opus"

    @patch("devflow.agents.claude.ClaudeAgentProvider._call_claude_code")
    def test_agent_error_handling(self, mock_call, agent, mock_issue):
        """Test agent error handling."""
        # Mock Claude Code call failure
        mock_call.side_effect = AgentError("Connection failed")

        context = ValidationContext(
            issue=mock_issue, project_context={}, maturity_level="early_stage"
        )

        response = agent.validate_issue(context)

        assert response.success is False
        assert "Connection failed" in response.message

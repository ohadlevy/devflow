"""Simplified unit tests for Claude AI agent."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from devflow.adapters.base import Issue, IssueState, PullRequest, PullRequestState
from devflow.agents.base import AgentCapability
from devflow.agents.claude import ClaudeAgentProvider


class TestClaudeAgentProvider:
    """Test ClaudeAgentProvider basic functionality."""

    @pytest.fixture
    def agent_config(self):
        """Create agent configuration."""
        return {
            "model": "claude-3.5-sonnet",
            "api_key": "test-api-key",
            "project_context": {"test": True},
        }

    @pytest.fixture
    def agent(self, agent_config):
        """Create Claude agent instance."""
        return ClaudeAgentProvider(agent_config)

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
        assert result is False

    def test_custom_model_configuration(self):
        """Test custom model configuration."""
        config = {"model": "claude-3-opus"}
        agent = ClaudeAgentProvider(config)

        assert agent.model == "claude-3-opus"

    def test_default_model_configuration(self):
        """Test default model configuration."""
        config = {}  # No model specified
        agent = ClaudeAgentProvider(config)

        assert agent.model == "claude-3.5-sonnet"  # Default

    def test_agent_config_validation(self, agent_config):
        """Test agent configuration validation."""
        # Should not raise exception with valid config
        agent = ClaudeAgentProvider(agent_config)
        assert agent is not None

    def test_agent_name_and_display(self, agent):
        """Test agent name and display name."""
        assert agent.name == "claude"
        assert agent.display_name == "Claude"
        assert isinstance(agent.name, str)
        assert isinstance(agent.display_name, str)

    def test_agent_capabilities_type(self, agent):
        """Test that capabilities returns correct type."""
        capabilities = agent.capabilities
        assert isinstance(capabilities, list)
        assert all(isinstance(cap, AgentCapability) for cap in capabilities)

    def test_supports_all_declared_capabilities(self, agent):
        """Test that agent supports all its declared capabilities."""
        for capability in agent.capabilities:
            assert agent.supports_capability(capability) is True

    def test_context_size_is_positive(self, agent):
        """Test that context size is a positive integer."""
        context_size = agent.max_context_size
        assert isinstance(context_size, int)
        assert context_size > 0

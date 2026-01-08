"""Test configuration system."""

import pytest
from pathlib import Path
from devflow.core.config import (
    ProjectConfig,
    ProjectMaturity,
    MaturityConfig,
    PlatformConfig,
    WorkflowConfig,
    AgentConfig
)
from devflow.exceptions import ValidationError


class TestProjectMaturity:
    """Test ProjectMaturity enum."""

    def test_get_all_levels(self):
        """Test getting all maturity levels."""
        levels = ProjectMaturity.get_all_levels()
        expected = ["prototype", "early_stage", "stable", "mature"]
        assert levels == expected

    def test_string_conversion(self):
        """Test string conversion of maturity levels."""
        assert str(ProjectMaturity.EARLY_STAGE) == "early_stage"


class TestMaturityConfig:
    """Test MaturityConfig class."""

    def test_get_preset_valid(self):
        """Test getting a valid preset."""
        preset = MaturityConfig.get_preset("early_stage")
        assert preset.min_coverage == 40
        assert preset.coverage_goal == 75
        assert preset.review_strictness == "moderate"

    def test_get_preset_invalid(self):
        """Test getting an invalid preset raises error."""
        with pytest.raises(ValidationError, match="Invalid maturity level"):
            MaturityConfig.get_preset("invalid_level")

    def test_list_presets(self):
        """Test listing all presets."""
        presets = MaturityConfig.list_presets()
        assert len(presets) == 4
        assert "prototype" in presets
        assert "mature" in presets


class TestPlatformConfig:
    """Test PlatformConfig validation."""

    def test_valid_platform(self):
        """Test creating with valid platform."""
        config = PlatformConfig(primary="github")
        assert config.primary == "github"
        assert config.issue_tracking == "github"  # Should default to primary

    def test_invalid_platform(self):
        """Test creating with invalid platform raises error."""
        with pytest.raises(ValueError, match="Unsupported platform"):
            PlatformConfig(primary="invalid_platform")


class TestProjectConfig:
    """Test ProjectConfig class."""

    def test_basic_creation(self):
        """Test basic config creation."""
        config = ProjectConfig(
            project_name="test-project",
            platforms=PlatformConfig(primary="github")
        )
        assert config.project_name == "test-project"
        assert config.maturity_level == ProjectMaturity.EARLY_STAGE
        assert config.platforms.primary == "github"

    def test_maturity_preset_property(self):
        """Test maturity preset property."""
        config = ProjectConfig(
            project_name="test-project",
            maturity_level=ProjectMaturity.STABLE,
            platforms=PlatformConfig(primary="github")
        )
        preset = config.maturity_preset
        assert preset.min_coverage == 70
        assert preset.review_strictness == "strict"

    def test_validate_complete_success(self):
        """Test complete validation with valid config."""
        config = ProjectConfig(
            project_name="test-project",
            platforms=PlatformConfig(primary="github")
        )
        errors = config.validate_complete()
        assert errors == []

    def test_validate_complete_missing_name(self):
        """Test validation fails with missing project name."""
        config = ProjectConfig(
            project_name="",
            platforms=PlatformConfig(primary="github")
        )
        errors = config.validate_complete()
        assert "Project name is required" in errors

    def test_get_effective_settings(self):
        """Test getting effective settings."""
        config = ProjectConfig(
            project_name="test-project",
            maturity_level=ProjectMaturity.PROTOTYPE,
            platforms=PlatformConfig(primary="github")
        )
        settings = config.get_effective_settings()

        assert settings["project_name"] == "test-project"
        assert settings["maturity_level"] == "prototype"
        assert settings["min_coverage"] == 30  # From prototype preset
        assert settings["platforms"]["primary"] == "github"


class TestWorkflowConfig:
    """Test WorkflowConfig functionality."""

    def test_default_workflow_config(self):
        """Test default workflow configuration."""
        config = WorkflowConfig()
        assert config.validation_enabled is True
        assert config.validation_timeout == 180
        assert config.implementation_max_iterations == 3
        assert config.commit_strategy == "squash"

    def test_custom_workflow_config(self):
        """Test custom workflow configuration."""
        config = WorkflowConfig(
            validation_enabled=False,
            validation_timeout=300,
            implementation_max_iterations=5,
            commit_strategy="merge"
        )
        assert config.validation_enabled is False
        assert config.validation_timeout == 300
        assert config.implementation_max_iterations == 5
        assert config.commit_strategy == "merge"

    def test_workflow_config_validation(self):
        """Test workflow configuration validation."""
        config = WorkflowConfig(implementation_max_iterations=10)
        assert config.implementation_max_iterations == 10

        # Test minimum values
        config = WorkflowConfig(implementation_max_iterations=1)
        assert config.implementation_max_iterations == 1

    def test_invalid_commit_strategy(self):
        """Test invalid commit strategy validation."""
        with pytest.raises(ValueError, match="Invalid commit strategy"):
            WorkflowConfig(commit_strategy="invalid")


class TestAgentConfig:
    """Test AgentConfig functionality."""

    def test_claude_agent_default(self):
        """Test Claude agent with default model."""
        config = AgentConfig(primary="claude")
        assert config.primary == "claude"
        assert config.claude_model == "claude-3.5-sonnet"

    def test_claude_agent_custom_model(self):
        """Test Claude agent with custom model."""
        config = AgentConfig(
            primary="claude",
            claude_model="claude-3-opus"
        )
        assert config.primary == "claude"
        assert config.claude_model == "claude-3-opus"

    def test_mock_agent(self):
        """Test mock agent configuration."""
        config = AgentConfig(primary="mock")
        assert config.primary == "mock"
        # Claude model should still have default even for mock
        assert config.claude_model == "claude-3.5-sonnet"

    def test_custom_model_variants(self):
        """Test various Claude model configurations."""
        models = [
            "claude-3.5-sonnet",
            "claude-3-opus",
            "claude-3-sonnet",
            "claude-3-haiku"
        ]

        for model in models:
            config = AgentConfig(primary="claude", claude_model=model)
            assert config.claude_model == model


class TestCompleteProjectConfig:
    """Test complete ProjectConfig with all components."""

    def test_full_project_config(self):
        """Test creating complete project configuration."""
        config = ProjectConfig(
            project_name="test-project",
            project_root=Path.cwd(),
            repo_owner="test-owner",
            repo_name="test-repo",
            base_branch="main",
            maturity_level=ProjectMaturity.STABLE,
            platforms=PlatformConfig(primary="github"),
            workflows=WorkflowConfig(
                validation_enabled=True,
                implementation_max_iterations=5
            ),
            agents=AgentConfig(
                primary="claude",
                claude_model="claude-3-opus"
            )
        )

        assert config.project_name == "test-project"
        assert config.repo_owner == "test-owner"
        assert config.repo_name == "test-repo"
        assert config.base_branch == "main"
        assert config.maturity_level == ProjectMaturity.STABLE
        assert config.platforms.primary == "github"
        assert config.workflows.validation_enabled is True
        assert config.workflows.implementation_max_iterations == 5
        assert config.agents.primary == "claude"
        assert config.agents.claude_model == "claude-3-opus"

    def test_config_with_gitlab(self):
        """Test configuration with GitLab as primary."""
        config = ProjectConfig(
            project_name="gitlab-project",
            project_root=Path.cwd(),
            repo_owner="gitlab-owner",
            repo_name="gitlab-repo",
            base_branch="master",
            maturity_level=ProjectMaturity.MATURE,
            platforms=PlatformConfig(primary="gitlab"),
            workflows=WorkflowConfig(),
            agents=AgentConfig(primary="claude")
        )

        assert config.platforms.primary == "gitlab"
        assert config.base_branch == "master"
        assert config.maturity_level == ProjectMaturity.MATURE

    def test_minimal_config(self):
        """Test minimal valid configuration."""
        config = ProjectConfig(
            project_name="minimal-project",
            project_root=Path.cwd(),
            repo_owner="owner",
            repo_name="repo",
            base_branch="main",
            maturity_level=ProjectMaturity.PROTOTYPE,
            platforms=PlatformConfig(primary="github"),
            workflows=WorkflowConfig(),
            agents=AgentConfig(primary="mock")
        )

        assert config.project_name == "minimal-project"
        assert config.maturity_level == ProjectMaturity.PROTOTYPE
        assert config.agents.primary == "mock"

    def test_config_with_valid_minimum_fields(self):
        """Test configuration with minimum valid fields."""
        config = ProjectConfig(
            project_name="test-project",
            project_root=Path.cwd(),
            repo_owner="owner",
            repo_name="repo",
            base_branch="main",
            maturity_level=ProjectMaturity.EARLY_STAGE,
            platforms=PlatformConfig(primary="github"),
            workflows=WorkflowConfig(),
            agents=AgentConfig(primary="claude")
        )

        assert config.project_name == "test-project"
        assert config.repo_owner == "owner"
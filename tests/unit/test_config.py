"""Test configuration system."""

import pytest
from pathlib import Path
from devflow.core.config import (
    ProjectConfig,
    ProjectMaturity,
    MaturityConfig,
    PlatformConfig
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
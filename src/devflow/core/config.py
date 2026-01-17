"""DevFlow configuration system with maturity-based presets.

This module provides the sophisticated configuration system that adapts
workflow behavior based on project maturity level, similar to the original
embedded system but enhanced for broader use.
"""

import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from platformdirs import user_config_dir
from pydantic import BaseModel, Field, validator

from devflow.exceptions import ConfigurationError, ValidationError


class ProjectMaturity(str, Enum):
    """Project maturity levels that determine workflow behavior.

    Each maturity level has different requirements for code coverage,
    review strictness, breaking changes, and documentation.
    """

    PROTOTYPE = "prototype"
    EARLY_STAGE = "early_stage"
    STABLE = "stable"
    MATURE = "mature"

    @classmethod
    def get_all_levels(cls) -> List[str]:
        """Get all available maturity levels."""
        return [level.value for level in cls]

    def __str__(self) -> str:
        return self.value


@dataclass
class MaturityPreset:
    """Configuration preset for a specific project maturity level."""

    min_coverage: int
    coverage_goal: int
    security_level: str
    review_strictness: str
    allow_breaking_changes: bool
    require_changelog: bool
    require_migration_guide: bool
    description: str

    def __post_init__(self) -> None:
        """Validate preset values after initialization."""
        if not 0 <= self.min_coverage <= 100:
            raise ValidationError("Coverage must be between 0 and 100")
        if not 0 <= self.coverage_goal <= 100:
            raise ValidationError("Coverage goal must be between 0 and 100")
        if self.min_coverage > self.coverage_goal:
            raise ValidationError("Minimum coverage cannot exceed coverage goal")


class MaturityConfig:
    """Maturity-based configuration presets.

    This class provides sophisticated configuration presets that adapt
    workflow behavior based on project maturity level.
    """

    PRESETS: Dict[ProjectMaturity, MaturityPreset] = {
        ProjectMaturity.PROTOTYPE: MaturityPreset(
            min_coverage=30,
            coverage_goal=60,
            security_level="basic",
            review_strictness="lenient",
            allow_breaking_changes=True,
            require_changelog=False,
            require_migration_guide=False,
            description="Fast iteration, basic quality checks, proof of concepts",
        ),
        ProjectMaturity.EARLY_STAGE: MaturityPreset(
            min_coverage=40,
            coverage_goal=75,
            security_level="standard",
            review_strictness="moderate",
            allow_breaking_changes=True,
            require_changelog=True,
            require_migration_guide=False,
            description="Growing codebase, establishing patterns, small teams",
        ),
        ProjectMaturity.STABLE: MaturityPreset(
            min_coverage=70,
            coverage_goal=85,
            security_level="high",
            review_strictness="strict",
            allow_breaking_changes=True,
            require_changelog=True,
            require_migration_guide=True,
            description="Production ready, careful evolution, breaking changes with notice",
        ),
        ProjectMaturity.MATURE: MaturityPreset(
            min_coverage=85,
            coverage_goal=95,
            security_level="critical",
            review_strictness="very_strict",
            allow_breaking_changes=False,
            require_changelog=True,
            require_migration_guide=True,
            description="Stable API, wide adoption, strict backward compatibility",
        ),
    }

    @classmethod
    def get_preset(cls, maturity: Union[str, ProjectMaturity]) -> MaturityPreset:
        """Get configuration preset for a maturity level.

        Args:
            maturity: Project maturity level

        Returns:
            Configuration preset for the maturity level

        Raises:
            ValidationError: If maturity level is invalid
        """
        if isinstance(maturity, str):
            try:
                maturity = ProjectMaturity(maturity)
            except ValueError:
                valid_levels = ", ".join(ProjectMaturity.get_all_levels())
                raise ValidationError(
                    f"Invalid maturity level: {maturity}. " f"Valid levels: {valid_levels}"
                )

        if maturity not in cls.PRESETS:
            raise ValidationError(f"No preset found for maturity level: {maturity}")

        return cls.PRESETS[maturity]

    @classmethod
    def list_presets(cls) -> Dict[str, Dict[str, Any]]:
        """List all available maturity presets.

        Returns:
            Dictionary of maturity levels and their configurations
        """
        return {
            level.value: {
                "description": preset.description,
                "min_coverage": preset.min_coverage,
                "coverage_goal": preset.coverage_goal,
                "security_level": preset.security_level,
                "review_strictness": preset.review_strictness,
                "allow_breaking_changes": preset.allow_breaking_changes,
                "require_changelog": preset.require_changelog,
                "require_migration_guide": preset.require_migration_guide,
            }
            for level, preset in cls.PRESETS.items()
        }


class PlatformConfig(BaseModel):
    """Platform configuration settings."""

    primary: str = Field(..., description="Primary platform (github, gitlab, etc.)")
    issue_tracking: Optional[str] = Field(None, description="Issue tracking platform")
    git_provider: Optional[str] = Field(None, description="Git hosting provider")

    @validator("primary")
    def validate_primary_platform(cls, v):
        """Validate primary platform."""
        supported_platforms = ["github", "gitlab", "bitbucket"]
        if v not in supported_platforms:
            raise ValueError(f"Unsupported platform: {v}. Supported: {supported_platforms}")
        return v

    def __init__(self, **kwargs):
        """Initialize with defaults based on primary platform."""
        super().__init__(**kwargs)
        if not self.issue_tracking:
            self.issue_tracking = self.primary
        if not self.git_provider:
            self.git_provider = self.primary


class AgentConfig(BaseModel):
    """AI agent configuration settings."""

    primary: str = Field(default="claude", description="Primary AI agent provider")
    review_sources: List[str] = Field(
        default_factory=lambda: ["claude"], description="Review agent sources"
    )
    timeout: int = Field(default=600, ge=30, le=3600, description="Agent timeout in seconds")
    max_iterations: int = Field(default=3, ge=1, le=10, description="Maximum agent iterations")
    claude_model: str = Field(default="claude-3.5-sonnet", description="Claude model to use")

    @validator("review_sources")
    def validate_review_sources(cls, v):
        """Validate review sources."""
        if not v:
            raise ValueError("At least one review source must be configured")
        supported_agents = ["claude", "gpt", "copilot"]
        for source in v:
            if source not in supported_agents:
                raise ValueError(f"Unsupported agent: {source}. Supported: {supported_agents}")
        return v


class WorkflowConfig(BaseModel):
    """Workflow configuration settings."""

    validation_enabled: bool = Field(default=True, description="Enable issue validation")
    validation_timeout: int = Field(default=180, ge=30, le=600, description="Validation timeout")
    validation_requires_approval: bool = Field(
        default=True, description="Require human approval after validation"
    )
    implementation_max_iterations: int = Field(
        default=3, ge=1, le=10, description="Max implementation iterations"
    )
    commit_strategy: str = Field(default="squash", description="Git commit strategy")
    context_preservation: bool = Field(
        default=True, description="Preserve context between iterations"
    )
    multi_source_review: bool = Field(default=True, description="Enable multi-source code review")
    human_override_detection: bool = Field(
        default=True, description="Detect human reviewer interventions"
    )
    followup_issue_creation: bool = Field(
        default=True, description="Create follow-up issues for tech debt"
    )

    @validator("commit_strategy")
    def validate_commit_strategy(cls, v):
        """Validate commit strategy."""
        valid_strategies = ["squash", "rebase", "merge"]
        if v not in valid_strategies:
            raise ValueError(f"Invalid commit strategy: {v}. Valid: {valid_strategies}")
        return v


class ProjectConfig(BaseModel):
    """Complete project configuration.

    This class represents the full configuration for a DevFlow project,
    including platform settings, agent configuration, and workflow options.
    """

    # Project identification
    project_name: str = Field(..., description="Project name")
    project_root: Optional[Path] = Field(None, description="Project root directory")

    # Maturity-based configuration
    maturity_level: ProjectMaturity = Field(
        default=ProjectMaturity.EARLY_STAGE, description="Project maturity level"
    )

    # Platform configuration
    platforms: PlatformConfig = Field(..., description="Platform configuration")

    # Agent configuration
    agents: AgentConfig = Field(default_factory=AgentConfig, description="AI agent configuration")

    # Workflow configuration
    workflows: WorkflowConfig = Field(
        default_factory=WorkflowConfig, description="Workflow configuration"
    )

    # Repository information (auto-detected)
    repo_owner: Optional[str] = Field(None, description="Repository owner")
    repo_name: Optional[str] = Field(None, description="Repository name")
    base_branch: str = Field(default="main", description="Base branch name")

    # Advanced settings
    max_concurrent_workflows: int = Field(
        default=3, ge=1, le=10, description="Max concurrent workflows"
    )
    state_file_path: Optional[Path] = Field(None, description="Custom state file path")
    log_level: str = Field(default="INFO", description="Logging level")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        validate_assignment = True
        extra = "forbid"

    def __init__(self, **kwargs):
        """Initialize project configuration with validation."""
        super().__init__(**kwargs)
        self._apply_maturity_settings()

    def _apply_maturity_settings(self) -> None:
        """Apply maturity-based settings to configuration."""
        preset = MaturityConfig.get_preset(self.maturity_level)

        # Store preset for easy access
        self._maturity_preset = preset

    @property
    def maturity_preset(self) -> MaturityPreset:
        """Get the current maturity preset."""
        return getattr(self, "_maturity_preset", MaturityConfig.get_preset(self.maturity_level))

    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> "ProjectConfig":
        """Load configuration from a YAML file.

        Args:
            config_path: Path to configuration file

        Returns:
            Loaded configuration

        Raises:
            ConfigurationError: If file cannot be loaded or is invalid
        """
        config_path = Path(config_path)

        if not config_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {config_path}", config_path=str(config_path)
            )

        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)

            if not data:
                raise ConfigurationError(
                    f"Configuration file is empty: {config_path}", config_path=str(config_path)
                )

            # Set project_root if not specified
            if "project_root" not in data:
                data["project_root"] = config_path.parent

            return cls(**data)

        except yaml.YAMLError as e:
            raise ConfigurationError(
                f"Invalid YAML syntax in configuration file: {e}", config_path=str(config_path)
            ) from e
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load configuration: {e}", config_path=str(config_path)
            ) from e

    @classmethod
    def from_auto_detection(cls, start_path: Optional[Path] = None) -> Optional["ProjectConfig"]:
        """Auto-detect configuration from current directory.

        Args:
            start_path: Starting path for detection (defaults to current directory)

        Returns:
            Auto-detected configuration or None if not found
        """
        start_path = start_path or Path.cwd()

        # Look for configuration files
        config_files = ["devflow.yaml", "devflow.yml", ".devflow.yaml"]

        current_path = start_path
        while current_path != current_path.parent:  # Stop at root
            for config_file in config_files:
                config_path = current_path / config_file
                if config_path.exists():
                    return cls.from_file(config_path)
            current_path = current_path.parent

        # If no config file found, try to detect from git repository
        git_root = cls._detect_git_repository(start_path)
        if git_root:
            return cls._create_default_config(git_root)

        return None

    @staticmethod
    def _detect_git_repository(start_path: Path) -> Optional[Path]:
        """Detect git repository root.

        Args:
            start_path: Starting path for detection

        Returns:
            Git repository root or None if not found
        """
        current_path = start_path
        while current_path != current_path.parent:
            if (current_path / ".git").exists():
                return current_path
            current_path = current_path.parent
        return None

    @classmethod
    def _create_default_config(cls, project_root: Path) -> "ProjectConfig":
        """Create default configuration for a project.

        Args:
            project_root: Project root directory

        Returns:
            Default configuration
        """
        # Auto-detect repository information
        repo_owner, repo_name = cls._detect_repo_info(project_root)

        return cls(
            project_name=repo_name or project_root.name,
            project_root=project_root,
            repo_owner=repo_owner,
            repo_name=repo_name,
            platforms=PlatformConfig(primary="github"),
        )

    @staticmethod
    def _detect_repo_info(project_root: Path) -> tuple[Optional[str], Optional[str]]:
        """Detect repository owner and name from git remote.

        Args:
            project_root: Project root directory

        Returns:
            Tuple of (owner, name) or (None, None) if detection fails
        """
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=True,
            )
            remote_url = result.stdout.strip()

            # Parse different URL formats
            if "github.com" in remote_url:
                if remote_url.startswith("git@"):
                    # git@github.com:owner/repo.git
                    parts = remote_url.split(":")[1].replace(".git", "").split("/")
                else:
                    # https://github.com/owner/repo.git
                    parts = remote_url.split("github.com/")[1].replace(".git", "").split("/")

                if len(parts) >= 2:
                    return parts[0], parts[1]

        except (subprocess.CalledProcessError, IndexError):
            pass

        return None, None

    def save_to_file(self, config_path: Union[str, Path]) -> None:
        """Save configuration to a YAML file.

        Args:
            config_path: Path to save configuration

        Raises:
            ConfigurationError: If file cannot be saved
        """
        config_path = Path(config_path)

        try:
            # Create directory if it doesn't exist
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert to serializable dictionary
            data = self.dict(exclude_unset=True, exclude_none=True)

            # Convert Path objects to strings
            if "project_root" in data and data["project_root"]:
                data["project_root"] = str(data["project_root"])
            if "state_file_path" in data and data["state_file_path"]:
                data["state_file_path"] = str(data["state_file_path"])

            with open(config_path, "w") as f:
                yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

        except Exception as e:
            raise ConfigurationError(
                f"Failed to save configuration: {e}", config_path=str(config_path)
            ) from e

    def validate_complete(self) -> List[str]:
        """Perform comprehensive validation of configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors: List[str] = []

        # Validate required fields
        if not self.project_name:
            errors.append("Project name is required")

        # Validate maturity level
        try:
            MaturityConfig.get_preset(self.maturity_level)
        except ValidationError as e:
            errors.append(str(e))

        # Validate platform configuration
        if not self.platforms.primary:
            errors.append("Primary platform must be specified")

        # Validate paths if provided
        if self.project_root and not self.project_root.exists():
            errors.append(f"Project root does not exist: {self.project_root}")

        return errors

    def get_effective_settings(self) -> Dict[str, Any]:
        """Get effective settings including maturity-based values.

        Returns:
            Dictionary of all effective configuration values
        """
        preset = self.maturity_preset

        return {
            # Project settings
            "project_name": self.project_name,
            "maturity_level": (
                self.maturity_level.value
                if hasattr(self.maturity_level, "value")
                else str(self.maturity_level)
            ),
            "project_root": str(self.project_root) if self.project_root else None,
            # Maturity-based settings
            "min_coverage": preset.min_coverage,
            "coverage_goal": preset.coverage_goal,
            "security_level": preset.security_level,
            "review_strictness": preset.review_strictness,
            "allow_breaking_changes": preset.allow_breaking_changes,
            "require_changelog": preset.require_changelog,
            "require_migration_guide": preset.require_migration_guide,
            # Platform settings
            "platforms": self.platforms.dict(),
            # Agent settings
            "agents": self.agents.dict(),
            # Workflow settings
            "workflows": self.workflows.dict(),
            # Repository settings
            "repo_owner": self.repo_owner,
            "repo_name": self.repo_name,
            "base_branch": self.base_branch,
        }


def load_config(config_path: Optional[Union[str, Path]] = None) -> ProjectConfig:
    """Load DevFlow configuration.

    Args:
        config_path: Optional path to configuration file

    Returns:
        Loaded configuration

    Raises:
        ConfigurationError: If configuration cannot be loaded
    """
    if config_path:
        return ProjectConfig.from_file(config_path)

    # Try auto-detection
    config = ProjectConfig.from_auto_detection()
    if config:
        return config

    # No configuration found
    raise ConfigurationError("No DevFlow configuration found. Run 'devflow init' to create one.")


def get_user_config_dir() -> Path:
    """Get user configuration directory for DevFlow."""
    return Path(user_config_dir("devflow", appauthor=False))


def get_default_config_path() -> Path:
    """Get default configuration file path."""
    return get_user_config_dir() / "config.yaml"

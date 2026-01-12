"""Project initialization command."""

from pathlib import Path
from typing import Optional

from devflow.core.config import PlatformConfig, ProjectConfig, ProjectMaturity
from devflow.exceptions import ConfigurationError, ValidationError


def initialize_project(
    project_name: Optional[str] = None,
    maturity_level: str = "early_stage",
    platform: str = "github",
    force: bool = False,
    config_file: Optional[Path] = None,
) -> ProjectConfig:
    """Initialize a new DevFlow project.

    Args:
        project_name: Project name (defaults to directory name)
        maturity_level: Project maturity level
        platform: Primary platform
        force: Force initialization even if config exists
        config_file: Custom config file path

    Returns:
        Created project configuration

    Raises:
        ConfigurationError: If initialization fails
        ValidationError: If parameters are invalid
    """
    # Determine project root
    project_root = Path.cwd()

    # Determine project name
    if not project_name:
        project_name = project_root.name

    # Validate maturity level
    if maturity_level not in ProjectMaturity.get_all_levels():
        valid_levels = ", ".join(ProjectMaturity.get_all_levels())
        raise ValidationError(
            f"Invalid maturity level: {maturity_level}. Valid levels: {valid_levels}"
        )

    # Determine config file path
    if not config_file:
        config_file = project_root / "devflow.yaml"

    # Check if config already exists
    if config_file.exists() and not force:
        raise ConfigurationError(
            f"Configuration file already exists: {config_file}. Use --force to overwrite."
        )

    # Auto-detect repository information
    try:
        existing_config = ProjectConfig._create_default_config(project_root)
        repo_owner = existing_config.repo_owner
        repo_name = existing_config.repo_name
    except Exception:
        repo_owner = None
        repo_name = None

    # Create configuration

    config = ProjectConfig(
        project_name=project_name,
        project_root=project_root,
        maturity_level=ProjectMaturity(maturity_level),
        platforms=PlatformConfig(primary=platform),
        repo_owner=repo_owner,
        repo_name=repo_name or project_name,
    )

    # Save configuration
    config.save_to_file(config_file)

    return config

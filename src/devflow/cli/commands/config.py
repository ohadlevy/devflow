"""Configuration management command."""

from pathlib import Path
from typing import Optional, Any, Union

from devflow.core.config import ProjectConfig, load_config
from devflow.exceptions import ConfigurationError, ValidationError


def manage_config(
    key: str,
    value: Optional[str] = None,
    unset: bool = False,
    config_file: Optional[Path] = None
) -> Union[str, None]:
    """Manage DevFlow configuration.

    Args:
        key: Configuration key (supports dot notation)
        value: Value to set (None to get current value)
        unset: Remove the configuration key
        config_file: Custom config file path

    Returns:
        Current value when getting, None when setting/unsetting

    Raises:
        ConfigurationError: If configuration operation fails
        ValidationError: If key or value is invalid
    """
    if not key:
        raise ValidationError("Configuration key cannot be empty")

    try:
        # Load current configuration
        if config_file:
            config = ProjectConfig.from_file(config_file)
            config_path = config_file
        else:
            config = load_config()
            config_path = Path("devflow.yaml")  # Default path

        # Handle different operations
        if unset:
            return _unset_config_value(config, key, config_path)
        elif value is not None:
            return _set_config_value(config, key, value, config_path)
        else:
            return _get_config_value(config, key)

    except Exception as e:
        raise ConfigurationError(f"Configuration operation failed: {str(e)}")


def _get_config_value(config: ProjectConfig, key: str) -> str:
    """Get a configuration value using dot notation.

    Args:
        config: Project configuration
        key: Configuration key (dot notation)

    Returns:
        Configuration value as string

    Raises:
        ValidationError: If key not found
    """
    try:
        # Handle common configuration keys
        if key == "maturity_level":
            return config.maturity_level.value
        elif key == "project_name":
            return config.project_name
        elif key == "platforms.primary":
            return config.platforms.primary
        elif key == "agents.primary":
            return config.agents.primary
        elif key.startswith("platforms."):
            attr = key.split(".", 1)[1]
            return getattr(config.platforms, attr, "")
        elif key.startswith("agents."):
            attr = key.split(".", 1)[1]
            return str(getattr(config.agents, attr, ""))
        elif key.startswith("workflows."):
            attr = key.split(".", 1)[1]
            return str(getattr(config.workflows, attr, ""))
        else:
            # Try to get from effective settings
            settings = config.get_effective_settings()
            if key in settings:
                return str(settings[key])

        raise ValidationError(f"Configuration key not found: {key}")

    except AttributeError:
        raise ValidationError(f"Invalid configuration key: {key}")


def _set_config_value(config: ProjectConfig, key: str, value: str, config_path: Path) -> None:
    """Set a configuration value using dot notation.

    Args:
        config: Project configuration
        key: Configuration key (dot notation)
        value: Value to set
        config_path: Path to save configuration

    Raises:
        ValidationError: If key is invalid or value cannot be set
    """
    try:
        # Handle common configuration keys
        if key == "maturity_level":
            from devflow.core.config import ProjectMaturity
            if value not in ProjectMaturity.get_all_levels():
                valid_levels = ", ".join(ProjectMaturity.get_all_levels())
                raise ValidationError(f"Invalid maturity level: {value}. Valid: {valid_levels}")
            config.maturity_level = ProjectMaturity(value)

        elif key == "project_name":
            if not value.strip():
                raise ValidationError("Project name cannot be empty")
            config.project_name = value.strip()

        elif key == "platforms.primary":
            valid_platforms = ["github", "gitlab", "bitbucket"]
            if value not in valid_platforms:
                raise ValidationError(f"Invalid platform: {value}. Valid: {valid_platforms}")
            config.platforms.primary = value

        elif key == "agents.primary":
            valid_agents = ["claude", "gpt", "copilot"]
            if value not in valid_agents:
                raise ValidationError(f"Invalid agent: {value}. Valid: {valid_agents}")
            config.agents.primary = value

        elif key == "workflows.validation_enabled":
            config.workflows.validation_enabled = value.lower() in ("true", "yes", "1")

        elif key == "workflows.implementation_max_iterations":
            try:
                iterations = int(value)
                if not 1 <= iterations <= 10:
                    raise ValueError("Must be between 1 and 10")
                config.workflows.implementation_max_iterations = iterations
            except ValueError as e:
                raise ValidationError(f"Invalid iteration count: {e}")

        else:
            raise ValidationError(f"Configuration key cannot be set: {key}")

        # Validate configuration after changes
        errors = config.validate_complete()
        if errors:
            raise ValidationError(f"Configuration validation failed: {'; '.join(errors)}")

        # Save updated configuration
        config.save_to_file(config_path)

    except Exception as e:
        if isinstance(e, (ValidationError, ConfigurationError)):
            raise
        raise ValidationError(f"Failed to set configuration: {str(e)}")


def _unset_config_value(config: ProjectConfig, key: str, config_path: Path) -> None:
    """Unset a configuration value.

    Args:
        config: Project configuration
        key: Configuration key to unset
        config_path: Path to save configuration

    Raises:
        ValidationError: If key cannot be unset
    """
    # Most configuration values have defaults and cannot be truly "unset"
    # This implementation resets values to their defaults

    try:
        if key == "maturity_level":
            from devflow.core.config import ProjectMaturity
            config.maturity_level = ProjectMaturity.EARLY_STAGE

        elif key == "platforms.primary":
            config.platforms.primary = "github"

        elif key == "agents.primary":
            config.agents.primary = "claude"

        elif key == "workflows.validation_enabled":
            config.workflows.validation_enabled = True

        elif key == "workflows.implementation_max_iterations":
            config.workflows.implementation_max_iterations = 3

        else:
            raise ValidationError(f"Configuration key cannot be unset: {key}")

        # Save updated configuration
        config.save_to_file(config_path)

    except Exception as e:
        if isinstance(e, (ValidationError, ConfigurationError)):
            raise
        raise ValidationError(f"Failed to unset configuration: {str(e)}")
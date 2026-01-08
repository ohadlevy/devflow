"""Environment validation command."""

import subprocess
import sys
from typing import Dict, List, Any

from devflow.core.config import ProjectConfig
from devflow.exceptions import ValidationError


def validate_environment(config: ProjectConfig) -> List[Dict[str, Any]]:
    """Validate DevFlow environment and configuration.

    Args:
        config: Project configuration

    Returns:
        List of validation results
    """
    results = []

    # Validate configuration
    results.append(_validate_configuration(config))

    # Validate Python environment
    results.append(_validate_python_environment())

    # Validate Git setup
    results.append(_validate_git_setup())

    # Validate platform connectivity
    results.append(_validate_platform_connectivity(config))

    # Validate project structure
    results.append(_validate_project_structure(config))

    return results


def _validate_configuration(config: ProjectConfig) -> Dict[str, Any]:
    """Validate project configuration."""
    try:
        errors = config.validate_complete()

        if errors:
            return {
                'component': 'Configuration',
                'passed': False,
                'message': f"Configuration errors: {'; '.join(errors)}"
            }

        return {
            'component': 'Configuration',
            'passed': True,
            'message': 'Configuration is valid'
        }

    except Exception as e:
        return {
            'component': 'Configuration',
            'passed': False,
            'message': f"Configuration validation failed: {str(e)}"
        }


def _validate_python_environment() -> Dict[str, Any]:
    """Validate Python environment."""
    try:
        # Check Python version
        if sys.version_info < (3, 9):
            return {
                'component': 'Python',
                'passed': False,
                'message': f"Python 3.9+ required, found {sys.version_info.major}.{sys.version_info.minor}"
            }

        # Check required packages (basic check)
        try:
            import click
            import yaml
            import rich
            return {
                'component': 'Python',
                'passed': True,
                'message': f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            }
        except ImportError as e:
            return {
                'component': 'Python',
                'passed': False,
                'message': f"Missing required package: {str(e)}"
            }

    except Exception as e:
        return {
            'component': 'Python',
            'passed': False,
            'message': f"Python environment check failed: {str(e)}"
        }


def _validate_git_setup() -> Dict[str, Any]:
    """Validate Git setup."""
    try:
        # Check if git is available
        result = subprocess.run(
            ['git', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return {
                'component': 'Git',
                'passed': False,
                'message': 'Git not found or not working'
            }

        # Check git configuration
        try:
            user_name = subprocess.run(
                ['git', 'config', 'user.name'],
                capture_output=True,
                text=True,
                timeout=10
            )

            user_email = subprocess.run(
                ['git', 'config', 'user.email'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if not user_name.stdout.strip() or not user_email.stdout.strip():
                return {
                    'component': 'Git',
                    'passed': False,
                    'message': 'Git user name and email not configured'
                }

        except subprocess.TimeoutExpired:
            return {
                'component': 'Git',
                'passed': False,
                'message': 'Git configuration check timed out'
            }

        return {
            'component': 'Git',
            'passed': True,
            'message': 'Git is properly configured'
        }

    except subprocess.TimeoutExpired:
        return {
            'component': 'Git',
            'passed': False,
            'message': 'Git command timed out'
        }
    except Exception as e:
        return {
            'component': 'Git',
            'passed': False,
            'message': f"Git validation failed: {str(e)}"
        }


def _validate_platform_connectivity(config: ProjectConfig) -> Dict[str, Any]:
    """Validate platform connectivity."""
    try:
        platform = config.platforms.primary

        if platform == "github":
            return _validate_github_connectivity(config)
        elif platform == "gitlab":
            return _validate_gitlab_connectivity(config)
        else:
            return {
                'component': 'Platform',
                'passed': False,
                'message': f"Platform validation not implemented for: {platform}"
            }

    except Exception as e:
        return {
            'component': 'Platform',
            'passed': False,
            'message': f"Platform validation failed: {str(e)}"
        }


def _validate_github_connectivity(config: ProjectConfig) -> Dict[str, Any]:
    """Validate GitHub connectivity."""
    try:
        # Check if gh CLI is available
        result = subprocess.run(
            ['gh', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return {
                'component': 'Platform (GitHub)',
                'passed': False,
                'message': 'GitHub CLI (gh) not found. Install from: https://cli.github.com/'
            }

        # Check if authenticated
        auth_result = subprocess.run(
            ['gh', 'auth', 'status'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if auth_result.returncode != 0:
            return {
                'component': 'Platform (GitHub)',
                'passed': False,
                'message': 'GitHub CLI not authenticated. Run: gh auth login'
            }

        # Test API access if repository is configured
        if config.repo_owner and config.repo_name:
            repo_result = subprocess.run(
                ['gh', 'repo', 'view', f"{config.repo_owner}/{config.repo_name}"],
                capture_output=True,
                text=True,
                timeout=15
            )

            if repo_result.returncode != 0:
                return {
                    'component': 'Platform (GitHub)',
                    'passed': False,
                    'message': f"Cannot access repository: {config.repo_owner}/{config.repo_name}"
                }

        return {
            'component': 'Platform (GitHub)',
            'passed': True,
            'message': 'GitHub CLI is authenticated and working'
        }

    except subprocess.TimeoutExpired:
        return {
            'component': 'Platform (GitHub)',
            'passed': False,
            'message': 'GitHub CLI commands timed out'
        }
    except Exception as e:
        return {
            'component': 'Platform (GitHub)',
            'passed': False,
            'message': f"GitHub validation failed: {str(e)}"
        }


def _validate_gitlab_connectivity(config: ProjectConfig) -> Dict[str, Any]:
    """Validate GitLab connectivity."""
    # Placeholder for GitLab validation
    return {
        'component': 'Platform (GitLab)',
        'passed': False,
        'message': 'GitLab validation not yet implemented'
    }


def _validate_project_structure(config: ProjectConfig) -> Dict[str, Any]:
    """Validate project structure."""
    try:
        if not config.project_root:
            return {
                'component': 'Project Structure',
                'passed': False,
                'message': 'Project root not specified'
            }

        if not config.project_root.exists():
            return {
                'component': 'Project Structure',
                'passed': False,
                'message': f"Project root does not exist: {config.project_root}"
            }

        if not config.project_root.is_dir():
            return {
                'component': 'Project Structure',
                'passed': False,
                'message': f"Project root is not a directory: {config.project_root}"
            }

        # Check for .git directory
        git_dir = config.project_root / ".git"
        if not git_dir.exists():
            return {
                'component': 'Project Structure',
                'passed': False,
                'message': 'Not a Git repository (no .git directory found)'
            }

        return {
            'component': 'Project Structure',
            'passed': True,
            'message': 'Project structure is valid'
        }

    except Exception as e:
        return {
            'component': 'Project Structure',
            'passed': False,
            'message': f"Project structure validation failed: {str(e)}"
        }
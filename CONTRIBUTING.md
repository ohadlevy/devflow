# Contributing to DevFlow

Thank you for your interest in contributing to DevFlow! We welcome contributions from developers of all experience levels.

## 📋 Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Plugin Development](#plugin-development)
- [Documentation](#documentation)
- [Community](#community)

## 🚀 Getting Started

### Prerequisites

- Python 3.9+ (we test on 3.9, 3.10, 3.11, and 3.12)
- Git
- GitHub account (for contributions)

### Development Setup

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/devflow.git
   cd devflow
   ```

2. **Set up development environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   ```

4. **Verify setup**:
   ```bash
   pytest
   devflow --help
   ```

## 🎨 Code Style

We use automated tools to maintain consistent code style:

- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking

### Running Code Style Tools

```bash
# Format code
black src/ tests/
isort src/ tests/

# Check linting
flake8 src/ tests/

# Type checking
mypy src/
```

### Code Style Guidelines

- **Type hints**: All public functions must have type hints
- **Docstrings**: Use Google-style docstrings for all public functions/classes
- **Error handling**: Always validate inputs and provide meaningful error messages
- **Logging**: Use structured logging with appropriate levels

#### Example Function with Proper Style

```python
from typing import Optional, List
import logging

from devflow.exceptions import ValidationError
from devflow.core.config import ProjectConfig

logger = logging.getLogger(__name__)

def validate_project_config(
    config: ProjectConfig,
    strict: bool = True
) -> Optional[List[str]]:
    """Validate project configuration for completeness and correctness.

    Args:
        config: The project configuration to validate.
        strict: If True, enforce strict validation rules.

    Returns:
        List of validation errors, or None if validation passes.

    Raises:
        ValidationError: If critical validation failures occur.
        TypeError: If config is not a ProjectConfig instance.
    """
    if not isinstance(config, ProjectConfig):
        raise TypeError(f"Expected ProjectConfig, got {type(config).__name__}")

    errors: List[str] = []

    # Validate required fields
    if not config.project_name:
        errors.append("Project name is required")

    if not config.platforms.primary:
        errors.append("Primary platform must be specified")

    # Log validation result
    if errors:
        logger.warning("Configuration validation failed", extra={
            "errors": errors,
            "config_name": config.project_name,
            "strict_mode": strict
        })
    else:
        logger.debug("Configuration validation passed", extra={
            "config_name": config.project_name
        })

    return errors if errors else None
```

## 🧪 Testing

We maintain comprehensive test coverage with multiple test types:

### Test Structure

```
tests/
├── unit/           # Fast, isolated unit tests
├── integration/    # Integration tests with external services
└── fixtures/       # Test data and mock objects
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/devflow --cov-report=html

# Run specific test types
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m "not slow"    # Skip slow tests

# Run specific test file
pytest tests/unit/core/test_config.py
```

### Writing Tests

#### Test Naming Convention

- Test files: `test_*.py`
- Test functions: `test_functionality_scenario`
- Test classes: `TestClassName`

#### Example Test

```python
import pytest
from unittest.mock import Mock, patch

from devflow.core.config import ProjectConfig
from devflow.exceptions import ValidationError

class TestProjectConfig:
    """Test suite for ProjectConfig functionality."""

    def test_valid_config_creation(self):
        """Test creating a valid configuration."""
        config = ProjectConfig(
            project_name="test-project",
            maturity_level="early_stage"
        )

        assert config.project_name == "test-project"
        assert config.maturity_level == "early_stage"

    def test_invalid_maturity_level_raises_error(self):
        """Test that invalid maturity levels raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ProjectConfig(
                project_name="test-project",
                maturity_level="invalid-level"
            )

        assert "Invalid maturity level" in str(exc_info.value)

    @patch('devflow.core.config.detect_git_repository')
    def test_auto_detection_with_git_repo(self, mock_detect):
        """Test auto-detection of configuration in git repository."""
        mock_detect.return_value = "/path/to/repo"

        config = ProjectConfig.from_auto_detection()

        assert config is not None
        mock_detect.assert_called_once()
```

### Test Coverage Requirements

- **Minimum coverage**: 85% for new code
- **Critical paths**: 100% coverage required
- **Error handling**: All exception paths must be tested

## 📝 Submitting Changes

### Pull Request Process

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Write tests for new functionality
   - Update documentation as needed
   - Follow code style guidelines
   - Add changelog entry

3. **Test your changes**:
   ```bash
   pytest
   black src/ tests/
   isort src/ tests/
   flake8 src/ tests/
   mypy src/
   ```

4. **Commit with descriptive message**:
   ```bash
   git commit -m "feat: add support for custom review providers

   - Add abstract ReviewProvider base class
   - Implement plugin discovery for review providers
   - Add configuration validation for review settings
   - Include tests and documentation

   Fixes #123"
   ```

5. **Push and create PR**:
   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

### PR Requirements

- [ ] All tests pass
- [ ] Code coverage meets requirements
- [ ] Documentation updated
- [ ] Changelog entry added
- [ ] Code review from maintainer

## 🔌 Plugin Development

DevFlow supports plugins for platforms, AI agents, and review providers.

### Platform Adapter Plugin

```python
from devflow.adapters.base import PlatformAdapter
from devflow.exceptions import PlatformError

class MyPlatformAdapter(PlatformAdapter):
    """Custom platform adapter for MyPlatform."""

    name = "myplatform"
    display_name = "MyPlatform"

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_token = config.get("api_token")
        if not self.api_token:
            raise PlatformError("API token is required for MyPlatform")

    def validate_connection(self) -> bool:
        """Validate connection to platform."""
        # Implementation here
        pass

    def create_pull_request(self, changes: Changes) -> PullRequest:
        """Create a pull request on the platform."""
        # Implementation here
        pass
```

### Plugin Registration

```python
# setup.py or pyproject.toml entry points
[project.entry-points."devflow.platforms"]
myplatform = "mypackage.adapters:MyPlatformAdapter"

[project.entry-points."devflow.agents"]
myagent = "mypackage.agents:MyAIAgent"
```

## 📖 Documentation

### Documentation Types

- **API Documentation**: Auto-generated from docstrings
- **User Guides**: Step-by-step tutorials
- **Configuration Reference**: Complete configuration options
- **Plugin Development**: How to create plugins

### Building Documentation

```bash
cd docs/
pip install -r requirements.txt
make html
```

### Documentation Guidelines

- Use clear, concise language
- Include practical examples
- Keep documentation up-to-date with code changes
- Use proper Markdown formatting

## 🏗️ Architecture Guidelines

### Error Handling

```python
from devflow.exceptions import DevFlowError, ValidationError, PlatformError

# Always validate inputs
def process_issue(issue_id: str, config: ProjectConfig) -> WorkflowResult:
    if not issue_id:
        raise ValidationError("Issue ID cannot be empty")

    if not issue_id.isdigit():
        raise ValidationError(f"Invalid issue ID format: {issue_id}")

    try:
        # Process issue
        result = do_processing(issue_id, config)
        return result
    except PlatformError as e:
        logger.error(f"Platform error processing issue {issue_id}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing issue {issue_id}: {e}")
        raise DevFlowError(f"Failed to process issue {issue_id}") from e
```

### Logging

```python
import logging
from devflow.core.logging import get_logger

# Use structured logging
logger = get_logger(__name__)

def process_workflow(workflow_id: str) -> None:
    logger.info("Starting workflow processing", extra={
        "workflow_id": workflow_id,
        "action": "start"
    })

    try:
        # Do work
        pass
    except Exception as e:
        logger.error("Workflow processing failed", extra={
            "workflow_id": workflow_id,
            "error": str(e),
            "action": "error"
        })
        raise

    logger.info("Workflow processing completed", extra={
        "workflow_id": workflow_id,
        "action": "complete"
    })
```

## 🚀 Release Process

Releases are automated through GitHub Actions:

1. Version bump in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create release tag: `git tag v0.2.0`
4. Push tag: `git push origin v0.2.0`
5. GitHub Actions builds and publishes to PyPI

## 🌍 Community

- **GitHub Discussions**: Ask questions and share ideas
- **GitHub Issues**: Bug reports and feature requests
- **Discord**: Real-time chat with maintainers and users

### Code of Conduct

We follow the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). Please be respectful and inclusive in all interactions.

## 🎉 Recognition

Contributors are recognized in:

- `AUTHORS.md` file
- Release notes
- Annual contributor highlights

Thank you for contributing to DevFlow! 🚀
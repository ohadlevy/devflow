"""Test custom exceptions."""

import pytest
from devflow.exceptions import (
    DevFlowError,
    ValidationError,
    PlatformError,
    AgentError,
    get_exception_class
)


class TestDevFlowError:
    """Test base DevFlowError class."""

    def test_basic_error(self):
        """Test creating basic error."""
        error = DevFlowError("Test message")
        assert str(error) == "Test message (Code: GENERAL_ERROR)"
        assert error.message == "Test message"
        assert error.error_code == "GENERAL_ERROR"

    def test_error_with_context(self):
        """Test error with context."""
        error = DevFlowError(
            "Test message",
            error_code="TEST_ERROR",
            context={"key": "value"}
        )
        assert "Context: key=value" in str(error)
        assert error.context["key"] == "value"


class TestValidationError:
    """Test ValidationError class."""

    def test_validation_error_with_field(self):
        """Test validation error with field information."""
        error = ValidationError(
            "Invalid value",
            field="test_field",
            value="bad_value"
        )
        assert error.field == "test_field"
        assert error.value == "bad_value"
        assert error.error_code == "VALIDATION_ERROR"

    def test_validation_error_with_list(self):
        """Test validation error with validation list."""
        validation_errors = ["Error 1", "Error 2"]
        error = ValidationError(
            "Multiple errors",
            validation_errors=validation_errors
        )
        assert error.validation_errors == validation_errors


class TestPlatformError:
    """Test PlatformError class."""

    def test_platform_error(self):
        """Test platform error creation."""
        error = PlatformError(
            "Connection failed",
            platform="github",
            status_code=404
        )
        assert error.platform == "github"
        assert error.status_code == 404
        assert error.error_code == "PLATFORM_ERROR"


class TestAgentError:
    """Test AgentError class."""

    def test_agent_error(self):
        """Test agent error creation."""
        error = AgentError(
            "Agent failed",
            agent_type="claude",
            operation="validation"
        )
        assert error.agent_type == "claude"
        assert error.operation == "validation"
        assert error.error_code == "AGENT_ERROR"


class TestExceptionMapping:
    """Test exception mapping functionality."""

    def test_get_exception_class_valid(self):
        """Test getting valid exception class."""
        cls = get_exception_class("validation")
        assert cls == ValidationError

    def test_get_exception_class_invalid(self):
        """Test getting invalid exception class raises error."""
        with pytest.raises(ValueError, match="Unknown error type"):
            get_exception_class("invalid_type")
"""Custom exceptions for DevFlow.

This module defines the exception hierarchy used throughout DevFlow for
proper error handling and user feedback.
"""

from typing import Any, Dict, Optional, List


class DevFlowError(Exception):
    """Base exception class for all DevFlow errors.

    All custom DevFlow exceptions should inherit from this class.
    This allows for easy catching of all DevFlow-related errors.

    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error code
        context: Additional context information
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "GENERAL_ERROR"
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (Code: {self.error_code}, Context: {context_str})"
        return f"{self.message} (Code: {self.error_code})"


class ValidationError(DevFlowError):
    """Raised when validation fails.

    This exception is raised when input validation fails, such as:
    - Invalid configuration parameters
    - Missing required fields
    - Malformed data

    Attributes:
        field: The field that failed validation
        value: The invalid value
        validation_errors: List of specific validation errors
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        validation_errors: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        context = kwargs.pop("context", {})
        if field:
            context["field"] = field
        if value is not None:
            context["value"] = str(value)
        if validation_errors:
            context["validation_errors"] = validation_errors

        super().__init__(
            message,
            error_code="VALIDATION_ERROR",
            context=context,
            **kwargs
        )
        self.field = field
        self.value = value
        self.validation_errors = validation_errors or []


class ConfigurationError(DevFlowError):
    """Raised when configuration is invalid or missing.

    This exception is raised for configuration-related issues:
    - Missing configuration files
    - Invalid configuration syntax
    - Incompatible configuration options
    """

    def __init__(self, message: str, config_path: Optional[str] = None, **kwargs) -> None:
        context = kwargs.pop("context", {})
        if config_path:
            context["config_path"] = config_path

        super().__init__(
            message,
            error_code="CONFIGURATION_ERROR",
            context=context,
            **kwargs
        )
        self.config_path = config_path


class PlatformError(DevFlowError):
    """Raised when platform operations fail.

    This exception is raised for platform-specific errors:
    - API authentication failures
    - Network connectivity issues
    - Platform-specific validation errors
    """

    def __init__(
        self,
        message: str,
        platform: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs
    ) -> None:
        context = kwargs.pop("context", {})
        if platform:
            context["platform"] = platform
        if status_code:
            context["status_code"] = status_code

        super().__init__(
            message,
            error_code="PLATFORM_ERROR",
            context=context,
            **kwargs
        )
        self.platform = platform
        self.status_code = status_code


class AgentError(DevFlowError):
    """Raised when AI agent operations fail.

    This exception is raised for AI agent-related errors:
    - Agent communication failures
    - Invalid agent responses
    - Agent timeout errors
    """

    def __init__(
        self,
        message: str,
        agent_type: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ) -> None:
        context = kwargs.pop("context", {})
        if agent_type:
            context["agent_type"] = agent_type
        if operation:
            context["operation"] = operation

        super().__init__(
            message,
            error_code="AGENT_ERROR",
            context=context,
            **kwargs
        )
        self.agent_type = agent_type
        self.operation = operation


class WorkflowError(DevFlowError):
    """Raised when workflow execution fails.

    This exception is raised for workflow-related errors:
    - Workflow state inconsistencies
    - Step execution failures
    - Workflow timeout errors
    """

    def __init__(
        self,
        message: str,
        workflow_id: Optional[str] = None,
        step: Optional[str] = None,
        **kwargs
    ) -> None:
        context = kwargs.pop("context", {})
        if workflow_id:
            context["workflow_id"] = workflow_id
        if step:
            context["step"] = step

        super().__init__(
            message,
            error_code="WORKFLOW_ERROR",
            context=context,
            **kwargs
        )
        self.workflow_id = workflow_id
        self.step = step


class GitOperationError(DevFlowError):
    """Raised when Git operations fail.

    This exception is raised for Git-related errors:
    - Repository access issues
    - Merge conflicts
    - Branch operation failures
    """

    def __init__(
        self,
        message: str,
        repository: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ) -> None:
        context = kwargs.pop("context", {})
        if repository:
            context["repository"] = repository
        if operation:
            context["operation"] = operation

        super().__init__(
            message,
            error_code="GIT_ERROR",
            context=context,
            **kwargs
        )
        self.repository = repository
        self.operation = operation


class AuthenticationError(DevFlowError):
    """Raised when authentication fails.

    This exception is raised for authentication-related errors:
    - Invalid credentials
    - Expired tokens
    - Insufficient permissions
    """

    def __init__(
        self,
        message: str,
        service: Optional[str] = None,
        auth_type: Optional[str] = None,
        **kwargs
    ) -> None:
        context = kwargs.pop("context", {})
        if service:
            context["service"] = service
        if auth_type:
            context["auth_type"] = auth_type

        super().__init__(
            message,
            error_code="AUTH_ERROR",
            context=context,
            **kwargs
        )
        self.service = service
        self.auth_type = auth_type


class PermissionError(DevFlowError):
    """Raised when permission checks fail.

    This exception is raised for permission-related errors:
    - Insufficient repository permissions
    - Missing API scopes
    - File system access denied
    """

    def __init__(
        self,
        message: str,
        resource: Optional[str] = None,
        required_permission: Optional[str] = None,
        **kwargs
    ) -> None:
        context = kwargs.pop("context", {})
        if resource:
            context["resource"] = resource
        if required_permission:
            context["required_permission"] = required_permission

        super().__init__(
            message,
            error_code="PERMISSION_ERROR",
            context=context,
            **kwargs
        )
        self.resource = resource
        self.required_permission = required_permission


class StateError(DevFlowError):
    """Raised when state management operations fail.

    This exception is raised for state-related errors:
    - Invalid state transitions
    - State persistence failures
    - State corruption
    """

    def __init__(
        self,
        message: str,
        current_state: Optional[str] = None,
        requested_state: Optional[str] = None,
        **kwargs
    ) -> None:
        context = kwargs.pop("context", {})
        if current_state:
            context["current_state"] = current_state
        if requested_state:
            context["requested_state"] = requested_state

        super().__init__(
            message,
            error_code="STATE_ERROR",
            context=context,
            **kwargs
        )
        self.current_state = current_state
        self.requested_state = requested_state


class PluginError(DevFlowError):
    """Raised when plugin operations fail.

    This exception is raised for plugin-related errors:
    - Plugin loading failures
    - Plugin compatibility issues
    - Plugin configuration errors
    """

    def __init__(
        self,
        message: str,
        plugin_name: Optional[str] = None,
        plugin_type: Optional[str] = None,
        **kwargs
    ) -> None:
        context = kwargs.pop("context", {})
        if plugin_name:
            context["plugin_name"] = plugin_name
        if plugin_type:
            context["plugin_type"] = plugin_type

        super().__init__(
            message,
            error_code="PLUGIN_ERROR",
            context=context,
            **kwargs
        )
        self.plugin_name = plugin_name
        self.plugin_type = plugin_type


# Exception mapping for easier error handling
ERROR_MAPPING = {
    "validation": ValidationError,
    "configuration": ConfigurationError,
    "platform": PlatformError,
    "agent": AgentError,
    "workflow": WorkflowError,
    "git": GitOperationError,
    "auth": AuthenticationError,
    "permission": PermissionError,
    "state": StateError,
    "plugin": PluginError,
}


def get_exception_class(error_type: str) -> type[DevFlowError]:
    """Get the appropriate exception class for an error type.

    Args:
        error_type: The type of error (e.g., 'validation', 'platform')

    Returns:
        The appropriate exception class

    Raises:
        ValueError: If error_type is not recognized
    """
    if error_type not in ERROR_MAPPING:
        raise ValueError(f"Unknown error type: {error_type}")

    return ERROR_MAPPING[error_type]
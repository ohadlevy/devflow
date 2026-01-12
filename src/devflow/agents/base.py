"""Abstract base classes for AI agents.

This module defines the interfaces that AI agents must implement
to provide consistent automation capabilities across different providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Generator, List, Optional, Union

from devflow.adapters.base import Issue, PullRequest
from devflow.exceptions import AgentError, ValidationError


class AgentCapability(str, Enum):
    """AI agent capabilities."""

    VALIDATION = "validation"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    ANALYSIS = "analysis"
    DOCUMENTATION = "documentation"


class ValidationResult(str, Enum):
    """Issue validation results."""

    VALID = "valid"
    NEEDS_CLARIFICATION = "needs_clarification"
    INVALID = "invalid"
    NEEDS_HUMAN = "needs_human"


class ImplementationResult(str, Enum):
    """Implementation results."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    NEEDS_HUMAN = "needs_human"


class ReviewDecision(str, Enum):
    """Code review decisions."""

    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    COMMENT = "comment"
    BLOCK = "block"


class IssueSeverity(str, Enum):
    """Issue severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class WorkflowContext:
    """Context information for workflow operations."""

    project_name: str
    repository_url: str
    base_branch: str
    working_directory: str
    issue: Optional[Issue] = None
    pull_request: Optional[PullRequest] = None
    previous_iterations: List[Dict[str, Any]] = None
    maturity_level: str = "early_stage"
    custom_settings: Dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.previous_iterations is None:
            self.previous_iterations = []
        if self.custom_settings is None:
            self.custom_settings = {}


@dataclass
class ValidationContext:
    """Context for issue validation."""

    issue: Issue
    project_context: Dict[str, Any]
    maturity_level: str
    previous_attempts: List[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.previous_attempts is None:
            self.previous_attempts = []


@dataclass
class ImplementationContext:
    """Context for code implementation."""

    issue: Issue
    working_directory: str
    project_context: Dict[str, Any]
    validation_result: Dict[str, Any]
    previous_iterations: List[Dict[str, Any]] = None
    constraints: Dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.previous_iterations is None:
            self.previous_iterations = []
        if self.constraints is None:
            self.constraints = {}


@dataclass
class ReviewContext:
    """Context for code review."""

    pull_request: PullRequest
    changed_files: List[Dict[str, Any]]
    project_context: Dict[str, Any]
    maturity_level: str
    review_focus: List[str] = None
    previous_reviews: List[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.review_focus is None:
            self.review_focus = ["correctness", "maintainability", "security"]
        if self.previous_reviews is None:
            self.previous_reviews = []


@dataclass
class AgentResponse:
    """Base response from AI agents."""

    success: bool
    message: str
    data: Dict[str, Any]
    confidence: float = 1.0  # 0.0 to 1.0
    reasoning: Optional[str] = None
    suggestions: List[str] = None
    warnings: List[str] = None

    def __post_init__(self) -> None:
        if self.suggestions is None:
            self.suggestions = []
        if self.warnings is None:
            self.warnings = []

        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationError("Confidence must be between 0.0 and 1.0")


@dataclass
class ValidationResponse(AgentResponse):
    """Response from issue validation."""

    result: ValidationResult = ValidationResult.INVALID
    clarifications_needed: List[str] = None
    estimated_complexity: Optional[str] = None
    suggested_labels: List[str] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.clarifications_needed is None:
            self.clarifications_needed = []
        if self.suggested_labels is None:
            self.suggested_labels = []


@dataclass
class ImplementationResponse(AgentResponse):
    """Response from code implementation."""

    result: ImplementationResult = ImplementationResult.FAILED
    files_changed: List[str] = None
    commits_made: List[str] = None
    tests_added: bool = False
    documentation_updated: bool = False
    follow_up_needed: List[str] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.files_changed is None:
            self.files_changed = []
        if self.commits_made is None:
            self.commits_made = []
        if self.follow_up_needed is None:
            self.follow_up_needed = []


@dataclass
class ReviewResponse(AgentResponse):
    """Response from code review."""

    decision: ReviewDecision = ReviewDecision.COMMENT
    severity: IssueSeverity = IssueSeverity.INFO
    issues_found: List[Dict[str, Any]] = None
    suggestions_made: List[Dict[str, Any]] = None
    security_concerns: List[Dict[str, Any]] = None
    performance_notes: List[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.issues_found is None:
            self.issues_found = []
        if self.suggestions_made is None:
            self.suggestions_made = []
        if self.security_concerns is None:
            self.security_concerns = []
        if self.performance_notes is None:
            self.performance_notes = []


class AgentProvider(ABC):
    """Abstract base class for AI agent providers.

    Agent providers implement specific AI models or services
    for automating development workflow tasks.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the agent provider.

        Args:
            config: Provider-specific configuration

        Raises:
            AgentError: If configuration is invalid
        """
        self.config = config
        self._validate_config()

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent provider name (e.g., 'claude', 'gpt', 'copilot')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable provider name (e.g., 'Claude', 'GPT-4', 'GitHub Copilot')."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> List[AgentCapability]:
        """List of capabilities this provider supports."""
        pass

    @property
    @abstractmethod
    def max_context_size(self) -> int:
        """Maximum context size for this provider."""
        pass

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider-specific configuration.

        Raises:
            AgentError: If configuration is invalid
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Test connection to the AI service.

        Returns:
            True if connection is successful

        Raises:
            AgentError: If connection validation fails
        """
        pass

    def supports_capability(self, capability: AgentCapability) -> bool:
        """Check if provider supports a specific capability.

        Args:
            capability: Capability to check

        Returns:
            True if capability is supported
        """
        return capability in self.capabilities

    # Core agent methods
    def validate_issue(self, context: ValidationContext) -> ValidationResponse:
        """Validate an issue for implementation readiness.

        Args:
            context: Validation context

        Returns:
            Validation response

        Raises:
            AgentError: If validation fails
        """
        if not self.supports_capability(AgentCapability.VALIDATION):
            raise AgentError(
                f"Agent {self.name} does not support validation capability",
                agent_type=self.name,
                operation="validate_issue",
            )

        return self._validate_issue_impl(context)

    def validate_issue_stream(
        self, context: ValidationContext
    ) -> Generator[str, None, ValidationResponse]:
        """Validate an issue for implementation readiness with streaming progress indicators.

        This method provides real-time progress updates during the validation process,
        allowing users to see what's happening during potentially long-running operations.
        The streaming pattern yields progress messages throughout execution and returns
        the final validation result.

        Args:
            context: Validation context containing issue details, project information,
                    and other required data for validation

        Yields:
            str: Progress messages during validation (e.g., "🔍 Analyzing requirements...",
                "📖 Reading project context...", "✅ Validation complete")

        Returns:
            ValidationResponse: Final validation response containing success status,
                              validation result (VALID, INVALID, NEEDS_CLARIFICATION),
                              confidence score, and detailed reasoning

        Raises:
            AgentError: If validation fails due to agent configuration issues,
                       missing capabilities, or unexpected errors during validation

        Example:
            >>> validation_generator = agent.validate_issue_stream(context)
            >>> for progress_message in validation_generator:
            ...     if isinstance(progress_message, str):
            ...         print(f"Progress: {progress_message}")
            >>> # Generator exhaustion returns the ValidationResponse
        """
        if not self.supports_capability(AgentCapability.VALIDATION):
            raise AgentError(
                f"Agent {self.name} does not support validation capability",
                agent_type=self.name,
                operation="validate_issue_stream",
            )

        # Yield from implementation and return the final response
        yield from self._validate_issue_stream_impl(context)

    def implement_changes(self, context: ImplementationContext) -> ImplementationResponse:
        """Implement code changes for an issue.

        Args:
            context: Implementation context

        Returns:
            Implementation response

        Raises:
            AgentError: If implementation fails
        """
        if not self.supports_capability(AgentCapability.IMPLEMENTATION):
            raise AgentError(
                f"Agent {self.name} does not support implementation capability",
                agent_type=self.name,
                operation="implement_changes",
            )

        return self._implement_changes_impl(context)

    def review_code(self, context: ReviewContext) -> ReviewResponse:
        """Review code changes in a pull request.

        Args:
            context: Review context

        Returns:
            Review response

        Raises:
            AgentError: If review fails
        """
        if not self.supports_capability(AgentCapability.REVIEW):
            raise AgentError(
                f"Agent {self.name} does not support review capability",
                agent_type=self.name,
                operation="review_code",
            )

        return self._review_code_impl(context)

    def analyze_codebase(self, context: WorkflowContext) -> Dict[str, Any]:
        """Analyze codebase for patterns and improvements.

        Args:
            context: Workflow context

        Returns:
            Analysis results

        Raises:
            AgentError: If analysis fails
        """
        if not self.supports_capability(AgentCapability.ANALYSIS):
            raise AgentError(
                f"Agent {self.name} does not support analysis capability",
                agent_type=self.name,
                operation="analyze_codebase",
            )

        return self._analyze_codebase_impl(context)

    def generate_documentation(self, context: WorkflowContext) -> Dict[str, Any]:
        """Generate or update documentation.

        Args:
            context: Workflow context

        Returns:
            Documentation generation results

        Raises:
            AgentError: If documentation generation fails
        """
        if not self.supports_capability(AgentCapability.DOCUMENTATION):
            raise AgentError(
                f"Agent {self.name} does not support documentation capability",
                agent_type=self.name,
                operation="generate_documentation",
            )

        return self._generate_documentation_impl(context)

    # Abstract implementation methods
    @abstractmethod
    def _validate_issue_impl(self, context: ValidationContext) -> ValidationResponse:
        """Implementation-specific issue validation.

        Args:
            context: Validation context

        Returns:
            Validation response
        """
        pass

    @abstractmethod
    def _validate_issue_stream_impl(
        self, context: ValidationContext
    ) -> Generator[str, None, ValidationResponse]:
        """Implementation-specific issue validation with streaming progress indicators.

        This abstract method must be implemented by concrete agent classes to provide
        validation logic with real-time progress updates. Implementations should:

        1. Yield descriptive progress messages throughout the validation process
        2. Handle errors gracefully and yield error messages before raising exceptions
        3. Use emojis and clear language for user-friendly progress updates
        4. Return a comprehensive ValidationResponse upon completion

        Args:
            context: ValidationContext containing:
                    - issue: Issue details (title, body, labels, etc.)
                    - project_info: Project context and configuration
                    - additional metadata for validation

        Yields:
            str: User-friendly progress messages with emojis and descriptive text
                Examples:
                - "🔍 Starting issue analysis..."
                - "📖 Reading project context and issue details..."
                - "💭 Analyzing requirements... (50 lines processed)"
                - "⚙️ Assessing implementation feasibility..."
                - "🧪 Checking testability and validation criteria..."
                - "✅ Analysis complete, processing results..."
                - "❌ Validation error: <error message>"

        Returns:
            ValidationResponse: Comprehensive validation result containing:
                              - success: Boolean indicating overall success
                              - message: Detailed validation summary
                              - result: ValidationResult enum (VALID, INVALID, NEEDS_CLARIFICATION)
                              - confidence: Float between 0.0 and 1.0
                              - reasoning: Detailed explanation of the validation decision
                              - data: Additional metadata (e.g., raw AI response)

        Implementation Guidelines:
            - Use try-catch blocks around subprocess calls and external API calls
            - Yield progress messages every 10-20 lines of processing for long operations
            - Include context-specific progress indicators (e.g., file count, analysis depth)
            - Handle timeouts and network errors gracefully
            - Provide meaningful error messages in both progress yields and final response
        """
        pass

    @abstractmethod
    def _implement_changes_impl(self, context: ImplementationContext) -> ImplementationResponse:
        """Implementation-specific code changes.

        Args:
            context: Implementation context

        Returns:
            Implementation response
        """
        pass

    @abstractmethod
    def _review_code_impl(self, context: ReviewContext) -> ReviewResponse:
        """Implementation-specific code review.

        Args:
            context: Review context

        Returns:
            Review response
        """
        pass

    def _analyze_codebase_impl(self, context: WorkflowContext) -> Dict[str, Any]:
        """Implementation-specific codebase analysis.

        Args:
            context: Workflow context

        Returns:
            Analysis results

        Note:
            Default implementation raises NotImplementedError.
            Override this method if the agent supports analysis.
        """
        raise NotImplementedError(f"Agent {self.name} does not implement codebase analysis")

    def _generate_documentation_impl(self, context: WorkflowContext) -> Dict[str, Any]:
        """Implementation-specific documentation generation.

        Args:
            context: Workflow context

        Returns:
            Documentation generation results

        Note:
            Default implementation raises NotImplementedError.
            Override this method if the agent supports documentation generation.
        """
        raise NotImplementedError(f"Agent {self.name} does not implement documentation generation")

    # Utility methods
    def estimate_token_usage(self, text: str) -> int:
        """Estimate token usage for a text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count

        Note:
            Default implementation uses a simple heuristic.
            Override for more accurate provider-specific estimation.
        """
        # Simple heuristic: ~4 characters per token
        return len(text) // 4

    def truncate_context(self, context: str, max_tokens: Optional[int] = None) -> str:
        """Truncate context to fit within token limits.

        Args:
            context: Context to truncate
            max_tokens: Maximum tokens allowed (uses provider max if None)

        Returns:
            Truncated context
        """
        if max_tokens is None:
            max_tokens = self.max_context_size

        estimated_tokens = self.estimate_token_usage(context)

        if estimated_tokens <= max_tokens:
            return context

        # Truncate to fit (simple approach)
        target_length = len(context) * max_tokens // estimated_tokens
        return context[:target_length] + "... [truncated]"

    def prepare_context(self, base_context: str, additional_data: Dict[str, Any]) -> str:
        """Prepare context string for agent processing.

        Args:
            base_context: Base context information
            additional_data: Additional context data

        Returns:
            Prepared context string
        """
        context_parts = [base_context]

        for key, value in additional_data.items():
            if value:
                context_parts.append(f"\n{key}:\n{value}")

        full_context = "\n".join(context_parts)
        return self.truncate_context(full_context)


class MultiAgentCoordinator:
    """Coordinates multiple AI agents for complex workflows."""

    def __init__(self, agents: List[AgentProvider]) -> None:
        """Initialize the coordinator.

        Args:
            agents: List of available agents

        Raises:
            ValidationError: If no agents provided
        """
        if not agents:
            raise ValidationError("At least one agent must be provided")

        self.agents = {agent.name: agent for agent in agents}

    def get_agent(self, name: str) -> Optional[AgentProvider]:
        """Get agent by name.

        Args:
            name: Agent name

        Returns:
            Agent instance or None if not found
        """
        return self.agents.get(name)

    def get_agents_with_capability(self, capability: AgentCapability) -> List[AgentProvider]:
        """Get all agents that support a specific capability.

        Args:
            capability: Required capability

        Returns:
            List of agents with the capability
        """
        return [agent for agent in self.agents.values() if agent.supports_capability(capability)]

    def select_best_agent(
        self,
        capability: AgentCapability,
        context_size: Optional[int] = None,
        preferences: Optional[List[str]] = None,
    ) -> Optional[AgentProvider]:
        """Select the best agent for a task.

        Args:
            capability: Required capability
            context_size: Required context size
            preferences: Preferred agent names (in order)

        Returns:
            Selected agent or None if none suitable
        """
        candidates = self.get_agents_with_capability(capability)

        if not candidates:
            return None

        # Filter by context size if specified
        if context_size:
            candidates = [agent for agent in candidates if agent.max_context_size >= context_size]

        if not candidates:
            return None

        # Apply preferences if specified
        if preferences:
            for preferred_name in preferences:
                for agent in candidates:
                    if agent.name == preferred_name:
                        return agent

        # Return first suitable agent
        return candidates[0]

    def coordinate_review(
        self, context: ReviewContext, reviewer_names: Optional[List[str]] = None
    ) -> List[ReviewResponse]:
        """Coordinate multi-agent code review.

        Args:
            context: Review context
            reviewer_names: Specific reviewers to use (None for all capable)

        Returns:
            List of review responses from all agents

        Raises:
            AgentError: If no suitable reviewers found
        """
        if reviewer_names:
            reviewers = [
                self.get_agent(name)
                for name in reviewer_names
                if self.get_agent(name)
                and self.get_agent(name).supports_capability(AgentCapability.REVIEW)
            ]
        else:
            reviewers = self.get_agents_with_capability(AgentCapability.REVIEW)

        if not reviewers:
            raise AgentError("No suitable review agents available", operation="coordinate_review")

        responses = []
        for reviewer in reviewers:
            try:
                response = reviewer.review_code(context)
                responses.append(response)
            except AgentError as e:
                # Log error but continue with other reviewers
                pass

        return responses

"""Mock AI Agent for testing and dry-run scenarios.

This agent provides mock responses for all capabilities without requiring
external AI services. Perfect for testing and dry-run mode.
"""

from typing import Any, Dict, List

from devflow.agents.base import (
    AgentCapability,
    AgentProvider,
    ImplementationContext,
    ImplementationResponse,
    ImplementationResult,
    IssueSeverity,
    ReviewContext,
    ReviewDecision,
    ReviewResponse,
    ValidationContext,
    ValidationResponse,
    ValidationResult,
    WorkflowContext,
)
from devflow.exceptions import AgentError


class MockAgentProvider(AgentProvider):
    """Mock AI agent provider for testing and dry-run scenarios.

    This agent provides realistic mock responses without requiring
    external AI services.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize mock agent provider.

        Args:
            config: Provider configuration
        """
        # Set attributes first
        self.mock_mode = config.get("mock_mode", True)
        self.simulate_failures = config.get("simulate_failures", False)
        self._name = "mock"  # Make name settable for testing

        super().__init__(config)

    @property
    def name(self) -> str:
        """Agent provider name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set agent provider name (for testing)."""
        self._name = value

    @property
    def display_name(self) -> str:
        """Human-readable provider name."""
        return "Mock Agent"

    @property
    def capabilities(self) -> List[AgentCapability]:
        """List of capabilities this provider supports."""
        return [
            AgentCapability.VALIDATION,
            AgentCapability.IMPLEMENTATION,
            AgentCapability.REVIEW,
            AgentCapability.ANALYSIS,
            AgentCapability.DOCUMENTATION,
        ]

    @property
    def max_context_size(self) -> int:
        """Maximum context size for this provider."""
        return 100000  # Mock context size

    def _validate_config(self) -> None:
        """Validate mock agent configuration."""
        # Mock agent always has valid configuration
        pass

    def validate_connection(self) -> bool:
        """Test connection to the AI service.

        Returns:
            True (mock agent is always available)
        """
        return not self.simulate_failures

    def _validate_issue_impl(self, context: ValidationContext) -> ValidationResponse:
        """Implementation-specific issue validation."""
        if self.simulate_failures:
            return ValidationResponse(
                success=False,
                message="Mock validation failed",
                data={"mock": True},
                result=ValidationResult.INVALID,
                confidence=0.0,
                reasoning="Simulated failure for testing",
            )

        # Generate realistic mock validation response
        issue = context.issue
        complexity = (
            "SIMPLE" if len(issue.body) < 100 else "MEDIUM" if len(issue.body) < 500 else "COMPLEX"
        )

        response_message = f"""## 🤖 Mock Validation Analysis

**VALIDATION**: VALID

**COMPLEXITY**: {complexity}

**ANALYSIS**:
The issue "{issue.title}" appears to be well-defined and implementable.
This is a mock analysis for testing and dry-run purposes.

**IMPLEMENTATION_APPROACH**:
1. Analyze the requirements from the issue description
2. Identify the necessary code changes
3. Implement the solution with appropriate tests
4. Document any breaking changes

**ESTIMATED_EFFORT**: 1-3 files to change, moderate complexity

This is a mock response generated for testing purposes."""

        return ValidationResponse(
            success=True,
            message=response_message,
            data={"mock": True, "issue_id": issue.id},
            result=ValidationResult.VALID,
            confidence=0.8,
            reasoning="Mock analysis of issue requirements and feasibility",
            estimated_complexity=complexity,
            clarifications_needed=[],
            suggested_labels=["automated", "validated"],
        )

    def _implement_changes_impl(self, context: ImplementationContext) -> ImplementationResponse:
        """Implementation-specific code changes."""
        if self.simulate_failures:
            return ImplementationResponse(
                success=False,
                message="Mock implementation failed",
                data={"mock": True},
                result=ImplementationResult.FAILED,
                confidence=0.0,
            )

        # Generate realistic mock implementation response
        issue = context.issue

        response_message = f"""## 🤖 Mock Implementation

**IMPLEMENTATION**: SUCCESS

**FILES_CHANGED**:
- src/mock_feature.py: Added new functionality for {issue.title}
- tests/test_mock_feature.py: Added comprehensive tests

**VALIDATION**:
- All existing tests pass
- New functionality tested
- Code follows project conventions

**REMAINING_WORK**:
- None - implementation complete

This is a mock implementation for testing purposes."""

        return ImplementationResponse(
            success=True,
            message=response_message,
            data={"mock": True, "issue_id": issue.id},
            result=ImplementationResult.SUCCESS,
            confidence=0.9,
            files_changed=["src/mock_feature.py", "tests/test_mock_feature.py"],
            commits_made=["feat: implement mock feature for testing"],
            tests_added=True,
            documentation_updated=False,
            follow_up_needed=[],
        )

    def _review_code_impl(self, context: ReviewContext) -> ReviewResponse:
        """Implementation-specific code review."""
        if self.simulate_failures:
            return ReviewResponse(
                success=False,
                message="Mock review failed",
                data={"mock": True},
                decision=ReviewDecision.COMMENT,
                severity=IssueSeverity.INFO,
                confidence=0.0,
            )

        # Generate realistic mock review response
        pr = context.pull_request
        num_files = len(context.changed_files)

        if num_files > 10:
            decision = ReviewDecision.REQUEST_CHANGES
            severity = IssueSeverity.MEDIUM
            summary = "Large changeset requires careful review"
        else:
            decision = ReviewDecision.APPROVE
            severity = IssueSeverity.INFO
            summary = "Changes look good to merge"

        response_message = f"""## 🤖 Mock Code Review

**DECISION**: {decision.value.upper()}

**SEVERITY**: {severity.value.upper()}

**SUMMARY**:
{summary}

**DETAILED_FEEDBACK**:
Mock review of {num_files} changed files in PR #{pr.number}.
All checks passed in this mock review scenario.

**SECURITY_CONCERNS**:
None identified in mock review

**PERFORMANCE_IMPACT**:
No significant impact expected

**TESTING_ASSESSMENT**:
Tests appear adequate for mock implementation

**SPECIFIC_ISSUES**:
No significant issues found in this mock review

**RECOMMENDATIONS**:
- Continue with current approach
- Monitor for any issues in production

This is a mock review for testing purposes."""

        return ReviewResponse(
            success=True,
            message=response_message,
            data={"mock": True, "pr_id": pr.id},
            decision=decision,
            severity=severity,
            confidence=0.8,
            issues_found=[],
            suggestions_made=[],
            security_concerns=[],
            performance_notes=[],
        )

    def _analyze_codebase_impl(self, context: WorkflowContext) -> Dict[str, Any]:
        """Implementation-specific codebase analysis."""
        return {
            "analysis_type": "mock",
            "project_name": context.project_name,
            "summary": "Mock codebase analysis completed",
            "recommendations": ["Continue development", "Add more tests", "Improve documentation"],
            "metrics": {
                "complexity": "moderate",
                "maintainability": "good",
                "test_coverage": "adequate",
            },
            "mock": True,
        }

    def _generate_documentation_impl(self, context: WorkflowContext) -> Dict[str, Any]:
        """Implementation-specific documentation generation."""
        return {
            "documentation_type": "mock",
            "project_name": context.project_name,
            "files_generated": ["README.md", "API_DOCS.md"],
            "summary": "Mock documentation generation completed",
            "mock": True,
        }

    def _validate_issue_stream_impl(self, context):
        """Implementation-specific issue validation with streaming progress."""
        from typing import Generator

        from devflow.agents.base import ValidationResponse, ValidationResult

        # Simulate streaming validation progress
        yield "🔍 Starting mock validation..."
        yield "📖 Reading issue requirements..."
        yield "⚙️ Analyzing feasibility..."
        yield "✅ Mock validation complete"

        # Return mock validation response
        return ValidationResponse(
            success=True,
            message="Mock validation completed successfully",
            data={"mock": True},
            result=ValidationResult.VALID,
            confidence=0.95,
            reasoning="Mock agent validation for testing",
        )

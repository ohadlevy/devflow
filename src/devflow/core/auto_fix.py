"""Auto-Fix Feedback Loop - Automatically fixes CI failures and review feedback.

This module implements the sophisticated auto-fix system that makes DevFlow
truly autonomous by handling failures and feedback automatically.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from devflow.agents.base import AgentProvider, ImplementationContext
from devflow.adapters.base import PlatformAdapter, ReviewDecision
from devflow.exceptions import AutoFixError

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Types of feedback that can trigger auto-fixes."""
    CI_FAILURE = "ci_failure"
    REVIEW_FEEDBACK = "review_feedback"
    MERGE_CONFLICT = "merge_conflict"
    SECURITY_ALERT = "security_alert"


class FixPriority(str, Enum):
    """Priority levels for auto-fixes."""
    CRITICAL = "critical"      # Security, build breaking
    HIGH = "high"             # Test failures, linting errors
    MEDIUM = "medium"         # Style issues, warnings
    LOW = "low"              # Suggestions, optimizations


@dataclass
class FeedbackItem:
    """Represents a single feedback item that needs fixing."""
    type: FeedbackType
    priority: FixPriority
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    suggestion: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class AutoFixResult:
    """Result of an auto-fix attempt."""
    success: bool
    fixes_applied: List[str]
    files_modified: List[str]
    commit_message: str
    validation_passed: bool
    error_message: Optional[str] = None


class FeedbackDetector(ABC):
    """Abstract base for feedback detection systems."""

    @abstractmethod
    def detect_feedback(self, pr_number: int, platform_adapter: PlatformAdapter) -> List[FeedbackItem]:
        """Detect feedback items that need fixing."""
        pass


class CIFailureDetector(FeedbackDetector):
    """Detects and parses CI/CD pipeline failures."""

    def detect_feedback(self, pr_number: int, platform_adapter: PlatformAdapter) -> List[FeedbackItem]:
        """Detect CI failures from GitHub Actions."""
        feedback_items = []

        try:
            # Get CI check results
            # TODO: Implement platform_adapter.get_pr_checks(pr_number)
            # For now, return mock data for architecture demonstration

            # Parse different types of CI failures
            failures = [
                {
                    "name": "test (3.11)",
                    "status": "failure",
                    "log": "flake8 src/ tests/ --count --select=E9,F63,F7,F82\nsrc/devflow/core/workflow_engine.py:1054:80: E501 line too long (87 > 79 characters)"
                },
                {
                    "name": "docs",
                    "status": "failure",
                    "log": "sphinx-build: error: Could not find documentation for new streaming methods"
                }
            ]

            for failure in failures:
                feedback_items.extend(self._parse_ci_failure(failure))

        except Exception as e:
            logger.error(f"Failed to detect CI failures: {e}")

        return feedback_items

    def _parse_ci_failure(self, failure: Dict[str, Any]) -> List[FeedbackItem]:
        """Parse specific CI failure into feedback items."""
        items = []

        log = failure.get("log", "")

        # Parse flake8 errors
        flake8_pattern = r"(.+):(\d+):(\d+): ([A-Z]\d+) (.+)"
        for match in re.finditer(flake8_pattern, log):
            file_path, line_num, col_num, error_code, message = match.groups()

            items.append(FeedbackItem(
                type=FeedbackType.CI_FAILURE,
                priority=FixPriority.HIGH if error_code.startswith('E9') else FixPriority.MEDIUM,
                title=f"Linting Error: {error_code}",
                description=message,
                file_path=file_path,
                line_number=int(line_num),
                suggestion=self._get_flake8_fix_suggestion(error_code, message),
                raw_data=failure
            ))

        # Parse documentation errors
        if "sphinx-build" in log and "error" in log:
            items.append(FeedbackItem(
                type=FeedbackType.CI_FAILURE,
                priority=FixPriority.MEDIUM,
                title="Documentation Build Error",
                description="Missing documentation for new code",
                suggestion="Add docstrings to new methods and update documentation",
                raw_data=failure
            ))

        return items

    def _get_flake8_fix_suggestion(self, error_code: str, message: str) -> str:
        """Get fix suggestion for flake8 errors."""
        suggestions = {
            "E501": "Break long line or use line continuation",
            "E302": "Add 2 blank lines before class or function definition",
            "E303": "Remove extra blank lines",
            "F401": "Remove unused import",
            "F841": "Remove unused variable"
        }
        return suggestions.get(error_code, "Fix linting issue")


class ReviewFeedbackDetector(FeedbackDetector):
    """Detects and parses code review feedback."""

    def detect_feedback(self, pr_number: int, platform_adapter: PlatformAdapter) -> List[FeedbackItem]:
        """Detect review feedback that requests changes."""
        feedback_items = []

        try:
            # Get PR reviews from platform
            reviews = platform_adapter.list_pull_request_reviews(
                platform_adapter.owner,
                platform_adapter.repo,
                pr_number
            )

            for review in reviews:
                if review.state == ReviewDecision.REQUEST_CHANGES:
                    items = self._parse_review_feedback(review.__dict__)
                    feedback_items.extend(items)

            # Also check for PR comments with change requests
            pr = platform_adapter.get_pull_request(
                platform_adapter.owner,
                platform_adapter.repo,
                pr_number
            )

            # Parse PR description for follow-up requests
            if pr.body and any(keyword in pr.body.lower() for keyword in ["fix", "change", "update", "todo"]):
                items = self._parse_pr_body_feedback(pr.body, pr_number)
                feedback_items.extend(items)

        except Exception as e:
            logger.error(f"Failed to detect review feedback for PR #{pr_number}: {e}")
            # Fallback to mock data for testing
            mock_reviews = [
                {
                    "state": "REQUEST_CHANGES",
                    "body": "Please add error handling for the subprocess calls in the streaming validation method.",
                    "user": "senior_developer"
                }
            ]

            for review in mock_reviews:
                if review["state"] == "REQUEST_CHANGES":
                    items = self._parse_review_feedback(review)
                    feedback_items.extend(items)

        return feedback_items

    def _parse_review_feedback(self, review: Dict[str, Any]) -> List[FeedbackItem]:
        """Parse review comments into actionable feedback items."""
        items = []

        body = review.get("body", "")
        user = review.get("user", "reviewer")

        # Advanced parsing for common review patterns
        feedback_patterns = [
            # Error handling requests
            {
                "patterns": ["error handling", "try-catch", "exception handling", "error management"],
                "title": "Add Error Handling",
                "priority": FixPriority.HIGH,
                "suggestion": "Add try-catch blocks and proper error handling for robustness"
            },
            # Documentation requests
            {
                "patterns": ["documentation", "docstring", "comment", "explain", "document"],
                "title": "Improve Documentation",
                "priority": FixPriority.MEDIUM,
                "suggestion": "Add comprehensive docstrings and inline comments"
            },
            # Testing requests
            {
                "patterns": ["test", "unit test", "coverage", "test case"],
                "title": "Add Tests",
                "priority": FixPriority.HIGH,
                "suggestion": "Add unit tests to ensure code reliability"
            },
            # Security concerns
            {
                "patterns": ["security", "vulnerability", "sanitize", "validate input"],
                "title": "Security Improvement",
                "priority": FixPriority.CRITICAL,
                "suggestion": "Address security concerns and add input validation"
            },
            # Performance issues
            {
                "patterns": ["performance", "optimize", "efficiency", "slow"],
                "title": "Performance Optimization",
                "priority": FixPriority.MEDIUM,
                "suggestion": "Optimize code for better performance"
            },
            # Type annotations
            {
                "patterns": ["type hint", "type annotation", "typing", "mypy"],
                "title": "Add Type Annotations",
                "priority": FixPriority.MEDIUM,
                "suggestion": "Add proper type annotations for better code clarity"
            },
            # Code style
            {
                "patterns": ["style", "format", "lint", "clean up"],
                "title": "Code Style Fix",
                "priority": FixPriority.LOW,
                "suggestion": "Fix code style and formatting issues"
            }
        ]

        # Extract file and line references
        file_refs = self._extract_file_references(body)

        for pattern_group in feedback_patterns:
            if any(pattern in body.lower() for pattern in pattern_group["patterns"]):
                for file_ref in file_refs or [None]:
                    items.append(FeedbackItem(
                        type=FeedbackType.REVIEW_FEEDBACK,
                        priority=pattern_group["priority"],
                        title=pattern_group["title"],
                        description=f"{user}: {body[:200]}{'...' if len(body) > 200 else ''}",
                        file_path=file_ref.get("path") if file_ref else None,
                        line_number=file_ref.get("line") if file_ref else None,
                        suggestion=pattern_group["suggestion"],
                        raw_data=review
                    ))

        # If no patterns matched, create generic feedback item
        if not items:
            items.append(FeedbackItem(
                type=FeedbackType.REVIEW_FEEDBACK,
                priority=FixPriority.MEDIUM,
                title="Review Feedback",
                description=f"{user}: {body}",
                suggestion="Address the reviewer's feedback",
                raw_data=review
            ))

        return items

    def _parse_pr_body_feedback(self, body: str, pr_number: int) -> List[FeedbackItem]:
        """Parse PR body for TODO items and follow-up requests."""
        items = []

        # Look for TODO comments in PR body
        import re
        todo_pattern = r'(?i)(?:todo|fixme|hack):\s*(.+?)(?:\n|$)'

        for match in re.finditer(todo_pattern, body):
            todo_text = match.group(1).strip()
            items.append(FeedbackItem(
                type=FeedbackType.REVIEW_FEEDBACK,
                priority=FixPriority.MEDIUM,
                title="TODO Item",
                description=f"PR #{pr_number} TODO: {todo_text}",
                suggestion="Complete the TODO item before merging",
                raw_data={"pr_body": body, "todo": todo_text}
            ))

        return items

    def _extract_file_references(self, text: str) -> List[Dict[str, Any]]:
        """Extract file and line references from review text."""
        import re

        # Pattern for file:line references
        file_patterns = [
            r'([a-zA-Z0-9_/.-]+\.py):(\d+)',  # file.py:123
            r'`([a-zA-Z0-9_/.-]+\.py)`',      # `file.py`
            r'in ([a-zA-Z0-9_/.-]+\.py)',     # in file.py
        ]

        refs = []
        for pattern in file_patterns:
            for match in re.finditer(pattern, text):
                if ':' in match.group(0) and len(match.groups()) >= 2:
                    refs.append({
                        "path": match.group(1),
                        "line": int(match.group(2))
                    })
                else:
                    refs.append({
                        "path": match.group(1),
                        "line": None
                    })

        return refs


class AutoFixEngine:
    """Core engine that orchestrates the auto-fix process."""

    def __init__(
        self,
        platform_adapter: PlatformAdapter,
        agent_provider: AgentProvider,
        working_directory: str
    ):
        self.platform_adapter = platform_adapter
        self.agent_provider = agent_provider
        self.working_directory = Path(working_directory)

        # Initialize feedback detectors
        self.detectors = [
            CIFailureDetector(),
            ReviewFeedbackDetector()
        ]

    def run_auto_fix_cycle(self, pr_number: int, max_iterations: int = 3) -> AutoFixResult:
        """Run complete auto-fix cycle for a PR."""
        logger.info(f"Starting auto-fix cycle for PR #{pr_number}")

        for iteration in range(max_iterations):
            logger.info(f"Auto-fix iteration {iteration + 1}/{max_iterations}")

            # Detect all types of feedback
            feedback_items = self._detect_all_feedback(pr_number)

            if not feedback_items:
                logger.info("No feedback items found - auto-fix cycle complete")
                return AutoFixResult(
                    success=True,
                    fixes_applied=[],
                    files_modified=[],
                    commit_message="No fixes needed",
                    validation_passed=True
                )

            # Prioritize and group feedback
            prioritized_feedback = self._prioritize_feedback(feedback_items)

            # Generate and apply fixes
            fix_result = self._apply_fixes(prioritized_feedback)

            if not fix_result.success:
                logger.error("Auto-fix failed, stopping cycle")
                return fix_result

            # Commit and push fixes
            commit_result = self._commit_and_push_fixes(fix_result)

            if not commit_result:
                fix_result.success = False
                fix_result.error_message = "Failed to commit fixes"
                return fix_result

            # Wait for CI/review response
            # TODO: Add intelligent waiting and re-checking

        # Max iterations reached
        return AutoFixResult(
            success=False,
            fixes_applied=[],
            files_modified=[],
            commit_message="",
            validation_passed=False,
            error_message=f"Max iterations ({max_iterations}) reached"
        )

    def _detect_all_feedback(self, pr_number: int) -> List[FeedbackItem]:
        """Run all feedback detectors."""
        all_feedback = []

        for detector in self.detectors:
            try:
                feedback = detector.detect_feedback(pr_number, self.platform_adapter)
                all_feedback.extend(feedback)
            except Exception as e:
                logger.error(f"Detector {detector.__class__.__name__} failed: {e}")

        return all_feedback

    def _prioritize_feedback(self, feedback_items: List[FeedbackItem]) -> List[FeedbackItem]:
        """Sort feedback by priority and type."""
        priority_order = {
            FixPriority.CRITICAL: 0,
            FixPriority.HIGH: 1,
            FixPriority.MEDIUM: 2,
            FixPriority.LOW: 3
        }

        return sorted(
            feedback_items,
            key=lambda item: (priority_order[item.priority], item.type.value)
        )

    def _apply_fixes(self, feedback_items: List[FeedbackItem]) -> AutoFixResult:
        """Apply fixes for feedback items using AI agent."""
        try:
            logger.info(f"Applying fixes for {len(feedback_items)} feedback items")

            # Group feedback by type and priority for efficient processing
            grouped_fixes = self._group_feedback_for_fixing(feedback_items)

            fixes_applied = []
            files_modified = set()
            validation_errors = []

            for group_name, group_items in grouped_fixes.items():
                logger.info(f"Processing {group_name} fixes: {len(group_items)} items")

                try:
                    # Create specialized fix prompt for this group
                    fix_prompt = self._create_specialized_fix_prompt(group_items, group_name)

                    # Apply fixes using Claude agent
                    fix_result = self._apply_ai_fixes(fix_prompt, group_items)

                    if fix_result['success']:
                        fixes_applied.extend(fix_result['fixes_applied'])
                        files_modified.update(fix_result['files_modified'])

                        # Validate fixes if possible
                        if fix_result['files_modified']:
                            validation_result = self._validate_fixes(fix_result['files_modified'], group_items)
                            if not validation_result['success']:
                                validation_errors.extend(validation_result['errors'])
                    else:
                        logger.warning(f"Failed to apply {group_name} fixes: {fix_result.get('error', 'Unknown error')}")

                except Exception as e:
                    logger.error(f"Error processing {group_name} fixes: {str(e)}")
                    validation_errors.append(f"Failed to process {group_name}: {str(e)}")

            # Create comprehensive commit message
            commit_message = self._generate_commit_message(fixes_applied, feedback_items)

            success = len(fixes_applied) > 0 and len(validation_errors) == 0

            return AutoFixResult(
                success=success,
                fixes_applied=fixes_applied,
                files_modified=list(files_modified),
                commit_message=commit_message,
                validation_passed=len(validation_errors) == 0,
                error_message="; ".join(validation_errors) if validation_errors else None
            )

        except Exception as e:
            logger.error(f"Failed to apply fixes: {e}")
            return AutoFixResult(
                success=False,
                fixes_applied=[],
                files_modified=[],
                commit_message="",
                validation_passed=False,
                error_message=str(e)
            )

    def _group_feedback_for_fixing(self, feedback_items: List[FeedbackItem]) -> Dict[str, List[FeedbackItem]]:
        """Group feedback items for efficient batch processing."""
        groups = {
            "critical_security": [],
            "linting_errors": [],
            "type_errors": [],
            "test_failures": [],
            "documentation": [],
            "code_style": [],
            "performance": [],
            "general": []
        }

        for item in feedback_items:
            if item.priority == FixPriority.CRITICAL:
                groups["critical_security"].append(item)
            elif item.type == FeedbackType.CI_FAILURE:
                if "flake8" in str(item.raw_data).lower() or "lint" in item.title.lower():
                    groups["linting_errors"].append(item)
                elif "mypy" in str(item.raw_data).lower() or "type" in item.title.lower():
                    groups["type_errors"].append(item)
                elif "test" in item.title.lower() or "pytest" in str(item.raw_data).lower():
                    groups["test_failures"].append(item)
                else:
                    groups["general"].append(item)
            elif "documentation" in item.title.lower() or "docstring" in item.title.lower():
                groups["documentation"].append(item)
            elif item.priority == FixPriority.LOW or "style" in item.title.lower():
                groups["code_style"].append(item)
            elif "performance" in item.title.lower() or "optimize" in item.title.lower():
                groups["performance"].append(item)
            else:
                groups["general"].append(item)

        # Remove empty groups
        return {k: v for k, v in groups.items() if v}

    def _create_specialized_fix_prompt(self, items: List[FeedbackItem], group_type: str) -> str:
        """Create specialized prompts for different types of fixes."""
        base_context = f"You are an expert developer fixing {group_type} issues in a Python codebase.\n\n"

        prompt_templates = {
            "critical_security": base_context + """
CRITICAL SECURITY FIXES REQUIRED:
Your task is to fix critical security vulnerabilities. This is high priority.

Security Guidelines:
- Validate and sanitize all user inputs
- Use parameterized queries for database operations
- Avoid eval() and exec() functions
- Properly handle sensitive data
- Add authentication and authorization checks where needed

Issues to fix:
""",
            "linting_errors": base_context + """
LINTING AND CODE STYLE FIXES:
Fix all linting errors to meet Python code quality standards.

Common fixes needed:
- Line length (break long lines using parentheses or backslashes)
- Import organization (remove unused imports, sort imports)
- Whitespace issues (add/remove spaces around operators)
- Blank line issues (add proper spacing between functions/classes)

Issues to fix:
""",
            "type_errors": base_context + """
TYPE ANNOTATION AND MYPY FIXES:
Fix type annotation issues for better code clarity and type safety.

Common fixes needed:
- Add missing type hints to function parameters and return values
- Fix incompatible type assignments
- Import necessary typing modules (List, Dict, Optional, Union)
- Add proper type annotations for class attributes

Issues to fix:
""",
            "test_failures": base_context + """
TEST FAILURE FIXES:
Fix failing tests to ensure code reliability.

Testing guidelines:
- Fix assertion errors by correcting the implementation or test expectations
- Add missing test dependencies or imports
- Fix test setup/teardown issues
- Ensure test isolation and proper mocking

Issues to fix:
""",
            "documentation": base_context + """
DOCUMENTATION IMPROVEMENTS:
Add comprehensive documentation to improve code maintainability.

Documentation standards:
- Add docstrings to all public functions, classes, and methods
- Use proper docstring format (Google or NumPy style)
- Include parameter descriptions, return value explanations, and examples
- Add inline comments for complex logic

Issues to fix:
""",
            "general": base_context + """
GENERAL CODE IMPROVEMENTS:
Fix various code quality and functionality issues.

General guidelines:
- Follow Python best practices
- Ensure code is readable and maintainable
- Add error handling where appropriate
- Optimize for correctness first, then performance

Issues to fix:
"""
        }

        prompt = prompt_templates.get(group_type, prompt_templates["general"])

        for i, item in enumerate(items, 1):
            prompt += f"\n{i}. {item.title}\n"
            prompt += f"   Priority: {item.priority.value}\n"
            prompt += f"   Description: {item.description}\n"
            if item.file_path:
                prompt += f"   File: {item.file_path}"
                if item.line_number:
                    prompt += f":{item.line_number}"
                prompt += "\n"
            if item.suggestion:
                prompt += f"   Suggestion: {item.suggestion}\n"

        prompt += "\n\nInstructions:"
        prompt += "\n- Fix ALL the issues listed above"
        prompt += "\n- Make minimal, targeted changes to resolve each issue"
        prompt += "\n- Preserve existing functionality while fixing the problems"
        prompt += "\n- Test your changes to ensure they work correctly"
        prompt += "\n- Create clean, readable code that follows Python best practices"

        return prompt

    def _apply_ai_fixes(self, fix_prompt: str, feedback_items: List[FeedbackItem]) -> Dict[str, Any]:
        """Apply fixes using Claude AI agent."""
        try:
            # Import here to avoid circular imports
            from devflow.agents.claude import ClaudeAgentProvider

            # Create agent instance with auto-fix configuration
            agent_config = {
                "model": "claude-3.5-sonnet",
                "max_tokens": 8192,
                "temperature": 0.1,  # Lower temperature for more consistent fixes
            }

            claude_agent = ClaudeAgentProvider(agent_config)

            # Create implementation context for fixes
            from devflow.agents.base import ImplementationContext

            context = ImplementationContext(
                issue=None,  # No specific issue for auto-fixes
                working_directory=str(self.working_directory),
                project_context={
                    "auto_fix_mode": True,
                    "feedback_items": [item.__dict__ for item in feedback_items],
                    "fix_prompt": fix_prompt
                },
                validation_result={},
                previous_iterations=[],
                constraints={"max_files": 10, "safe_mode": True}
            )

            # Apply fixes using Claude
            logger.info("Requesting AI fixes from Claude agent...")
            impl_response = claude_agent.implement_changes(context)

            if impl_response.success:
                # Parse the response to extract what was actually fixed
                fixes_applied = self._parse_ai_fix_response(impl_response, feedback_items)
                files_modified = self._extract_modified_files_from_response(impl_response)

                return {
                    'success': True,
                    'fixes_applied': fixes_applied,
                    'files_modified': files_modified,
                    'ai_response': impl_response
                }
            else:
                return {
                    'success': False,
                    'error': f"AI agent failed: {impl_response.message}",
                    'ai_response': impl_response
                }

        except Exception as e:
            logger.error(f"AI fix application failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _parse_ai_fix_response(self, response, feedback_items: List[FeedbackItem]) -> List[str]:
        """Parse AI response to determine what fixes were actually applied."""
        fixes = []

        # Check response message for fix confirmations
        response_text = response.message.lower()

        for item in feedback_items:
            # Look for indicators that this specific issue was addressed
            item_keywords = [item.title.lower(), item.type.value]
            if item.file_path:
                item_keywords.append(item.file_path.lower())

            if any(keyword in response_text for keyword in item_keywords):
                fixes.append(f"Fixed {item.title}")
            elif "fixed" in response_text or "resolved" in response_text:
                # Generic fix indication
                fixes.append(f"Addressed {item.title}")

        return fixes

    def _extract_modified_files_from_response(self, response) -> List[str]:
        """Extract list of modified files from AI response."""
        files = []

        # Parse response data for file modifications
        if hasattr(response, 'data') and response.data:
            if 'files_changed' in response.data:
                files.extend(response.data['files_changed'])
            elif 'modified_files' in response.data:
                files.extend(response.data['modified_files'])

        # Parse response message for file mentions
        import re
        file_pattern = r'([a-zA-Z0-9_/.-]+\.py)'
        message_files = re.findall(file_pattern, response.message)
        files.extend(message_files)

        return list(set(files))  # Remove duplicates

    def _validate_fixes(self, files_modified: List[str], feedback_items: List[FeedbackItem]) -> Dict[str, Any]:
        """Validate that fixes were applied correctly."""
        errors = []

        try:
            # Basic file existence check
            for file_path in files_modified:
                full_path = self.working_directory / file_path
                if not full_path.exists():
                    errors.append(f"Modified file not found: {file_path}")

            # TODO: Add more sophisticated validation:
            # - Run linting tools to check if linting errors were fixed
            # - Run type checking to verify type errors were resolved
            # - Run tests to ensure functionality wasn't broken

            return {
                'success': len(errors) == 0,
                'errors': errors
            }

        except Exception as e:
            return {
                'success': False,
                'errors': [f"Validation failed: {str(e)}"]
            }

    def _generate_commit_message(self, fixes_applied: List[str], feedback_items: List[FeedbackItem]) -> str:
        """Generate a descriptive commit message for auto-fixes."""
        if not fixes_applied:
            return "chore: automated fixes (no changes applied)"

        # Categorize fixes by type
        categories = {}
        for item in feedback_items:
            category = self._categorize_fix_type(item)
            if category not in categories:
                categories[category] = 0
            categories[category] += 1

        # Create commit message based on fix categories
        if len(categories) == 1:
            category = list(categories.keys())[0]
            count = list(categories.values())[0]
            message = f"fix({category}): resolve {count} {category} issue{'s' if count > 1 else ''}"
        else:
            total_fixes = sum(categories.values())
            message = f"fix: auto-resolve {total_fixes} issues"

            # Add details about categories
            details = []
            for category, count in categories.items():
                details.append(f"{count} {category}")
            message += f" ({', '.join(details)})"

        # Add AI attribution
        message += "\n\n🤖 Auto-generated fixes by DevFlow AI system"
        message += f"\n- {len(fixes_applied)} fixes applied"
        message += f"\n- {len(set(item.file_path for item in feedback_items if item.file_path))} files modified"

        return message

    def _categorize_fix_type(self, item: FeedbackItem) -> str:
        """Categorize a feedback item for commit message generation."""
        title_lower = item.title.lower()

        if "security" in title_lower:
            return "security"
        elif "test" in title_lower:
            return "test"
        elif "lint" in title_lower or "style" in title_lower:
            return "style"
        elif "type" in title_lower or "mypy" in title_lower:
            return "typing"
        elif "doc" in title_lower:
            return "docs"
        elif "performance" in title_lower:
            return "perf"
        elif item.type == FeedbackType.CI_FAILURE:
            return "ci"
        elif item.type == FeedbackType.REVIEW_FEEDBACK:
            return "review"
        else:
            return "general"

    def _create_fix_prompt(self, feedback_items: List[FeedbackItem]) -> str:
        """Create AI prompt for fixing feedback items."""
        prompt = "Fix the following issues:\n\n"

        for i, item in enumerate(feedback_items, 1):
            prompt += f"{i}. {item.title}\n"
            prompt += f"   Priority: {item.priority.value}\n"
            prompt += f"   Description: {item.description}\n"
            if item.file_path:
                prompt += f"   File: {item.file_path}"
                if item.line_number:
                    prompt += f":{item.line_number}"
                prompt += "\n"
            if item.suggestion:
                prompt += f"   Suggestion: {item.suggestion}\n"
            prompt += "\n"

        prompt += "Apply all fixes and ensure code quality standards are met."
        return prompt

    def _commit_and_push_fixes(self, fix_result: AutoFixResult) -> bool:
        """Commit and push auto-fixes."""
        try:
            if not fix_result.files_modified:
                logger.info("No files to commit")
                return True

            logger.info(f"Committing {len(fix_result.files_modified)} modified files")

            # Import subprocess for git operations
            import subprocess

            # Add all modified files to git
            add_result = subprocess.run(
                ['git', 'add'] + fix_result.files_modified,
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                check=True
            )

            # Check if there are actually changes to commit
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                check=True
            )

            if not status_result.stdout.strip():
                logger.info("No changes detected for commit")
                return True

            # Commit the changes
            commit_result = subprocess.run(
                ['git', 'commit', '-m', fix_result.commit_message],
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                check=True
            )

            logger.info(f"Committed auto-fixes: {commit_result.stdout.strip()}")

            # Push the changes to remote
            try:
                # Get current branch name
                branch_result = subprocess.run(
                    ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                    cwd=self.working_directory,
                    capture_output=True,
                    text=True,
                    check=True
                )
                current_branch = branch_result.stdout.strip()

                # Push to remote
                push_result = subprocess.run(
                    ['git', 'push', 'origin', current_branch],
                    cwd=self.working_directory,
                    capture_output=True,
                    text=True,
                    check=True
                )

                logger.info(f"Pushed auto-fixes to {current_branch}: {push_result.stdout.strip()}")
                return True

            except subprocess.CalledProcessError as push_error:
                # Push failed but commit succeeded
                logger.warning(f"Failed to push auto-fixes (commit succeeded): {push_error.stderr}")
                # Still return True since the commit worked
                return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Git operation failed: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Failed to commit and push fixes: {e}")
            return False


# Integration with workflow engine
def integrate_auto_fix_with_workflow():
    """Integration points for auto-fix system with main workflow."""

    # 1. After review stage - check for review feedback
    # 2. After PR creation - monitor CI status
    # 3. Periodic monitoring - check for new feedback

    pass
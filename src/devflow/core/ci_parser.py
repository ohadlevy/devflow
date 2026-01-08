"""CI Failure Detection and Parsing System.

Parses GitHub Actions logs and other CI systems to extract actionable
failure information for the auto-fix system.
"""

import json
import re
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from devflow.core.auto_fix import FeedbackItem, FeedbackType, FixPriority

logger = logging.getLogger(__name__)


@dataclass
class CIFailure:
    """Represents a specific CI failure with context."""
    job_name: str
    step_name: str
    error_type: str
    error_message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    raw_log: Optional[str] = None


class GitHubActionsParser:
    """Parser for GitHub Actions CI failures."""

    def __init__(self):
        self.parsers = {
            'flake8': self._parse_flake8_errors,
            'black': self._parse_black_errors,
            'mypy': self._parse_mypy_errors,
            'pytest': self._parse_pytest_errors,
            'sphinx': self._parse_sphinx_errors,
            'isort': self._parse_isort_errors
        }

    def parse_ci_failures(self, pr_number: int, platform_adapter) -> List[FeedbackItem]:
        """Parse CI failures from GitHub Actions."""
        feedback_items = []

        try:
            # Get CI check results from GitHub API
            # Using gh CLI to get the actual failure logs
            failures = self._get_ci_failures(pr_number)

            for failure in failures:
                items = self._parse_failure(failure)
                feedback_items.extend(items)

        except Exception as e:
            logger.error(f"Failed to parse CI failures for PR #{pr_number}: {e}")

        return feedback_items

    def _get_ci_failures(self, pr_number: int) -> List[Dict]:
        """Get actual CI failure data using gh CLI."""
        import subprocess

        try:
            # Get check runs for the PR
            result = subprocess.run([
                'gh', 'api', f'/repos/{{owner}}/{{repo}}/pulls/{pr_number}/checks'
            ], capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.warning(f"Failed to get CI checks: {result.stderr}")
                return []

            data = json.loads(result.stdout)
            failures = []

            for check in data.get('check_runs', []):
                if check.get('conclusion') == 'failure':
                    failure_data = {
                        'name': check.get('name', ''),
                        'status': 'failure',
                        'log_url': check.get('details_url', ''),
                        'output': check.get('output', {})
                    }

                    # Try to get the actual log content
                    if check.get('id'):
                        log_content = self._get_check_log(check['id'])
                        failure_data['log'] = log_content

                    failures.append(failure_data)

            return failures

        except subprocess.TimeoutExpired:
            logger.error("Timeout getting CI check data")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse CI check data: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting CI failures: {e}")
            return []

    def _get_check_log(self, check_id: int) -> str:
        """Get detailed log for a specific check run."""
        try:
            import subprocess
            result = subprocess.run([
                'gh', 'api', f'/repos/{{owner}}/{{repo}}/check-runs/{check_id}/annotations'
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                annotations = json.loads(result.stdout)
                return '\n'.join(ann.get('message', '') for ann in annotations)

        except Exception as e:
            logger.debug(f"Could not get check log for {check_id}: {e}")

        return ""

    def _parse_failure(self, failure: Dict) -> List[FeedbackItem]:
        """Parse a specific CI failure into feedback items."""
        job_name = failure.get('name', '').lower()
        log_content = failure.get('log', '')

        feedback_items = []

        # Determine parser based on job name or log content
        for parser_key, parser_func in self.parsers.items():
            if parser_key in job_name or parser_key in log_content.lower():
                try:
                    items = parser_func(failure, log_content)
                    feedback_items.extend(items)
                except Exception as e:
                    logger.error(f"Parser {parser_key} failed: {e}")

        # Fallback generic parsing if no specific parser matched
        if not feedback_items:
            feedback_items.extend(self._parse_generic_failure(failure, log_content))

        return feedback_items

    def _parse_flake8_errors(self, failure: Dict, log_content: str) -> List[FeedbackItem]:
        """Parse flake8 linting errors."""
        items = []

        # Pattern: ./src/devflow/core/workflow_engine.py:1054:80: E501 line too long
        flake8_pattern = r'(.+?):(\d+):(\d+): ([A-Z]\d+) (.+)'

        for match in re.finditer(flake8_pattern, log_content):
            file_path, line_num, col_num, error_code, message = match.groups()

            # Determine priority based on error code
            priority = FixPriority.HIGH if error_code.startswith('E9') else FixPriority.MEDIUM
            if error_code.startswith('W'):
                priority = FixPriority.LOW

            items.append(FeedbackItem(
                type=FeedbackType.CI_FAILURE,
                priority=priority,
                title=f"Linting Error: {error_code}",
                description=f"{message} (Line {line_num}:{col_num})",
                file_path=file_path.strip('./'),
                line_number=int(line_num),
                suggestion=self._get_flake8_fix_suggestion(error_code, message),
                raw_data={'failure': failure, 'error_code': error_code}
            ))

        return items

    def _parse_black_errors(self, failure: Dict, log_content: str) -> List[FeedbackItem]:
        """Parse black formatting errors."""
        items = []

        # Black outputs "would reformat" lines for files that need formatting
        black_pattern = r'would reformat (.+)'

        for match in re.finditer(black_pattern, log_content):
            file_path = match.group(1)

            items.append(FeedbackItem(
                type=FeedbackType.CI_FAILURE,
                priority=FixPriority.MEDIUM,
                title="Code Formatting Issue",
                description=f"File needs reformatting with black: {file_path}",
                file_path=file_path,
                suggestion=f"Run 'black {file_path}' to fix formatting",
                raw_data={'failure': failure}
            ))

        # Check for specific formatting errors
        if "error:" in log_content.lower() and "black" in failure.get('name', '').lower():
            items.append(FeedbackItem(
                type=FeedbackType.CI_FAILURE,
                priority=FixPriority.MEDIUM,
                title="Black Formatting Error",
                description="Black encountered an error during formatting",
                suggestion="Check file syntax and black configuration",
                raw_data={'failure': failure, 'log': log_content}
            ))

        return items

    def _parse_mypy_errors(self, failure: Dict, log_content: str) -> List[FeedbackItem]:
        """Parse mypy type checking errors."""
        items = []

        # Pattern: src/devflow/core/workflow.py:45: error: Argument 1 to "func" has incompatible type
        mypy_pattern = r'(.+?):(\d+): (error|warning): (.+)'

        for match in re.finditer(mypy_pattern, log_content):
            file_path, line_num, severity, message = match.groups()

            priority = FixPriority.HIGH if severity == 'error' else FixPriority.MEDIUM

            items.append(FeedbackItem(
                type=FeedbackType.CI_FAILURE,
                priority=priority,
                title=f"Type Error: {severity.title()}",
                description=message,
                file_path=file_path,
                line_number=int(line_num),
                suggestion=self._get_mypy_fix_suggestion(message),
                raw_data={'failure': failure, 'severity': severity}
            ))

        return items

    def _parse_pytest_errors(self, failure: Dict, log_content: str) -> List[FeedbackItem]:
        """Parse pytest test failures."""
        items = []

        # Pattern: FAILED tests/test_file.py::test_function - AssertionError: message
        pytest_failure_pattern = r'FAILED (.+?)::(.+?) - (.+)'

        for match in re.finditer(pytest_failure_pattern, log_content):
            file_path, test_name, error_message = match.groups()

            items.append(FeedbackItem(
                type=FeedbackType.CI_FAILURE,
                priority=FixPriority.HIGH,
                title=f"Test Failure: {test_name}",
                description=error_message,
                file_path=file_path,
                suggestion=f"Fix the failing test: {test_name}",
                raw_data={'failure': failure, 'test_name': test_name}
            ))

        # Parse test collection errors
        if "collection failed" in log_content.lower():
            items.append(FeedbackItem(
                type=FeedbackType.CI_FAILURE,
                priority=FixPriority.CRITICAL,
                title="Test Collection Failed",
                description="Tests cannot be collected due to syntax or import errors",
                suggestion="Check for syntax errors and import issues in test files",
                raw_data={'failure': failure}
            ))

        return items

    def _parse_sphinx_errors(self, failure: Dict, log_content: str) -> List[FeedbackItem]:
        """Parse Sphinx documentation build errors."""
        items = []

        # Pattern: WARNING: autodoc: failed to import module 'module_name'
        if "sphinx" in failure.get('name', '').lower():
            if "warning" in log_content.lower() or "error" in log_content.lower():
                items.append(FeedbackItem(
                    type=FeedbackType.CI_FAILURE,
                    priority=FixPriority.MEDIUM,
                    title="Documentation Build Issue",
                    description="Sphinx documentation build encountered issues",
                    suggestion="Check for missing docstrings or broken documentation links",
                    raw_data={'failure': failure}
                ))

        return items

    def _parse_isort_errors(self, failure: Dict, log_content: str) -> List[FeedbackItem]:
        """Parse isort import sorting errors."""
        items = []

        # isort outputs files that would be reformatted
        if "fixing" in log_content.lower() or "import" in log_content.lower():
            items.append(FeedbackItem(
                type=FeedbackType.CI_FAILURE,
                priority=FixPriority.MEDIUM,
                title="Import Sorting Issue",
                description="Import statements need to be sorted",
                suggestion="Run 'isort .' to fix import sorting",
                raw_data={'failure': failure}
            ))

        return items

    def _parse_generic_failure(self, failure: Dict, log_content: str) -> List[FeedbackItem]:
        """Parse generic CI failures when no specific parser applies."""
        items = []

        job_name = failure.get('name', 'Unknown')

        items.append(FeedbackItem(
            type=FeedbackType.CI_FAILURE,
            priority=FixPriority.HIGH,
            title=f"CI Failure: {job_name}",
            description=f"Job '{job_name}' failed - check logs for details",
            suggestion="Review the CI logs and fix the underlying issue",
            raw_data={'failure': failure, 'log_content': log_content[:500]}
        ))

        return items

    def _get_flake8_fix_suggestion(self, error_code: str, message: str) -> str:
        """Get specific fix suggestion for flake8 error codes."""
        suggestions = {
            'E501': "Break the long line using parentheses, backslashes, or split into multiple statements",
            'E302': "Add two blank lines before the class or function definition",
            'E303': "Remove the extra blank lines",
            'E231': "Add whitespace after comma, colon, or semicolon",
            'E225': "Add whitespace around operator",
            'F401': "Remove the unused import or add '# noqa: F401' if intentionally unused",
            'F841': "Use the variable or remove it if not needed",
            'W503': "Break before binary operator instead of after",
            'E711': "Use 'is' or 'is not' instead of '==' or '!=' with None/True/False"
        }

        base_suggestion = suggestions.get(error_code, "Fix the linting issue")

        # Add context-specific suggestions
        if "line too long" in message:
            return f"{base_suggestion}. Current line is too long."
        elif "imported but unused" in message:
            return f"{base_suggestion}. The import is not being used in this file."

        return base_suggestion

    def _get_mypy_fix_suggestion(self, message: str) -> str:
        """Get fix suggestion for mypy errors."""
        if "incompatible type" in message:
            return "Check the type annotations and ensure they match the actual values"
        elif "has no attribute" in message:
            return "Verify the object has the expected attribute or add proper type checks"
        elif "Cannot determine type" in message:
            return "Add explicit type annotations to help mypy understand the types"
        else:
            return "Review the type error and add proper type annotations or fixes"


def integrate_ci_parser_with_auto_fix():
    """Integration point for CI parser with auto-fix system."""

    # This would be called from the auto-fix engine's CI failure detector
    # to use the concrete GitHub Actions parser instead of the mock one

    from devflow.core.auto_fix import CIFailureDetector

    class EnhancedCIFailureDetector(CIFailureDetector):
        """Enhanced CI failure detector with real GitHub Actions parsing."""

        def __init__(self):
            self.parser = GitHubActionsParser()

        def detect_feedback(self, pr_number: int, platform_adapter) -> List[FeedbackItem]:
            """Use real GitHub Actions parser."""
            return self.parser.parse_ci_failures(pr_number, platform_adapter)

    return EnhancedCIFailureDetector()
"""Claude AI Agent Provider.

This module provides Claude Code and Claude API integration for DevFlow,
preserving the sophisticated patterns from the original embedded system.
"""

import json
import logging
import subprocess
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
)
from devflow.exceptions import AgentError

logger = logging.getLogger(__name__)


class ClaudeAgentProvider(AgentProvider):
    """Claude AI agent provider using Claude Code CLI.

    Provides intelligent automation capabilities through Claude Code integration,
    preserving the sophisticated prompting and context management from the
    original embedded pipeline system.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize Claude agent provider.

        Args:
            config: Provider configuration

        Raises:
            AgentError: If configuration is invalid
        """
        # Set attributes first before calling super() which validates config
        self.use_claude_cli = config.get("use_claude_cli", True)
        self.api_key = config.get("api_key")
        self.model = config.get("model", "claude-3.5-sonnet")

        super().__init__(config)

    @property
    def name(self) -> str:
        """Agent provider name."""
        return "claude"

    @property
    def display_name(self) -> str:
        """Human-readable provider name."""
        return "Claude"

    @property
    def capabilities(self) -> List[AgentCapability]:
        """List of capabilities this provider supports."""
        return [
            AgentCapability.VALIDATION,
            AgentCapability.IMPLEMENTATION,
            AgentCapability.REVIEW,
            AgentCapability.ANALYSIS,
        ]

    @property
    def max_context_size(self) -> int:
        """Maximum context size for this provider."""
        return 200000  # Claude's context window

    def _validate_config(self) -> None:
        """Validate Claude-specific configuration."""
        if self.use_claude_cli:
            # Check if Claude Code CLI is available
            try:
                result = subprocess.run(
                    ["claude", "--version"], capture_output=True, text=True, check=False, timeout=10
                )
                if result.returncode != 0:
                    raise AgentError(
                        "Claude Code CLI not found. Install from: https://claude.com/claude-code",
                        agent_type=self.name,
                    )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                raise AgentError("Claude Code CLI not available", agent_type=self.name)
        else:
            if not self.api_key:
                raise AgentError(
                    "Claude API key required when not using Claude Code CLI", agent_type=self.name
                )

    def validate_connection(self) -> bool:
        """Test connection to Claude service.

        Returns:
            True if connection is successful

        Raises:
            AgentError: If connection validation fails
        """
        if self.use_claude_cli:
            try:
                # Test basic Claude Code CLI functionality
                result = subprocess.run(
                    ["claude", "--help"], capture_output=True, text=True, check=True, timeout=10
                )
                return result.returncode == 0
            except Exception as e:
                raise AgentError(f"Claude CLI connection failed: {str(e)}") from e
        else:
            # TODO: Implement Claude API validation
            logger.warning("Claude API validation not yet implemented")
            return True

    def _run_claude_command(
        self,
        prompt: str,
        context_files: List[str] = None,
        timeout: int = 300,
        allowed_tools: List[str] = None,
        working_directory: str = None,
    ) -> str:
        """Run Claude Code CLI command with sophisticated permission system.

        Based on the original pipeline's permission and guidance approach.

        Args:
            prompt: Prompt to send to Claude
            context_files: Files to include as context (unused - using --add-dir instead)
            timeout: Command timeout
            allowed_tools: Whitelist of tools/operations Claude can use
            working_directory: Working directory for Claude (enables --add-dir)

        Returns:
            Claude's response

        Raises:
            AgentError: If command fails
        """
        try:
            args = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose"]

            # Add sophisticated permission system from original pipeline
            if allowed_tools:
                args.extend(["--allowedTools", " ".join(allowed_tools)])

            if working_directory:
                args.extend(["--add-dir", str(working_directory)])

            from rich.console import Console

            console = Console()

            console.print("[cyan]🚀 Starting Claude streaming session...[/cyan]")

            # Use Popen for real-time streaming like the original
            process = subprocess.Popen(
                args,
                cwd=working_directory,  # Critical: set working directory like original
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered for real-time output
            )

            stdout_lines = []

            # Stream and display progress in real-time
            try:
                while True:
                    if process.poll() is not None:
                        # Process finished, read remaining output
                        remaining = process.stdout.read()
                        if remaining:
                            for line in remaining.split("\n"):
                                if line.strip():
                                    formatted = self._format_stream_json(line)
                                    if formatted:
                                        console.print(formatted, end="")
                                    stdout_lines.append(line)
                        break

                    # Read line-by-line for real-time progress
                    line = process.stdout.readline()
                    if line:
                        formatted = self._format_stream_json(line)
                        if formatted:
                            console.print(formatted, end="")
                        stdout_lines.append(line)

            except Exception as stream_error:
                console.print(f"[red]Streaming error: {stream_error}[/red]")

            # Get final result
            process.wait(timeout=timeout)
            full_output = "".join(stdout_lines)

            if process.returncode != 0:
                stderr_output = process.stderr.read() if process.stderr else "Unknown error"
                raise subprocess.CalledProcessError(process.returncode, args, stderr=stderr_output)

            console.print("[green]✅ Claude session completed[/green]")
            return full_output

        except subprocess.TimeoutExpired as e:
            if "process" in locals():
                process.kill()
            raise AgentError(
                f"Claude command timed out after {timeout}s", agent_type=self.name
            ) from e

        except subprocess.CalledProcessError as e:
            error_msg = f"Claude command failed: {e.stderr or str(e)}"
            raise AgentError(error_msg, agent_type=self.name) from e

        except Exception as e:
            raise AgentError(f"Claude execution failed: {str(e)}") from e

    def _format_stream_json(self, line: str) -> str:
        """Format a stream-json line for real-time progress display.

        Based on original pipeline's _format_stream_json method.

        Args:
            line: JSON line from Claude stream-json output

        Returns:
            Formatted string for display, or empty string if nothing to show
        """
        try:
            import json

            data = json.loads(line.strip())
            msg_type = data.get("type")

            if msg_type == "system":
                subtype = data.get("subtype")
                if subtype == "init":
                    model = data.get("model", "unknown")
                    return f"🔧 Session initialized (model: {model})\n"
                return ""

            elif msg_type == "assistant":
                message = data.get("message", {})
                content = message.get("content", [])

                output_parts = []
                for item in content:
                    if item.get("type") == "text":
                        text = item.get("text", "").strip()
                        if text:
                            # Show first 100 chars of AI thinking for progress
                            display_text = text[:100] + "..." if len(text) > 100 else text
                            output_parts.append(f"💭 {display_text}")

                    elif item.get("type") == "tool_use":
                        tool_name = item.get("name")
                        tool_input = item.get("input", {})

                        # Show tool usage for progress tracking
                        if tool_name == "Read" and "file_path" in tool_input:
                            file_path = tool_input["file_path"].split("/")[-1]  # Just filename
                            output_parts.append(f"📖 Reading {file_path}")
                        elif tool_name == "Edit":
                            file_path = tool_input.get("file_path", "file").split("/")[-1]
                            output_parts.append(f"✏️  Editing {file_path}")
                        elif tool_name == "Write":
                            file_path = tool_input.get("file_path", "file").split("/")[-1]
                            output_parts.append(f"📝 Writing {file_path}")
                        else:
                            output_parts.append(f"🔧 Using {tool_name}")

                return "\n".join(output_parts) + "\n" if output_parts else ""

            return ""

        except (json.JSONDecodeError, KeyError, AttributeError):
            return ""

    def _validate_issue_impl(self, context: ValidationContext) -> ValidationResponse:
        """Implementation-specific issue validation."""
        try:
            # Build validation prompt based on the original sophisticated system
            prompt = self._build_validation_prompt(context)

            # Run Claude validation with permission system from original
            if self.use_claude_cli:
                # Define allowed tools for validation (limited read-only operations)
                allowed_tools = ["Read", "Grep", "Glob", "TodoWrite"]

                response_text = self._run_claude_command(
                    prompt,
                    timeout=180,
                    allowed_tools=allowed_tools,
                    working_directory=None,  # Validation runs in project root
                )
            else:
                # TODO: Implement Claude API call
                response_text = "Validation not yet implemented for Claude API"

            # Parse response (simplified - would need full JSON parsing in real implementation)
            result = self._parse_validation_response(response_text, context)

            confidence = self._calculate_confidence(response_text, "validation")

            return ValidationResponse(
                success=True,
                message=response_text,
                data={"raw_response": response_text},
                result=result,
                confidence=confidence,
                reasoning="Claude analysis of issue requirements and feasibility",
            )

        except Exception as e:
            return ValidationResponse(
                success=False,
                message=f"Validation failed: {str(e)}",
                data={"error": str(e)},
                result=ValidationResult.INVALID,
                confidence=0.0,
            )

    def _build_validation_prompt(self, context: ValidationContext) -> str:
        """Build sophisticated validation prompt."""
        issue = context.issue
        maturity = context.maturity_level

        prompt = f"""You are a senior software engineer validating this GitHub issue for automated implementation.

# ISSUE ANALYSIS REQUEST

## Issue Details
**Issue #**: {issue.number}
**Title**: {issue.title}
**Author**: {issue.author}
**Labels**: {', '.join(issue.labels) if issue.labels else 'None'}
**Created**: {issue.created_at}

## Description
{issue.body}

## Project Context
- **Maturity Level**: {maturity}
- **Previous Attempts**: {len(context.previous_attempts)}
- **Quality Standards**: {"High" if maturity in ["stable", "mature"] else "Standard"}

## Validation Requirements

Analyze this issue for automated implementation readiness. Consider:

### 1. Clarity & Scope
- Is the problem statement clear and unambiguous?
- Are acceptance criteria well-defined or derivable?
- Is the scope appropriately bounded for automated implementation?

### 2. Implementation Feasibility
- Can this be implemented without human design decisions?
- Are there clear technical approaches available?
- Are dependencies and requirements obvious?

### 3. Risk Assessment
- What could go wrong during automated implementation?
- Are there breaking change implications?
- Security, performance, or compatibility concerns?

### 4. Complexity Estimation
Rate as SIMPLE/MEDIUM/COMPLEX based on:
- Lines of code likely required
- Number of files to modify
- External dependencies needed
- Testing complexity

## Response Format

Provide your assessment in this exact format:

**VALIDATION**: [VALID | NEEDS_CLARIFICATION | INVALID]

**COMPLEXITY**: [SIMPLE | MEDIUM | COMPLEX]

**ANALYSIS**:
[Your detailed technical analysis of the issue]

**IMPLEMENTATION_APPROACH**:
[Specific steps for implementation if valid]

**QUESTIONS**:
[Any clarifying questions if validation is NEEDS_CLARIFICATION]

**RISKS**:
[Potential implementation risks and mitigation strategies]

**ESTIMATED_EFFORT**: [Number of files to change, key components to modify]

Be thorough but concise. Focus on actionable technical details that would help an AI agent implement this successfully.
"""
        return prompt

    def _parse_validation_response(
        self, response_text: str, context: ValidationContext
    ) -> ValidationResult:
        """Parse Claude's validation response."""
        # Look for structured decision markers
        response_lower = response_text.lower()

        # Check for explicit validation result (handle markdown formatting)
        if (
            "validation: valid" in response_lower
            or "validation**: valid" in response_lower
            or "result: valid" in response_lower
        ):
            return ValidationResult.VALID
        elif (
            "validation: needs_clarification" in response_lower
            or "validation**: needs_clarification" in response_lower
            or "needs clarification" in response_lower
            or "unclear" in response_lower
            or "ambiguous" in response_lower
        ):
            return ValidationResult.NEEDS_CLARIFICATION
        elif (
            "validation: invalid" in response_lower
            or "validation**: invalid" in response_lower
            or "result: invalid" in response_lower
            or "cannot implement" in response_lower
            or "insufficient information" in response_lower
        ):
            return ValidationResult.INVALID

        # Fallback: analyze content sentiment
        positive_indicators = ["implementable", "clear", "well-defined", "straightforward"]
        negative_indicators = ["unclear", "ambiguous", "missing", "incomplete", "complex"]

        positive_count = sum(1 for indicator in positive_indicators if indicator in response_lower)
        negative_count = sum(1 for indicator in negative_indicators if indicator in response_lower)

        if positive_count > negative_count and positive_count > 0:
            return ValidationResult.VALID
        elif negative_count > positive_count:
            return ValidationResult.NEEDS_CLARIFICATION
        else:
            return ValidationResult.NEEDS_CLARIFICATION  # Default to caution

    def _implement_changes_impl(self, context: ImplementationContext) -> ImplementationResponse:
        """Implementation-specific code changes."""
        try:
            # Build implementation prompt
            prompt = self._build_implementation_prompt(context)

            # Run Claude implementation with sophisticated permission system
            if self.use_claude_cli:
                from rich.console import Console

                console = Console()

                console.print("[cyan]📝 Preparing implementation prompt...[/cyan]")

                # Define allowed tools from original pipeline (comprehensive implementation permissions)
                allowed_tools = [
                    # File operations in worktree
                    "Read",
                    "Edit",
                    "Write",
                    "Glob",
                    "Grep",
                    # Git operations on assigned branch only
                    "Bash(git add:*)",
                    "Bash(git commit:*)",
                    "Bash(git status:*)",
                    "Bash(git diff:*)",
                    "Bash(git log:*)",
                    "Bash(git rebase:*)",
                    "Bash(git reset:*)",
                    "Bash(git show:*)",
                    # Tests and linters
                    "Bash(pytest:*)",
                    "Bash(python -m pytest:*)",
                    "Bash(python3 -m pytest:*)",
                    "Bash(black:*)",
                    "Bash(isort:*)",
                    "Bash(flake8:*)",
                    "Bash(coverage:*)",
                    # Pre-commit hooks
                    "Bash(pre-commit:*)",
                    "Bash(source venv/bin/activate*)",
                    # Python operations
                    "Bash(python:*)",
                    "Bash(python3:*)",
                    "Bash(pip:*)",
                    # GitHub operations
                    "Bash(gh pr create:*)",
                    "Bash(gh issue comment:*)",
                    "Bash(gh issue create:*)",
                    "Bash(gh issue view:*)",
                    # Utility tools
                    "Task",
                    "TodoWrite",
                ]

                console.print("[cyan]🤖 Sending request to Claude with permissions...[/cyan]")
                response_text = self._run_claude_command(
                    prompt,
                    timeout=600,
                    allowed_tools=allowed_tools,
                    working_directory=context.working_directory,
                )

                console.print("[green]✅ Received implementation from Claude[/green]")
            else:
                response_text = "Implementation not yet implemented for Claude API"

            # Parse response for results
            result = self._parse_implementation_response(response_text)

            confidence = self._calculate_confidence(response_text, "implementation")

            return ImplementationResponse(
                success=True,
                message=response_text,
                data={"raw_response": response_text},
                result=result,
                confidence=confidence,
            )

        except Exception as e:
            return ImplementationResponse(
                success=False,
                message=f"Implementation failed: {str(e)}",
                data={"error": str(e)},
                result=ImplementationResult.FAILED,
                confidence=0.0,
            )

    def _build_implementation_prompt(self, context: ImplementationContext) -> str:
        """Build sophisticated implementation prompt based on original pipeline."""
        issue = context.issue
        constraints = context.constraints
        iteration_count = constraints.get("current_iteration", 1)
        max_iterations = constraints.get("max_iterations", 3)

        # Get branch name from working directory (assumes worktree pattern)
        import os

        branch_name = f"issue-{issue.number}"

        # Build sophisticated prompt based on the original pipeline's approach
        prompt = f"""You are implementing a fix for GitHub issue #{issue.number}: {issue.title}

⚠️  CRITICAL RULE - COMMIT MESSAGE FORMAT ⚠️
ABSOLUTELY FORBIDDEN in commit messages:
- ANY mention of "Claude", "AI", "artificial intelligence", "LLM", "language model"
- ANY Co-Authored-By lines with "Claude" or AI-related names
- ANY "Generated with" or "Created by" lines mentioning tools/AI
- ANY emoji attributions like "🤖 Generated with..."

Your commits MUST look like they were written by a human developer.
Use simple, professional commit messages like: "Fix authentication retry logic (#{issue.number})"

VIOLATION OF THIS RULE = IMMEDIATE FAILURE

Issue details:
{issue.body}

OPERATIONAL CONSTRAINTS (CRITICAL - MUST FOLLOW):

Allowed Operations:
✓ Read ANY file in the worktree: {context.working_directory}
✓ Edit/Write/Delete files in the worktree: {context.working_directory}
✓ Create new files and directories in the worktree
✓ Run tests, linters, pre-commit hooks (pytest, black, isort, flake8, etc.)
✓ Install dependencies (pip install in venv)
✓ Git operations on branch: {branch_name}
  - git add, commit, rebase, squash, amend, reset
  - ONLY on your assigned branch {branch_name}
✓ GitHub operations (via gh CLI):
  - Create pull requests for this issue
  - Add comments to issue #{issue.number}
  - Create new issues if bugs/tasks discovered during work
  - Read repository information

Forbidden Operations:
✗ NO git operations on other branches (main, master, etc.)
✗ NO creating or deleting git tags
✗ NO pushing to remote (orchestrator handles this)
✗ NO merging pull requests
✗ NO closing or deleting issues
✗ NO modifying files outside worktree: {context.working_directory}
✗ NO operations on other worktrees or repositories

Your tasks:
1. Explore the codebase to locate the files that need changes
2. Implement the fix as described in the issue
3. Write comprehensive tests (unit and/or integration as needed)
4. Ensure all pre-commit hooks pass (black, isort, flake8, pytest)
5. Commit your changes (one clean commit, squash if needed)

Working directory: {context.working_directory}
Current branch: {branch_name}

Git Workflow (CRITICAL - MUST FOLLOW):
- ⚠️  FORBIDDEN: NO "Claude", "AI", "Generated with", or "Co-Authored-By: Claude" in commits
- ⚠️  Commit messages MUST appear human-written (see CRITICAL RULE above)
- MUST use venv for commits: source venv/bin/activate && git commit ...
- NEVER EVER use --no-verify flag (FORBIDDEN - hooks must always run)
- If pre-commit hooks fail: fix the issues, don't skip hooks
- Create atomic commits (one logical change per commit)
- If multiple commits needed: squash them before finishing
  Command: git rebase -i HEAD~N  (mark all but first as 'squash')
- If pre-commit hooks modify files: amend the commit
  Commands: source venv/bin/activate && git add -u && git commit --amend --no-edit
- Commit message format: "Fix description (#{issue.number})" - NOTHING ELSE

FORBIDDEN Git Operations (DO NOT DO THESE):
- git commit --no-verify  (NEVER skip hooks)
- git commit -n           (NEVER skip hooks)
- Any flag that bypasses pre-commit hooks

Common Git Operations:
1. Squash multiple commits:
   git rebase -i HEAD~N
   Change 'pick' to 'squash' or 's' for all but the first commit

2. Amend after pre-commit changes:
   git add -u
   git commit --amend --no-edit

3. Reset and recommit cleanly:
   git reset --soft HEAD~N
   git commit -m "Clean commit message"

Project Requirements:
- Maintain high test coverage
- Follow existing code patterns
- Comprehensive tests required
- DO NOT mention Claude/AI anywhere

Expected Output (JSON):
{{
  "success": true/false,
  "files_modified": ["list", "of", "files"],
  "summary": "brief summary of changes",
  "commit_sha": "sha if committed",
  "commit_message": "the final commit message (MUST NOT contain Claude/AI/Generated)",
  "commits_squashed": true/false,
  "errors": ["any", "errors"]
}}

FINAL REMINDER: Check your commit message does NOT contain:
❌ "Claude" ❌ "AI" ❌ "Generated with" ❌ "Co-Authored-By: Claude"
✅ Use simple human-style commit like: "Fix authentication retry (#{issue.number})"
"""
        return prompt

    def _format_previous_attempts(self, previous_iterations: List[Any]) -> str:
        """Format previous implementation attempts for context."""
        if not previous_iterations:
            return "No previous attempts."

        formatted = []
        for i, attempt in enumerate(previous_iterations[:3], 1):  # Show last 3 attempts
            attempt_info = getattr(attempt, "summary", str(attempt)[:100])
            formatted.append(f"Attempt {i}: {attempt_info}")

        return "\n".join(formatted)

    def _parse_implementation_response(self, response_text: str) -> ImplementationResult:
        """Parse implementation response."""
        response_lower = response_text.lower()

        # Check for explicit status indicators
        if (
            "implementation: success" in response_lower
            or "status: success" in response_lower
            or "implementation complete" in response_lower
        ):
            return ImplementationResult.SUCCESS
        elif (
            "implementation: failed" in response_lower
            or "status: failed" in response_lower
            or "implementation failed" in response_lower
        ):
            return ImplementationResult.FAILED
        elif (
            "implementation: partial" in response_lower
            or "status: partial" in response_lower
            or "partially implemented" in response_lower
        ):
            return ImplementationResult.PARTIAL

        # Analyze implementation indicators
        success_indicators = [
            "created",
            "added",
            "implemented",
            "modified",
            "updated",
            "fixed",
            "completed",
            "successful",
            "working",
            "tests pass",
        ]
        failure_indicators = [
            "error",
            "failed",
            "exception",
            "cannot",
            "unable",
            "missing",
            "broken",
            "syntax error",
            "import error",
            "tests fail",
        ]
        partial_indicators = [
            "partial",
            "incomplete",
            "partially",
            "some issues",
            "work in progress",
            "needs more",
            "additional work",
        ]

        success_count = sum(1 for indicator in success_indicators if indicator in response_lower)
        failure_count = sum(1 for indicator in failure_indicators if indicator in response_lower)
        partial_count = sum(1 for indicator in partial_indicators if indicator in response_lower)

        # Determine result based on indicators
        if failure_count > 0:
            return ImplementationResult.FAILED
        elif partial_count > 0 or (success_count > 0 and success_count < 3):
            return ImplementationResult.PARTIAL
        elif success_count >= 3:
            return ImplementationResult.SUCCESS
        else:
            # Default based on response length and structure
            if len(response_text) < 100:
                return ImplementationResult.FAILED
            else:
                return ImplementationResult.PARTIAL

    def _review_code_impl(self, context: ReviewContext) -> ReviewResponse:
        """Implementation-specific code review."""
        try:
            # Build review prompt
            prompt = self._build_review_prompt(context)

            # Run Claude review
            if self.use_claude_cli:
                context_files = self._get_context_files(context)
                response_text = self._run_claude_command(prompt, context_files, timeout=300)
            else:
                response_text = "Review not yet implemented for Claude API"

            # Parse response
            decision, severity = self._parse_review_response(response_text, context)

            confidence = self._calculate_confidence(response_text, "review")

            return ReviewResponse(
                success=True,
                message=response_text,
                data={"raw_response": response_text},
                decision=decision,
                severity=severity,
                confidence=confidence,
            )

        except Exception as e:
            return ReviewResponse(
                success=False,
                message=f"Review failed: {str(e)}",
                data={"error": str(e)},
                decision=ReviewDecision.COMMENT,
                severity=IssueSeverity.INFO,
                confidence=0.0,
            )

    def _build_review_prompt(self, context: ReviewContext) -> str:
        """Build code review prompt."""
        pr = context.pull_request
        maturity = context.maturity_level

        prompt = f"""You are a senior code reviewer performing automated code review.

# CODE REVIEW REQUEST

## Pull Request Details
**PR #**: {pr.number}
**Title**: {pr.title}
**Author**: {pr.author}
**Source Branch**: {pr.source_branch}
**Target Branch**: {pr.target_branch}

## Description
{pr.body}

## Changed Files ({len(context.changed_files)} files)
{chr(10).join([f"- {f.get('filename', 'unknown')} ({f.get('status', 'modified')})" for f in context.changed_files[:15]])}
{f"... and {len(context.changed_files) - 15} more files" if len(context.changed_files) > 15 else ""}

## Project Context
- **Maturity Level**: {maturity}
- **Review Focus**: {', '.join(context.review_focus)}
- **Quality Standards**: {"Strict" if maturity in ["stable", "mature"] else "Standard"}

## Review Criteria

### Code Quality & Correctness
- Is the implementation correct and complete?
- Are edge cases properly handled?
- Is error handling appropriate?
- Does the code follow project conventions?

### Security Assessment
- Are there security vulnerabilities?
- Is input validation adequate?
- Are credentials or sensitive data properly handled?
- Are dependencies secure?

### Performance & Maintainability
- Are there performance implications?
- Is the code readable and maintainable?
- Is the design appropriate for the change scope?
- Are there code smells or anti-patterns?

### Testing & Documentation
{"- Are all changes covered by tests?" if maturity in ["stable", "mature"] else "- Are critical paths tested?"}
{"- Is documentation updated for public APIs?" if maturity in ["stable", "mature"] else "- Is basic documentation present?"}
- Are test cases comprehensive?
- Are comments clear and necessary?

## Maturity-Specific Standards

{self._get_maturity_standards(maturity)}

## Response Format

Provide your review in this exact format:

**DECISION**: [APPROVE | REQUEST_CHANGES | COMMENT]

**SEVERITY**: [CRITICAL | HIGH | MEDIUM | LOW | INFO]

**SUMMARY**:
[Brief overall assessment of the pull request]

**DETAILED_FEEDBACK**:
[Comprehensive technical review with specific file references]

**SECURITY_CONCERNS**:
[Any security issues identified or "None identified"]

**PERFORMANCE_IMPACT**:
[Performance implications or "No significant impact"]

**TESTING_ASSESSMENT**:
[Quality and completeness of tests]

**SPECIFIC_ISSUES**:
{self._get_issue_template()}

**RECOMMENDATIONS**:
[Actionable suggestions for improvement]

Be thorough but constructive. Focus on maintainability, security, and correctness.
"""
        return prompt

    def _get_maturity_standards(self, maturity: str) -> str:
        """Get maturity-specific review standards."""
        standards = {
            "prototype": "- Focus on functionality over perfection\n- Allow experimental patterns\n- Basic error handling sufficient",
            "early_stage": "- Require good error handling\n- Encourage best practices\n- Moderate test coverage expected",
            "stable": "- Strict adherence to conventions\n- Comprehensive testing required\n- Breaking changes need justification",
            "mature": "- Zero tolerance for regressions\n- Comprehensive documentation required\n- Performance impact analysis mandatory",
        }
        return standards.get(maturity, standards["early_stage"])

    def _get_issue_template(self) -> str:
        """Get template for listing specific issues."""
        return """File: [filename]
Line: [line number]
Issue: [description]
Severity: [CRITICAL/HIGH/MEDIUM/LOW]
Suggestion: [how to fix]

[Repeat for each issue found, or write "No significant issues found"]"""

    def _parse_review_response(
        self, response_text: str, context: ReviewContext
    ) -> tuple[ReviewDecision, IssueSeverity]:
        """Parse review response."""
        response_lower = response_text.lower()

        # Parse decision
        decision = ReviewDecision.COMMENT  # default
        if (
            "decision: approve" in response_lower
            or "approve" in response_lower
            and "lgtm" in response_lower
        ):
            decision = ReviewDecision.APPROVE
        elif (
            "decision: request_changes" in response_lower
            or "request changes" in response_lower
            or "needs changes" in response_lower
            or "must fix" in response_lower
        ):
            decision = ReviewDecision.REQUEST_CHANGES
        elif (
            "decision: comment" in response_lower
            or "minor issues" in response_lower
            or "suggestions" in response_lower
        ):
            decision = ReviewDecision.COMMENT

        # Parse severity - look for explicit markers first
        severity = IssueSeverity.INFO  # default
        if (
            "severity: critical" in response_lower
            or "critical" in response_lower
            and ("bug" in response_lower or "security" in response_lower)
        ):
            severity = IssueSeverity.CRITICAL
        elif (
            "severity: high" in response_lower
            or ("high" in response_lower and "priority" in response_lower)
            or "breaking change" in response_lower
        ):
            severity = IssueSeverity.HIGH
        elif (
            "severity: medium" in response_lower
            or ("medium" in response_lower and "priority" in response_lower)
            or "performance" in response_lower
            or "maintainability" in response_lower
        ):
            severity = IssueSeverity.MEDIUM
        elif (
            "severity: low" in response_lower
            or ("low" in response_lower and "priority" in response_lower)
            or "style" in response_lower
            or "formatting" in response_lower
        ):
            severity = IssueSeverity.LOW

        # Auto-determine severity based on decision if not explicit
        if decision == ReviewDecision.REQUEST_CHANGES and severity == IssueSeverity.INFO:
            # If requesting changes but no explicit severity, infer from keywords
            critical_keywords = ["security", "vulnerability", "crash", "data loss"]
            high_keywords = ["bug", "error", "exception", "breaking"]
            medium_keywords = ["performance", "memory", "logic"]

            if any(keyword in response_lower for keyword in critical_keywords):
                severity = IssueSeverity.CRITICAL
            elif any(keyword in response_lower for keyword in high_keywords):
                severity = IssueSeverity.HIGH
            elif any(keyword in response_lower for keyword in medium_keywords):
                severity = IssueSeverity.MEDIUM
            else:
                severity = IssueSeverity.LOW

        return decision, severity

    def _calculate_confidence(self, response_text: str, operation_type: str) -> float:
        """Calculate confidence score for Claude's response."""
        confidence = 0.5  # Base confidence

        response_lower = response_text.lower()

        # Check response structure and completeness
        if len(response_text) > 200:
            confidence += 0.1
        if len(response_text) > 500:
            confidence += 0.1

        # Look for structured response indicators
        if operation_type == "validation":
            structure_indicators = [
                "validation:",
                "analysis:",
                "complexity:",
                "implementation_approach:",
            ]
        elif operation_type == "implementation":
            structure_indicators = [
                "implementation:",
                "files_changed:",
                "tests_added:",
                "validation:",
            ]
        elif operation_type == "review":
            structure_indicators = ["decision:", "severity:", "summary:", "detailed_feedback:"]
        else:
            structure_indicators = []

        structure_score = sum(
            1 for indicator in structure_indicators if indicator in response_lower
        )
        confidence += min(structure_score * 0.05, 0.2)

        # Check for certainty language
        certain_phrases = ["clear", "definite", "obvious", "straightforward", "certain"]
        uncertain_phrases = ["might", "maybe", "unclear", "unsure", "possibly", "probably"]

        certain_count = sum(1 for phrase in certain_phrases if phrase in response_lower)
        uncertain_count = sum(1 for phrase in uncertain_phrases if phrase in response_lower)

        confidence += min(certain_count * 0.02, 0.1)
        confidence -= min(uncertain_count * 0.02, 0.1)

        # Check for technical detail level
        technical_terms = [
            "function",
            "method",
            "class",
            "import",
            "test",
            "file",
            "error",
            "exception",
        ]
        technical_count = sum(1 for term in technical_terms if term in response_lower)
        confidence += min(technical_count * 0.01, 0.1)

        # Ensure confidence is within bounds
        return max(0.1, min(confidence, 0.95))

    def _get_context_files(self, context) -> List[str]:
        """Get relevant context files for Claude command."""
        context_files = []

        # Add configuration files
        config_files = ["devflow.yaml", "pyproject.toml", "setup.py", "requirements.txt"]
        for config_file in config_files:
            try:
                from pathlib import Path

                if Path(config_file).exists():
                    context_files.append(config_file)
            except Exception:
                pass

        # Add relevant source files based on context
        if hasattr(context, "issue") and context.issue:
            # Try to infer relevant files from issue description
            issue_text = f"{context.issue.title} {context.issue.body}".lower()

            # Look for file mentions
            import re

            file_patterns = [
                r"(\w+\.py)",
                r"(\w+/\w+\.py)",
                r"(src/\w+/\w+\.py)",
                r"(tests/\w+\.py)",
            ]

            for pattern in file_patterns:
                matches = re.findall(pattern, issue_text)
                context_files.extend(matches[:3])  # Limit to first 3 matches

        # Limit total context files to avoid overwhelming Claude
        return context_files[:10]

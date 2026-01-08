"""GitHub Platform Adapter - Real implementation.

This module provides the actual GitHub API integration, extracted and enhanced
from the original embedded pipeline system.
"""

import json
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from devflow.adapters.base import (
    Issue,
    IssueState,
    MergeStrategy,
    PlatformAdapter,
    PullRequest,
    PullRequestState,
    Repository,
    Review,
    ReviewDecision,
    WorkflowRun
)
from devflow.exceptions import PlatformError


class GitHubPlatformAdapter(PlatformAdapter):
    """GitHub platform adapter using gh CLI.

    Provides real GitHub API integration via the gh CLI tool,
    preserving the sophisticated patterns from the original embedded system.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize GitHub adapter.

        Args:
            config: Configuration containing repository info

        Raises:
            PlatformError: If configuration is invalid
        """
        # Set attributes first before calling super() which validates config
        self.owner = config.get("repo_owner")
        self.repo = config.get("repo_name")

        if self.owner and self.repo:
            self.repo_full = f"{self.owner}/{self.repo}"
        else:
            self.repo_full = None

        super().__init__(config)

    @property
    def name(self) -> str:
        """Platform adapter name."""
        return "github"

    @property
    def display_name(self) -> str:
        """Human-readable platform name."""
        return "GitHub"

    def _validate_config(self) -> None:
        """Validate GitHub-specific configuration."""
        if not self.repo_full:
            raise PlatformError(
                "GitHub adapter requires 'repo_owner' and 'repo_name' in configuration",
                platform=self.name
            )

    def _run_gh_command(
        self,
        args: List[str],
        check: bool = True,
        timeout: int = 30
    ) -> subprocess.CompletedProcess:
        """Run a gh CLI command.

        Args:
            args: Command arguments (without 'gh' prefix)
            check: Whether to raise on non-zero exit code
            timeout: Command timeout in seconds

        Returns:
            Completed process result

        Raises:
            PlatformError: If command fails and check=True
        """
        try:
            result = subprocess.run(
                ["gh"] + args,
                capture_output=True,
                text=True,
                check=check,
                timeout=timeout
            )
            return result

        except subprocess.CalledProcessError as e:
            error_msg = f"GitHub CLI command failed: {' '.join(args)}"
            if e.stderr:
                error_msg += f"\nError: {e.stderr}"
            raise PlatformError(
                error_msg,
                platform=self.name,
                status_code=e.returncode
            ) from e

        except subprocess.TimeoutExpired as e:
            raise PlatformError(
                f"GitHub CLI command timed out after {timeout}s: {' '.join(args)}",
                platform=self.name
            ) from e

        except FileNotFoundError as e:
            raise PlatformError(
                "GitHub CLI (gh) not found. Install from: https://cli.github.com/",
                platform=self.name
            ) from e

    def validate_connection(self) -> bool:
        """Test connection to GitHub.

        Returns:
            True if connection is successful

        Raises:
            PlatformError: If connection validation fails
        """
        try:
            # Test authentication
            result = self._run_gh_command(["auth", "status"], check=False)
            if result.returncode != 0:
                raise PlatformError(
                    "GitHub CLI not authenticated. Run: gh auth login",
                    platform=self.name
                )

            # Test repository access if configured
            if self.repo_full:
                result = self._run_gh_command(
                    ["repo", "view", self.repo_full, "--json", "name"],
                    check=False
                )
                if result.returncode != 0:
                    raise PlatformError(
                        f"Cannot access repository: {self.repo_full}",
                        platform=self.name
                    )

            return True

        except Exception as e:
            if isinstance(e, PlatformError):
                raise
            raise PlatformError(f"GitHub connection validation failed: {str(e)}") from e

    # Repository operations
    def get_repository(self, owner: str, repo: str) -> Repository:
        """Get repository information."""
        try:
            result = self._run_gh_command([
                "repo", "view", f"{owner}/{repo}",
                "--json", "id,name,nameWithOwner,description,defaultBranchRef,isPrivate,url,sshUrl"
            ])

            data = json.loads(result.stdout)

            return Repository(
                id=str(data["id"]),
                name=data["name"],
                full_name=data["nameWithOwner"],
                owner=owner,
                description=data.get("description", ""),
                default_branch=data["defaultBranchRef"]["name"],
                private=data["isPrivate"],
                url=data["url"],
                clone_url=data["url"] + ".git",  # Construct clone URL from repository URL
                ssh_url=data["sshUrl"],
                platform_data=data
            )

        except Exception as e:
            raise PlatformError(
                f"Failed to get repository {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    # Issue operations
    def get_issue(self, owner: str, repo: str, issue_number: int) -> Issue:
        """Get issue details."""
        try:
            result = self._run_gh_command([
                "issue", "view", str(issue_number),
                "--repo", f"{owner}/{repo}",
                "--json", "id,number,title,body,state,labels,assignees,author,createdAt,updatedAt,url"
            ])

            data = json.loads(result.stdout)

            return Issue(
                id=str(data["id"]),
                number=data["number"],
                title=data["title"],
                body=data.get("body", ""),
                state=IssueState.OPEN if data["state"] == "OPEN" else IssueState.CLOSED,
                labels=[label["name"] for label in data.get("labels", [])],
                assignees=[assignee["login"] for assignee in data.get("assignees", [])],
                author=data["author"]["login"],
                created_at=self._parse_datetime(data["createdAt"]),
                updated_at=self._parse_datetime(data["updatedAt"]),
                url=data["url"],
                platform_data=data
            )

        except Exception as e:
            raise PlatformError(
                f"Failed to get issue #{issue_number} from {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    def list_issues(
        self,
        owner: str,
        repo: str,
        state: IssueState = IssueState.OPEN,
        labels: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Issue]:
        """List repository issues."""
        try:
            args = [
                "issue", "list",
                "--repo", f"{owner}/{repo}",
                "--state", state.value,
                "--limit", str(limit),
                "--json", "id,number,title,body,state,labels,assignees,author,createdAt,updatedAt,url"
            ]

            if labels:
                args.extend(["--label", ",".join(labels)])

            result = self._run_gh_command(args)
            issues_data = json.loads(result.stdout)

            issues = []
            for data in issues_data:
                issue = Issue(
                    id=str(data["id"]),
                    number=data["number"],
                    title=data["title"],
                    body=data.get("body", ""),
                    state=IssueState.OPEN if data["state"] == "OPEN" else IssueState.CLOSED,
                    labels=[label["name"] for label in data.get("labels", [])],
                    assignees=[assignee["login"] for assignee in data.get("assignees", [])],
                    author=data["author"]["login"],
                    created_at=self._parse_datetime(data["createdAt"]),
                    updated_at=self._parse_datetime(data["updatedAt"]),
                    url=data["url"],
                    platform_data=data
                )
                issues.append(issue)

            return issues

        except Exception as e:
            raise PlatformError(
                f"Failed to list issues from {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None
    ) -> Issue:
        """Create a new issue."""
        try:
            args = [
                "issue", "create",
                "--repo", f"{owner}/{repo}",
                "--title", title,
                "--body", body
            ]

            if labels:
                args.extend(["--label", ",".join(labels)])

            if assignees:
                args.extend(["--assignee", ",".join(assignees)])

            result = self._run_gh_command(args)

            # Parse issue number from output (gh returns URL)
            issue_url = result.stdout.strip()
            issue_number = int(issue_url.split("/")[-1])

            # Fetch the created issue to return full data
            return self.get_issue(owner, repo, issue_number)

        except Exception as e:
            raise PlatformError(
                f"Failed to create issue in {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    def update_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[IssueState] = None,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None
    ) -> Issue:
        """Update an existing issue."""
        try:
            args = [
                "issue", "edit", str(issue_number),
                "--repo", f"{owner}/{repo}"
            ]

            if title:
                args.extend(["--title", title])
            if body:
                args.extend(["--body", body])
            if labels:
                args.extend(["--add-label", ",".join(labels)])
            if assignees:
                args.extend(["--add-assignee", ",".join(assignees)])

            self._run_gh_command(args)

            # Handle state change separately if needed
            if state == IssueState.CLOSED:
                self._run_gh_command([
                    "issue", "close", str(issue_number),
                    "--repo", f"{owner}/{repo}"
                ])
            elif state == IssueState.OPEN:
                self._run_gh_command([
                    "issue", "reopen", str(issue_number),
                    "--repo", f"{owner}/{repo}"
                ])

            # Return updated issue
            return self.get_issue(owner, repo, issue_number)

        except Exception as e:
            raise PlatformError(
                f"Failed to update issue #{issue_number} in {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    def add_issue_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str
    ) -> Dict[str, Any]:
        """Add a comment to an issue."""
        try:
            result = self._run_gh_command([
                "issue", "comment", str(issue_number),
                "--repo", f"{owner}/{repo}",
                "--body", body
            ])

            return {
                "url": result.stdout.strip(),
                "body": body
            }

        except Exception as e:
            raise PlatformError(
                f"Failed to add comment to issue #{issue_number} in {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    # Pull request operations
    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> PullRequest:
        """Get pull request details."""
        try:
            result = self._run_gh_command([
                "pr", "view", str(pr_number),
                "--repo", f"{owner}/{repo}",
                "--json", "id,number,title,body,state,headRefName,baseRefName,author,assignees,labels,createdAt,updatedAt,mergeable,url"
            ])

            data = json.loads(result.stdout)

            # Map GitHub states to our enum
            state_mapping = {
                "OPEN": PullRequestState.OPEN,
                "CLOSED": PullRequestState.CLOSED,
                "MERGED": PullRequestState.MERGED
            }

            return PullRequest(
                id=str(data["id"]),
                number=data["number"],
                title=data["title"],
                body=data.get("body", ""),
                state=state_mapping.get(data["state"], PullRequestState.CLOSED),
                source_branch=data["headRefName"],
                target_branch=data["baseRefName"],
                author=data["author"]["login"],
                reviewers=[assignee["login"] for assignee in data.get("assignees", [])],
                labels=[label["name"] for label in data.get("labels", [])],
                created_at=self._parse_datetime(data["createdAt"]),
                updated_at=self._parse_datetime(data["updatedAt"]),
                mergeable=data.get("mergeable", True),
                url=data["url"],
                platform_data=data
            )

        except Exception as e:
            raise PlatformError(
                f"Failed to get PR #{pr_number} from {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: PullRequestState = PullRequestState.OPEN,
        limit: int = 100
    ) -> List[PullRequest]:
        """List repository pull requests."""
        try:
            # Map our state enum to GitHub CLI state
            gh_state = "open" if state == PullRequestState.OPEN else "closed"

            result = self._run_gh_command([
                "pr", "list",
                "--repo", f"{owner}/{repo}",
                "--state", gh_state,
                "--limit", str(limit),
                "--json", "id,number,title,body,state,headRefName,baseRefName,author,assignees,labels,createdAt,updatedAt,mergeable,url"
            ])

            prs_data = json.loads(result.stdout)

            state_mapping = {
                "OPEN": PullRequestState.OPEN,
                "CLOSED": PullRequestState.CLOSED,
                "MERGED": PullRequestState.MERGED
            }

            pull_requests = []
            for data in prs_data:
                pr = PullRequest(
                    id=str(data["id"]),
                    number=data["number"],
                    title=data["title"],
                    body=data.get("body", ""),
                    state=state_mapping.get(data["state"], PullRequestState.CLOSED),
                    source_branch=data["headRefName"],
                    target_branch=data["baseRefName"],
                    author=data["author"]["login"],
                    reviewers=[assignee["login"] for assignee in data.get("assignees", [])],
                    labels=[label["name"] for label in data.get("labels", [])],
                    created_at=self._parse_datetime(data["createdAt"]),
                    updated_at=self._parse_datetime(data["updatedAt"]),
                    mergeable=data.get("mergeable", True),
                    url=data["url"],
                    platform_data=data
                )
                pull_requests.append(pr)

            return pull_requests

        except Exception as e:
            raise PlatformError(
                f"Failed to list PRs from {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        source_branch: str,
        target_branch: str,
        draft: bool = False
    ) -> PullRequest:
        """Create a new pull request."""
        try:
            args = [
                "pr", "create",
                "--repo", f"{owner}/{repo}",
                "--title", title,
                "--body", body,
                "--head", source_branch,
                "--base", target_branch
            ]

            if draft:
                args.append("--draft")

            result = self._run_gh_command(args)

            # Parse PR number from output (gh returns URL)
            pr_url = result.stdout.strip()
            pr_number = int(pr_url.split("/")[-1])

            # Fetch the created PR to return full data
            return self.get_pull_request(owner, repo, pr_number)

        except Exception as e:
            raise PlatformError(
                f"Failed to create PR in {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    def update_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[PullRequestState] = None
    ) -> PullRequest:
        """Update an existing pull request."""
        try:
            args = [
                "pr", "edit", str(pr_number),
                "--repo", f"{owner}/{repo}"
            ]

            if title:
                args.extend(["--title", title])
            if body:
                args.extend(["--body", body])

            self._run_gh_command(args)

            # Handle state changes separately
            if state == PullRequestState.CLOSED:
                self._run_gh_command([
                    "pr", "close", str(pr_number),
                    "--repo", f"{owner}/{repo}"
                ])

            # Return updated PR
            return self.get_pull_request(owner, repo, pr_number)

        except Exception as e:
            raise PlatformError(
                f"Failed to update PR #{pr_number} in {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    def merge_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        merge_strategy: MergeStrategy = MergeStrategy.SQUASH,
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Merge a pull request."""
        try:
            # Map our enum to GitHub CLI merge strategy
            strategy_mapping = {
                MergeStrategy.MERGE: "merge",
                MergeStrategy.SQUASH: "squash",
                MergeStrategy.REBASE: "rebase"
            }

            args = [
                "pr", "merge", str(pr_number),
                "--repo", f"{owner}/{repo}",
                f"--{strategy_mapping[merge_strategy]}"
            ]

            if commit_title and merge_strategy == MergeStrategy.SQUASH:
                args.extend(["--subject", commit_title])

            if commit_message and merge_strategy == MergeStrategy.SQUASH:
                args.extend(["--body", commit_message])

            result = self._run_gh_command(args)

            return {
                "merged": True,
                "strategy": merge_strategy.value,
                "output": result.stdout.strip()
            }

        except Exception as e:
            raise PlatformError(
                f"Failed to merge PR #{pr_number} in {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    # Review operations (simplified for now)
    def list_pull_request_reviews(
        self,
        owner: str,
        repo: str,
        pr_number: int
    ) -> List[Review]:
        """List pull request reviews."""
        # Note: This is a simplified implementation
        # The original system had sophisticated review handling
        return []

    def create_pull_request_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        decision: ReviewDecision,
        comments: Optional[List[Dict[str, Any]]] = None
    ) -> Review:
        """Create a pull request review."""
        try:
            # Map ReviewDecision to gh CLI format
            gh_decision_map = {
                ReviewDecision.APPROVED: "APPROVE",
                ReviewDecision.REQUEST_CHANGES: "REQUEST_CHANGES",
                ReviewDecision.COMMENT: "COMMENT"
            }

            # Use gh CLI to create review
            args = [
                "pr", "review", str(pr_number),
                "--repo", f"{owner}/{repo}",
                "--body", body,
            ]

            # Add decision if not just a comment
            if decision in gh_decision_map:
                if decision == ReviewDecision.APPROVED:
                    args.append("--approve")
                elif decision == ReviewDecision.REQUEST_CHANGES:
                    args.append("--request-changes")
                # For COMMENT, no additional flag needed

            result = self._run_gh_command(args)

            # Create Review object - gh CLI doesn't return review ID easily
            # so we'll create a basic review object
            from datetime import datetime
            review = Review(
                id=f"review-{pr_number}-{int(datetime.now().timestamp())}",
                user="devflow-ai",
                body=body,
                state=decision,
                submitted_at=datetime.now().isoformat(),
                platform_data={"gh_result": result.stdout}
            )

            return review

        except Exception as e:
            raise PlatformError(
                f"Failed to create review for PR #{pr_number} in {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    def get_pull_request_files(
        self,
        owner: str,
        repo: str,
        pr_number: int
    ) -> List[Dict[str, Any]]:
        """Get files changed in a pull request."""
        try:
            result = self._run_gh_command([
                "pr", "diff", str(pr_number),
                "--repo", f"{owner}/{repo}",
                "--name-only"
            ])

            files = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    files.append({
                        "filename": line,
                        "status": "modified",  # Simplified - would need more detailed info
                        "changes": 0,
                        "additions": 0,
                        "deletions": 0
                    })

            return files

        except Exception as e:
            raise PlatformError(
                f"Failed to get PR #{pr_number} files from {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    # CI/CD operations (simplified)
    def list_workflow_runs(
        self,
        owner: str,
        repo: str,
        branch: Optional[str] = None,
        limit: int = 100
    ) -> List[WorkflowRun]:
        """List workflow runs for repository."""
        # Note: This would need implementation for CI/CD integration
        return []

    def get_workflow_run(
        self,
        owner: str,
        repo: str,
        run_id: str
    ) -> WorkflowRun:
        """Get details of a specific workflow run."""
        # Note: This would need implementation for CI/CD integration
        raise NotImplementedError("Workflow run details not yet implemented")

    # Label operations
    def add_labels_to_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        labels: List[str]
    ) -> None:
        """Add labels to an issue."""
        try:
            if labels:
                self._run_gh_command([
                    "issue", "edit", str(issue_number),
                    "--repo", f"{owner}/{repo}",
                    "--add-label", ",".join(labels)
                ])

        except Exception as e:
            raise PlatformError(
                f"Failed to add labels to issue #{issue_number} in {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    def remove_labels_from_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        labels: List[str]
    ) -> None:
        """Remove labels from an issue."""
        try:
            if labels:
                self._run_gh_command([
                    "issue", "edit", str(issue_number),
                    "--repo", f"{owner}/{repo}",
                    "--remove-label", ",".join(labels)
                ])

        except Exception as e:
            raise PlatformError(
                f"Failed to remove labels from issue #{issue_number} in {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    # Utility methods
    def get_issue_url(self, owner: str, repo: str, issue_number: int) -> str:
        """Get URL for an issue."""
        return f"https://github.com/{owner}/{repo}/issues/{issue_number}"

    def get_pull_request_url(self, owner: str, repo: str, pr_number: int) -> str:
        """Get URL for a pull request."""
        return f"https://github.com/{owner}/{repo}/pull/{pr_number}"

    def _parse_datetime(self, date_str: str) -> datetime:
        """Parse GitHub datetime string."""
        try:
            # GitHub uses ISO format with Z suffix
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception:
            # Fallback to current time if parsing fails
            return datetime.now()

    # Repository management methods (new functionality)
    def create_repository(
        self,
        owner: str,
        repo: str,
        description: str = "",
        private: bool = False
    ) -> Repository:
        """Create a new GitHub repository."""
        try:
            args = [
                "repo", "create", f"{owner}/{repo}",
                "--description", description
            ]

            if private:
                args.append("--private")
            else:
                args.append("--public")

            self._run_gh_command(args)

            # Return the created repository
            return self.get_repository(owner, repo)

        except Exception as e:
            raise PlatformError(
                f"Failed to create repository {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e

    def setup_repository_labels(
        self,
        owner: str,
        repo: str,
        labels: Optional[List[Dict[str, str]]] = None
    ) -> None:
        """Set up standard labels for the repository."""
        try:
            if not labels:
                # Default DevFlow labels
                labels = [
                    {"name": "bug", "color": "d73a4a", "description": "Something isn't working"},
                    {"name": "enhancement", "color": "a2eeef", "description": "New feature or request"},
                    {"name": "documentation", "color": "0075ca", "description": "Improvements or additions to documentation"},
                    {"name": "good first issue", "color": "7057ff", "description": "Good for newcomers"},
                    {"name": "help wanted", "color": "008672", "description": "Extra attention is needed"},
                    {"name": "question", "color": "d876e3", "description": "Further information is requested"},
                    {"name": "automated-fix", "color": "1f883d", "description": "Automated fix by DevFlow"},
                    {"name": "needs-human-review", "color": "fbca04", "description": "Requires human attention"},
                    {"name": "platform", "color": "0052cc", "description": "Platform integration"},
                    {"name": "ai", "color": "5319e7", "description": "AI agent related"},
                    {"name": "testing", "color": "bfd4f2", "description": "Testing related"},
                    {"name": "quality", "color": "e4e669", "description": "Code quality improvements"}
                ]

            for label in labels:
                try:
                    self._run_gh_command([
                        "label", "create",
                        "--repo", f"{owner}/{repo}",
                        label["name"],
                        "--color", label["color"],
                        "--description", label.get("description", "")
                    ], check=False)  # Don't fail if label already exists
                except Exception:
                    # Ignore errors for existing labels
                    pass

        except Exception as e:
            raise PlatformError(
                f"Failed to setup labels for {owner}/{repo}: {str(e)}",
                platform=self.name
            ) from e
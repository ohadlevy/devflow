"""Basic Git Platform Adapter for testing and dry-run scenarios.

This adapter provides basic git functionality without requiring external
platform services like GitHub API. Perfect for testing and dry-run mode.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    WorkflowRun,
)
from devflow.exceptions import PlatformError


class BasicGitAdapter(PlatformAdapter):
    """Basic Git adapter for local operations without external services.

    This adapter provides git functionality using local operations only,
    making it suitable for testing and dry-run scenarios.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize Basic Git adapter.

        Args:
            config: Configuration containing repository info

        Raises:
            PlatformError: If configuration is invalid
        """
        # Set attributes first
        self.owner = config.get("repo_owner", "mock-owner")
        self.repo = config.get("repo_name", "mock-repo")
        self.repo_full = f"{self.owner}/{self.repo}"
        self.project_root = Path(config.get("project_root", Path.cwd()))

        super().__init__(config)

    @property
    def name(self) -> str:
        """Platform adapter name."""
        return "basic_git"

    @property
    def display_name(self) -> str:
        """Human-readable platform name."""
        return "Basic Git"

    def _validate_config(self) -> None:
        """Validate configuration."""
        if not self.project_root.exists():
            raise PlatformError(
                f"Project root does not exist: {self.project_root}", platform=self.name
            )

    def validate_connection(self) -> bool:
        """Test git availability.

        Returns:
            True if git is available and we're in a repo

        Raises:
            PlatformError: If git validation fails
        """
        try:
            # Check if git is available
            result = subprocess.run(
                ["git", "--version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                raise PlatformError("Git not available", platform=self.name)

            # Check if we're in a git repository
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )

            return result.returncode == 0

        except Exception as e:
            raise PlatformError(f"Git validation failed: {str(e)}") from e

    # Repository operations
    def get_repository(self, owner: str, repo: str) -> Repository:
        """Get repository information."""
        return Repository(
            id="mock-repo-1",
            name=repo,
            full_name=f"{owner}/{repo}",
            owner=owner,
            description="Mock repository for testing",
            default_branch="main",
            private=False,
            url=f"https://github.com/{owner}/{repo}",
            clone_url=f"https://github.com/{owner}/{repo}.git",
            ssh_url=f"git@github.com:{owner}/{repo}.git",
            platform_data={"mock": True},
        )

    # Issue operations (mock implementations)
    def get_issue(self, owner: str, repo: str, issue_number: int) -> Issue:
        """Get issue details (mock)."""
        return Issue(
            id=f"mock-issue-{issue_number}",
            number=issue_number,
            title=f"Mock Issue #{issue_number}",
            body=f"This is a mock issue for testing purposes. Issue number: {issue_number}",
            state=IssueState.OPEN,
            labels=["bug", "enhancement"],
            assignees=[],
            author="mock-user",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            url=f"https://github.com/{owner}/{repo}/issues/{issue_number}",
            platform_data={"mock": True, "issue_number": issue_number},
        )

    def list_issues(
        self,
        owner: str,
        repo: str,
        state: IssueState = IssueState.OPEN,
        labels: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Issue]:
        """List repository issues (mock)."""
        # Return a few mock issues
        return [self.get_issue(owner, repo, i) for i in range(1, min(4, limit + 1))]

    def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
    ) -> Issue:
        """Create a new issue (mock)."""
        issue_number = 999  # Mock issue number
        return Issue(
            id=f"mock-issue-{issue_number}",
            number=issue_number,
            title=title,
            body=body,
            state=IssueState.OPEN,
            labels=labels or [],
            assignees=assignees or [],
            author="devflow-bot",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            url=f"https://github.com/{owner}/{repo}/issues/{issue_number}",
            platform_data={"mock": True, "created": True},
        )

    def update_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[IssueState] = None,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
    ) -> Issue:
        """Update an existing issue (mock)."""
        # Return updated mock issue
        issue = self.get_issue(owner, repo, issue_number)
        if title:
            issue.title = title
        if body:
            issue.body = body
        if state:
            issue.state = state
        if labels:
            issue.labels = labels
        if assignees:
            issue.assignees = assignees
        issue.updated_at = datetime.now()
        return issue

    def add_issue_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> Dict[str, Any]:
        """Add a comment to an issue (mock)."""
        return {
            "url": f"https://github.com/{owner}/{repo}/issues/{issue_number}#comment-mock",
            "body": body,
            "mock": True,
        }

    # Pull request operations (mock implementations)
    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> PullRequest:
        """Get pull request details (mock)."""
        return PullRequest(
            id=f"mock-pr-{pr_number}",
            number=pr_number,
            title=f"Mock PR #{pr_number}",
            body="Mock pull request for testing",
            state=PullRequestState.OPEN,
            source_branch=f"feature/issue-{pr_number}",
            target_branch="main",
            author="devflow-bot",
            reviewers=[],
            labels=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            mergeable=True,
            url=f"https://github.com/{owner}/{repo}/pull/{pr_number}",
            platform_data={"mock": True},
        )

    def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: PullRequestState = PullRequestState.OPEN,
        limit: int = 100,
    ) -> List[PullRequest]:
        """List repository pull requests (mock)."""
        return [self.get_pull_request(owner, repo, i) for i in range(1, min(3, limit + 1))]

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        source_branch: str,
        target_branch: str,
        draft: bool = False,
    ) -> PullRequest:
        """Create a new pull request (mock)."""
        pr_number = 888  # Mock PR number
        return PullRequest(
            id=f"mock-pr-{pr_number}",
            number=pr_number,
            title=title,
            body=body,
            state=PullRequestState.OPEN,
            source_branch=source_branch,
            target_branch=target_branch,
            author="devflow-bot",
            reviewers=[],
            labels=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            mergeable=True,
            url=f"https://github.com/{owner}/{repo}/pull/{pr_number}",
            platform_data={"mock": True, "draft": draft},
        )

    def update_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[PullRequestState] = None,
    ) -> PullRequest:
        """Update an existing pull request (mock)."""
        pr = self.get_pull_request(owner, repo, pr_number)
        if title:
            pr.title = title
        if body:
            pr.body = body
        if state:
            pr.state = state
        pr.updated_at = datetime.now()
        return pr

    def merge_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        merge_strategy: MergeStrategy = MergeStrategy.SQUASH,
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Merge a pull request (mock)."""
        return {
            "merged": True,
            "strategy": merge_strategy.value,
            "commit_sha": "mock-commit-sha-123",
            "mock": True,
        }

    # Review operations (mock implementations)
    def list_pull_request_reviews(self, owner: str, repo: str, pr_number: int) -> List[Review]:
        """List pull request reviews (mock)."""
        return []  # No reviews in mock mode

    def create_pull_request_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        decision: ReviewDecision,
        comments: Optional[List[Dict[str, Any]]] = None,
    ) -> Review:
        """Create a pull request review (mock)."""
        raise NotImplementedError("Mock review creation not implemented")

    def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Get files changed in a pull request (mock)."""
        return [
            {
                "filename": "src/example.py",
                "status": "modified",
                "changes": 10,
                "additions": 8,
                "deletions": 2,
            },
            {
                "filename": "tests/test_example.py",
                "status": "added",
                "changes": 20,
                "additions": 20,
                "deletions": 0,
            },
        ]

    # CI/CD operations (mock)
    def list_workflow_runs(
        self, owner: str, repo: str, branch: Optional[str] = None, limit: int = 100
    ) -> List[WorkflowRun]:
        """List workflow runs for repository (mock)."""
        return []

    def get_workflow_run(self, owner: str, repo: str, run_id: str) -> WorkflowRun:
        """Get details of a specific workflow run (mock)."""
        raise NotImplementedError("Mock workflow run details not implemented")

    # Label operations (mock)
    def add_labels_to_issue(
        self, owner: str, repo: str, issue_number: int, labels: List[str]
    ) -> None:
        """Add labels to an issue (mock)."""
        pass  # Mock operation - no actual changes

    def remove_labels_from_issue(
        self, owner: str, repo: str, issue_number: int, labels: List[str]
    ) -> None:
        """Remove labels from an issue (mock)."""
        pass  # Mock operation - no actual changes

    # Utility methods
    def get_issue_url(self, owner: str, repo: str, issue_number: int) -> str:
        """Get URL for an issue."""
        return f"https://github.com/{owner}/{repo}/issues/{issue_number}"

    def get_pull_request_url(self, owner: str, repo: str, pr_number: int) -> str:
        """Get URL for a pull request."""
        return f"https://github.com/{owner}/{repo}/pull/{pr_number}"

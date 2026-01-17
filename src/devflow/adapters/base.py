"""Abstract base classes for platform adapters.

This module defines the interfaces that platform adapters must implement
to provide consistent functionality across different platforms (GitHub, GitLab, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Union

from devflow.exceptions import PlatformError, ValidationError


class IssueState(str, Enum):
    """Standard issue states across platforms."""

    OPEN = "open"
    CLOSED = "closed"
    ALL = "all"


class PullRequestState(str, Enum):
    """Standard pull request states across platforms."""

    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"
    DRAFT = "draft"
    ALL = "all"


class ReviewDecision(str, Enum):
    """Review decision types."""

    APPROVED = "approved"
    REQUEST_CHANGES = "request_changes"
    COMMENT = "comment"
    PENDING = "pending"


class MergeStrategy(str, Enum):
    """Pull request merge strategies."""

    MERGE = "merge"
    SQUASH = "squash"
    REBASE = "rebase"


@dataclass
class Issue:
    """Represents an issue across platforms."""

    id: str
    number: int
    title: str
    body: str
    state: IssueState
    labels: List[str]
    assignees: List[str]
    author: str
    created_at: datetime
    updated_at: datetime
    url: str
    platform_data: Dict[str, Any]  # Platform-specific data

    def __post_init__(self) -> None:
        """Validate issue data."""
        if not self.title:
            raise ValidationError("Issue title cannot be empty")
        if not self.id:
            raise ValidationError("Issue ID cannot be empty")


@dataclass
class PullRequest:
    """Represents a pull request across platforms."""

    id: str
    number: int
    title: str
    body: str
    state: PullRequestState
    source_branch: str
    target_branch: str
    author: str
    reviewers: List[str]
    labels: List[str]
    created_at: datetime
    updated_at: datetime
    mergeable: bool
    url: str
    platform_data: Dict[str, Any]  # Platform-specific data

    def __post_init__(self) -> None:
        """Validate pull request data."""
        if not self.title:
            raise ValidationError("Pull request title cannot be empty")
        if not self.source_branch:
            raise ValidationError("Source branch cannot be empty")
        if not self.target_branch:
            raise ValidationError("Target branch cannot be empty")


@dataclass
class Review:
    """Represents a code review across platforms."""

    id: str
    reviewer: str
    decision: ReviewDecision
    body: str
    submitted_at: datetime
    comments: List["ReviewComment"]
    platform_data: Dict[str, Any]  # Platform-specific data


@dataclass
class ReviewComment:
    """Represents a review comment."""

    id: str
    author: str
    body: str
    file_path: Optional[str]
    line_number: Optional[int]
    created_at: datetime
    platform_data: Dict[str, Any]  # Platform-specific data


@dataclass
class Repository:
    """Represents a repository across platforms."""

    id: str
    name: str
    full_name: str
    owner: str
    description: str
    default_branch: str
    private: bool
    url: str
    clone_url: str
    ssh_url: str
    platform_data: Dict[str, Any]  # Platform-specific data


@dataclass
class WorkflowRun:
    """Represents a CI/CD workflow run."""

    id: str
    name: str
    status: str  # pending, success, failure, error
    conclusion: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    url: str
    platform_data: Dict[str, Any]  # Platform-specific data


class PlatformAdapter(ABC):
    """Abstract base class for platform adapters.

    Platform adapters provide a unified interface for interacting with
    different code hosting platforms (GitHub, GitLab, Bitbucket, etc.).
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the platform adapter.

        Args:
            config: Platform-specific configuration

        Raises:
            PlatformError: If configuration is invalid
        """
        self.config = config
        self._validate_config()

    @property
    @abstractmethod
    def name(self) -> str:
        """Platform adapter name (e.g., 'github', 'gitlab')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable platform name (e.g., 'GitHub', 'GitLab')."""
        pass

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate platform-specific configuration.

        Raises:
            PlatformError: If configuration is invalid
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Test connection to the platform.

        Returns:
            True if connection is successful

        Raises:
            PlatformError: If connection validation fails
        """
        pass

    # Repository operations
    @abstractmethod
    def get_repository(self, owner: str, repo: str) -> Repository:
        """Get repository information.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Repository information

        Raises:
            PlatformError: If repository cannot be accessed
        """
        pass

    # Issue operations
    @abstractmethod
    def get_issue(self, owner: str, repo: str, issue_number: int) -> Issue:
        """Get issue details.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number

        Returns:
            Issue details

        Raises:
            PlatformError: If issue cannot be accessed
        """
        pass

    @abstractmethod
    def list_issues(
        self,
        owner: str,
        repo: str,
        state: IssueState = IssueState.OPEN,
        labels: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Issue]:
        """List repository issues.

        Args:
            owner: Repository owner
            repo: Repository name
            state: Issue state filter
            labels: Label filters
            limit: Maximum number of issues to return

        Returns:
            List of issues

        Raises:
            PlatformError: If issues cannot be listed
        """
        pass

    @abstractmethod
    def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
    ) -> Issue:
        """Create a new issue.

        Args:
            owner: Repository owner
            repo: Repository name
            title: Issue title
            body: Issue description
            labels: Issue labels
            assignees: Issue assignees

        Returns:
            Created issue

        Raises:
            PlatformError: If issue cannot be created
        """
        pass

    @abstractmethod
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
        """Update an existing issue.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            title: New issue title
            body: New issue body
            state: New issue state
            labels: New issue labels
            assignees: New issue assignees

        Returns:
            Updated issue

        Raises:
            PlatformError: If issue cannot be updated
        """
        pass

    @abstractmethod
    def add_issue_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> Dict[str, Any]:
        """Add a comment to an issue.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            body: Comment body

        Returns:
            Created comment data

        Raises:
            PlatformError: If comment cannot be added
        """
        pass

    # Pull request operations
    @abstractmethod
    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> PullRequest:
        """Get pull request details.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Pull request details

        Raises:
            PlatformError: If pull request cannot be accessed
        """
        pass

    @abstractmethod
    def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: PullRequestState = PullRequestState.OPEN,
        limit: int = 100,
    ) -> List[PullRequest]:
        """List repository pull requests.

        Args:
            owner: Repository owner
            repo: Repository name
            state: Pull request state filter
            limit: Maximum number of pull requests to return

        Returns:
            List of pull requests

        Raises:
            PlatformError: If pull requests cannot be listed
        """
        pass

    @abstractmethod
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
        """Create a new pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            title: Pull request title
            body: Pull request description
            source_branch: Source branch name
            target_branch: Target branch name
            draft: Create as draft pull request

        Returns:
            Created pull request

        Raises:
            PlatformError: If pull request cannot be created
        """
        pass

    @abstractmethod
    def update_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[PullRequestState] = None,
    ) -> PullRequest:
        """Update an existing pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            title: New pull request title
            body: New pull request body
            state: New pull request state

        Returns:
            Updated pull request

        Raises:
            PlatformError: If pull request cannot be updated
        """
        pass

    @abstractmethod
    def merge_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        merge_strategy: MergeStrategy = MergeStrategy.SQUASH,
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Merge a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            merge_strategy: Merge strategy to use
            commit_title: Custom commit title
            commit_message: Custom commit message

        Returns:
            Merge result data

        Raises:
            PlatformError: If pull request cannot be merged
        """
        pass

    # Review operations
    @abstractmethod
    def list_pull_request_reviews(self, owner: str, repo: str, pr_number: int) -> List[Review]:
        """List pull request reviews.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of reviews

        Raises:
            PlatformError: If reviews cannot be listed
        """
        pass

    @abstractmethod
    def create_pull_request_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        decision: ReviewDecision,
        comments: Optional[List[Dict[str, Any]]] = None,
    ) -> Review:
        """Create a pull request review.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            body: Review body
            decision: Review decision
            comments: Line-specific comments

        Returns:
            Created review

        Raises:
            PlatformError: If review cannot be created
        """
        pass

    @abstractmethod
    def get_pull_request_files(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Get files changed in a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of changed files with diff information

        Raises:
            PlatformError: If files cannot be retrieved
        """
        pass

    # CI/CD operations
    @abstractmethod
    def list_workflow_runs(
        self, owner: str, repo: str, branch: Optional[str] = None, limit: int = 100
    ) -> List[WorkflowRun]:
        """List workflow runs for repository.

        Args:
            owner: Repository owner
            repo: Repository name
            branch: Filter by branch
            limit: Maximum number of runs to return

        Returns:
            List of workflow runs

        Raises:
            PlatformError: If workflow runs cannot be listed
        """
        pass

    @abstractmethod
    def get_workflow_run(self, owner: str, repo: str, run_id: str) -> WorkflowRun:
        """Get details of a specific workflow run.

        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID

        Returns:
            Workflow run details

        Raises:
            PlatformError: If workflow run cannot be accessed
        """
        pass

    # Label operations
    @abstractmethod
    def add_labels_to_issue(
        self, owner: str, repo: str, issue_number: int, labels: List[str]
    ) -> None:
        """Add labels to an issue.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            labels: Labels to add

        Raises:
            PlatformError: If labels cannot be added
        """
        pass

    @abstractmethod
    def remove_labels_from_issue(
        self, owner: str, repo: str, issue_number: int, labels: List[str]
    ) -> None:
        """Remove labels from an issue.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number
            labels: Labels to remove

        Raises:
            PlatformError: If labels cannot be removed
        """
        pass

    # Utility methods
    def get_issue_url(self, owner: str, repo: str, issue_number: int) -> str:
        """Get URL for an issue.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number

        Returns:
            Issue URL
        """
        # Default implementation - should be overridden by platforms
        return f"https://{self.name}.com/{owner}/{repo}/issues/{issue_number}"

    def get_pull_request_url(self, owner: str, repo: str, pr_number: int) -> str:
        """Get URL for a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Pull request URL
        """
        # Default implementation - should be overridden by platforms
        return f"https://{self.name}.com/{owner}/{repo}/pull/{pr_number}"


class GitProvider(ABC):
    """Abstract base class for Git providers.

    Git providers handle low-level Git operations like cloning,
    branching, committing, and pushing.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the Git provider.

        Args:
            config: Git provider configuration
        """
        self.config = config

    @abstractmethod
    def clone_repository(
        self, repository_url: str, local_path: str, branch: Optional[str] = None
    ) -> None:
        """Clone a repository.

        Args:
            repository_url: Repository URL to clone
            local_path: Local path to clone to
            branch: Specific branch to clone

        Raises:
            GitOperationError: If clone operation fails
        """
        pass

    @abstractmethod
    def create_worktree(
        self,
        repository_path: str,
        worktree_path: str,
        branch_name: str,
        base_branch: Optional[str] = None,
    ) -> None:
        """Create a Git worktree.

        Args:
            repository_path: Path to main repository
            worktree_path: Path for new worktree
            branch_name: Name of branch to create
            base_branch: Base branch for new branch

        Raises:
            GitOperationError: If worktree creation fails
        """
        pass

    @abstractmethod
    def remove_worktree(self, worktree_path: str, force: bool = False) -> None:
        """Remove a Git worktree.

        Args:
            worktree_path: Path to worktree to remove
            force: Force removal even if worktree has changes

        Raises:
            GitOperationError: If worktree removal fails
        """
        pass

    @abstractmethod
    def commit_changes(
        self, repository_path: str, message: str, files: Optional[List[str]] = None
    ) -> str:
        """Commit changes to repository.

        Args:
            repository_path: Path to repository
            message: Commit message
            files: Specific files to commit (None for all changes)

        Returns:
            Commit hash

        Raises:
            GitOperationError: If commit operation fails
        """
        pass

    @abstractmethod
    def push_branch(
        self,
        repository_path: str,
        branch_name: str,
        remote: str = "origin",
        set_upstream: bool = True,
    ) -> None:
        """Push branch to remote repository.

        Args:
            repository_path: Path to repository
            branch_name: Name of branch to push
            remote: Remote name
            set_upstream: Set upstream branch

        Raises:
            GitOperationError: If push operation fails
        """
        pass

    @abstractmethod
    def get_current_branch(self, repository_path: str) -> str:
        """Get current branch name.

        Args:
            repository_path: Path to repository

        Returns:
            Current branch name

        Raises:
            GitOperationError: If branch detection fails
        """
        pass

    @abstractmethod
    def branch_exists(self, repository_path: str, branch_name: str, remote: bool = False) -> bool:
        """Check if branch exists.

        Args:
            repository_path: Path to repository
            branch_name: Name of branch to check
            remote: Check remote branches

        Returns:
            True if branch exists

        Raises:
            GitOperationError: If branch check fails
        """
        pass

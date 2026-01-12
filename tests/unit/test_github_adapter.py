"""Unit tests for GitHub platform adapter."""

from datetime import datetime
from unittest.mock import Mock, call, patch

import pytest

from devflow.adapters.base import IssueState, MergeStrategy, PullRequestState
from devflow.adapters.github.client import GitHubPlatformAdapter
from devflow.exceptions import PlatformError


class TestGitHubPlatformAdapter:
    """Test GitHubPlatformAdapter functionality."""

    @pytest.fixture
    def adapter_config(self):
        """Create adapter configuration."""
        return {
            "repo_owner": "test-owner",
            "repo_name": "test-repo",
            "project_root": "/tmp/test-project",
        }

    @pytest.fixture
    def adapter(self, adapter_config):
        """Create GitHub adapter instance."""
        return GitHubPlatformAdapter(adapter_config)

    def test_adapter_initialization(self, adapter):
        """Test adapter initializes properly."""
        assert adapter.name == "github"
        assert adapter.display_name == "GitHub"
        assert adapter.owner == "test-owner"
        assert adapter.repo == "test-repo"
        assert adapter.repo_full == "test-owner/test-repo"

    @patch("subprocess.run")
    def test_validate_connection_success(self, mock_run, adapter):
        """Test successful connection validation."""
        # Mock successful gh auth status
        mock_run.return_value = Mock(returncode=0, stdout="github.com\n")

        result = adapter.validate_connection()
        assert result is True

        mock_run.assert_called_once_with(
            ["gh", "auth", "status"], capture_output=True, text=True, check=False
        )

    @patch("subprocess.run")
    def test_validate_connection_failure(self, mock_run, adapter):
        """Test failed connection validation."""
        # Mock failed gh auth status
        mock_run.return_value = Mock(returncode=1, stderr="Not logged in")

        result = adapter.validate_connection()
        assert result is False

    @patch("subprocess.run")
    def test_get_repository_success(self, mock_run, adapter):
        """Test successful repository retrieval."""
        mock_output = """
{
  "name": "test-repo",
  "full_name": "test-owner/test-repo",
  "owner": {
    "login": "test-owner"
  },
  "description": "Test repository",
  "private": false,
  "html_url": "https://github.com/test-owner/test-repo",
  "default_branch": "main"
}
"""
        mock_run.return_value = Mock(returncode=0, stdout=mock_output)

        repo = adapter.get_repository("test-owner", "test-repo")

        assert repo.name == "test-repo"
        assert repo.full_name == "test-owner/test-repo"
        assert repo.owner == "test-owner"
        assert repo.description == "Test repository"
        assert repo.private is False
        assert repo.url == "https://github.com/test-owner/test-repo"
        assert repo.default_branch == "main"

    @patch("subprocess.run")
    def test_get_issue_success(self, mock_run, adapter):
        """Test successful issue retrieval."""
        mock_output = """
{
  "number": 123,
  "title": "Test Issue",
  "body": "This is a test issue",
  "state": "open",
  "labels": [
    {"name": "bug"},
    {"name": "enhancement"}
  ],
  "assignees": [
    {"login": "assignee1"}
  ],
  "user": {
    "login": "test-author"
  },
  "created_at": "2023-01-01T10:00:00Z",
  "updated_at": "2023-01-01T12:00:00Z",
  "html_url": "https://github.com/test-owner/test-repo/issues/123"
}
"""
        mock_run.return_value = Mock(returncode=0, stdout=mock_output)

        issue = adapter.get_issue("test-owner", "test-repo", 123)

        assert issue.number == 123
        assert issue.title == "Test Issue"
        assert issue.body == "This is a test issue"
        assert issue.state == IssueState.OPEN
        assert issue.labels == ["bug", "enhancement"]
        assert issue.assignees == ["assignee1"]
        assert issue.author == "test-author"
        assert issue.url == "https://github.com/test-owner/test-repo/issues/123"

    @patch("subprocess.run")
    def test_list_issues_success(self, mock_run, adapter):
        """Test successful issue listing."""
        mock_output = """
[
  {
    "number": 123,
    "title": "Test Issue 1",
    "body": "First issue",
    "state": "open",
    "labels": [{"name": "bug"}],
    "assignees": [],
    "user": {"login": "author1"},
    "created_at": "2023-01-01T10:00:00Z",
    "updated_at": "2023-01-01T10:00:00Z",
    "html_url": "https://github.com/test-owner/test-repo/issues/123"
  },
  {
    "number": 124,
    "title": "Test Issue 2",
    "body": "Second issue",
    "state": "closed",
    "labels": [],
    "assignees": [{"login": "assignee1"}],
    "user": {"login": "author2"},
    "created_at": "2023-01-01T11:00:00Z",
    "updated_at": "2023-01-01T11:00:00Z",
    "html_url": "https://github.com/test-owner/test-repo/issues/124"
  }
]
"""
        mock_run.return_value = Mock(returncode=0, stdout=mock_output)

        issues = adapter.list_issues("test-owner", "test-repo", limit=10)

        assert len(issues) == 2
        assert issues[0].number == 123
        assert issues[0].state == IssueState.OPEN
        assert issues[1].number == 124
        assert issues[1].state == IssueState.CLOSED

    @patch("subprocess.run")
    def test_create_issue_success(self, mock_run, adapter):
        """Test successful issue creation."""
        mock_output = """
{
  "number": 125,
  "title": "New Test Issue",
  "body": "This is a new test issue",
  "state": "open",
  "labels": [{"name": "bug"}],
  "assignees": [],
  "user": {"login": "test-author"},
  "created_at": "2023-01-01T13:00:00Z",
  "updated_at": "2023-01-01T13:00:00Z",
  "html_url": "https://github.com/test-owner/test-repo/issues/125"
}
"""
        mock_run.return_value = Mock(returncode=0, stdout=mock_output)

        issue = adapter.create_issue(
            owner="test-owner",
            repo="test-repo",
            title="New Test Issue",
            body="This is a new test issue",
            labels=["bug"],
        )

        assert issue.number == 125
        assert issue.title == "New Test Issue"
        assert issue.body == "This is a new test issue"
        assert issue.labels == ["bug"]

    @patch("subprocess.run")
    def test_get_pull_request_success(self, mock_run, adapter):
        """Test successful pull request retrieval."""
        mock_output = """
{
  "number": 456,
  "title": "Test PR",
  "body": "Test pull request",
  "state": "open",
  "head": {
    "ref": "feature-branch"
  },
  "base": {
    "ref": "main"
  },
  "user": {
    "login": "pr-author"
  },
  "requested_reviewers": [
    {"login": "reviewer1"}
  ],
  "labels": [
    {"name": "feature"}
  ],
  "created_at": "2023-01-01T14:00:00Z",
  "updated_at": "2023-01-01T14:00:00Z",
  "mergeable": true,
  "html_url": "https://github.com/test-owner/test-repo/pull/456"
}
"""
        mock_run.return_value = Mock(returncode=0, stdout=mock_output)

        pr = adapter.get_pull_request("test-owner", "test-repo", 456)

        assert pr.number == 456
        assert pr.title == "Test PR"
        assert pr.body == "Test pull request"
        assert pr.state == PullRequestState.OPEN
        assert pr.source_branch == "feature-branch"
        assert pr.target_branch == "main"
        assert pr.author == "pr-author"
        assert pr.reviewers == ["reviewer1"]
        assert pr.labels == ["feature"]
        assert pr.mergeable is True

    @patch("subprocess.run")
    def test_create_pull_request_success(self, mock_run, adapter):
        """Test successful pull request creation."""
        mock_output = """
{
  "number": 457,
  "title": "New Test PR",
  "body": "New test pull request",
  "state": "open",
  "head": {"ref": "new-feature"},
  "base": {"ref": "main"},
  "user": {"login": "test-author"},
  "requested_reviewers": [],
  "labels": [],
  "created_at": "2023-01-01T15:00:00Z",
  "updated_at": "2023-01-01T15:00:00Z",
  "mergeable": true,
  "html_url": "https://github.com/test-owner/test-repo/pull/457"
}
"""
        mock_run.return_value = Mock(returncode=0, stdout=mock_output)

        pr = adapter.create_pull_request(
            owner="test-owner",
            repo="test-repo",
            title="New Test PR",
            body="New test pull request",
            source_branch="new-feature",
            target_branch="main",
        )

        assert pr.number == 457
        assert pr.title == "New Test PR"
        assert pr.source_branch == "new-feature"
        assert pr.target_branch == "main"

    @patch("subprocess.run")
    def test_merge_pull_request_success(self, mock_run, adapter):
        """Test successful pull request merge."""
        mock_output = """
{
  "sha": "abc123def456",
  "merged": true,
  "message": "Pull request successfully merged"
}
"""
        mock_run.return_value = Mock(returncode=0, stdout=mock_output)

        result = adapter.merge_pull_request(
            owner="test-owner",
            repo="test-repo",
            pr_number=456,
            merge_strategy=MergeStrategy.SQUASH,
            commit_title="Test merge commit",
        )

        assert result["merged"] is True
        assert result["sha"] == "abc123def456"

    @patch("subprocess.run")
    def test_get_pull_request_files_success(self, mock_run, adapter):
        """Test successful retrieval of pull request files."""
        mock_output = """
[
  {
    "filename": "src/test.py",
    "status": "modified",
    "additions": 10,
    "deletions": 5,
    "changes": 15
  },
  {
    "filename": "tests/test_test.py",
    "status": "added",
    "additions": 20,
    "deletions": 0,
    "changes": 20
  }
]
"""
        mock_run.return_value = Mock(returncode=0, stdout=mock_output)

        files = adapter.get_pull_request_files("test-owner", "test-repo", 456)

        assert len(files) == 2
        assert files[0]["filename"] == "src/test.py"
        assert files[0]["status"] == "modified"
        assert files[1]["filename"] == "tests/test_test.py"
        assert files[1]["status"] == "added"

    @patch("subprocess.run")
    def test_command_failure_handling(self, mock_run, adapter):
        """Test handling of command failures."""
        # Mock failed command
        mock_run.return_value = Mock(returncode=1, stderr="Error: Repository not found", stdout="")

        with pytest.raises(PlatformError, match="GitHub command failed"):
            adapter.get_issue("test-owner", "test-repo", 999)

    def test_get_issue_url(self, adapter):
        """Test issue URL generation."""
        url = adapter.get_issue_url("test-owner", "test-repo", 123)
        assert url == "https://github.com/test-owner/test-repo/issues/123"

    def test_get_pull_request_url(self, adapter):
        """Test pull request URL generation."""
        url = adapter.get_pull_request_url("test-owner", "test-repo", 456)
        assert url == "https://github.com/test-owner/test-repo/pull/456"

    @patch("subprocess.run")
    def test_add_issue_comment_success(self, mock_run, adapter):
        """Test successful issue comment addition."""
        mock_output = """
{
  "id": 123456,
  "body": "Test comment",
  "user": {"login": "test-user"},
  "created_at": "2023-01-01T16:00:00Z",
  "html_url": "https://github.com/test-owner/test-repo/issues/123#issuecomment-123456"
}
"""
        mock_run.return_value = Mock(returncode=0, stdout=mock_output)

        result = adapter.add_issue_comment(
            owner="test-owner", repo="test-repo", issue_number=123, body="Test comment"
        )

        assert result["id"] == 123456
        assert result["body"] == "Test comment"

    @patch("subprocess.run")
    def test_invalid_json_response(self, mock_run, adapter):
        """Test handling of invalid JSON response."""
        mock_run.return_value = Mock(returncode=0, stdout="Invalid JSON response")

        with pytest.raises(PlatformError, match="Failed to parse GitHub response"):
            adapter.get_issue("test-owner", "test-repo", 123)

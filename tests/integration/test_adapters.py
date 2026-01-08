"""Integration tests for platform adapters."""

import pytest
from pathlib import Path

from devflow.adapters.git.basic import BasicGitAdapter
from devflow.adapters.base import IssueState, PullRequestState, MergeStrategy
from devflow.exceptions import PlatformError


class TestBasicGitAdapter:
    """Test BasicGitAdapter functionality."""

    @pytest.fixture
    def adapter(self):
        """Create basic git adapter."""
        config = {
            "repo_owner": "test-owner",
            "repo_name": "test-repo",
            "project_root": str(Path.cwd())
        }
        return BasicGitAdapter(config)

    def test_adapter_initialization(self, adapter):
        """Test adapter initializes properly."""
        assert adapter.name == "basic_git"
        assert adapter.display_name == "Basic Git"
        assert adapter.owner == "test-owner"
        assert adapter.repo == "test-repo"
        assert adapter.repo_full == "test-owner/test-repo"

    def test_validate_connection(self, adapter):
        """Test connection validation."""
        # Should pass if git is available
        result = adapter.validate_connection()
        assert isinstance(result, bool)

    def test_get_repository(self, adapter):
        """Test repository information retrieval."""
        repo = adapter.get_repository("test-owner", "test-repo")
        assert repo.name == "test-repo"
        assert repo.full_name == "test-owner/test-repo"
        assert repo.owner == "test-owner"
        assert repo.platform_data["mock"] is True

    def test_get_issue(self, adapter):
        """Test issue retrieval."""
        issue = adapter.get_issue("test-owner", "test-repo", 123)
        assert issue.number == 123
        assert issue.title == "Mock Issue #123"
        assert issue.state == IssueState.OPEN
        assert "bug" in issue.labels
        assert issue.platform_data["mock"] is True

    def test_list_issues(self, adapter):
        """Test issue listing."""
        issues = adapter.list_issues("test-owner", "test-repo", limit=5)
        assert len(issues) == 3  # Returns mock issues 1, 2, 3
        assert all(issue.platform_data["mock"] is True for issue in issues)

    def test_create_issue(self, adapter):
        """Test issue creation."""
        issue = adapter.create_issue(
            owner="test-owner",
            repo="test-repo",
            title="Test Issue",
            body="Test issue body",
            labels=["bug", "test"]
        )
        assert issue.title == "Test Issue"
        assert issue.body == "Test issue body"
        assert issue.labels == ["bug", "test"]
        assert issue.platform_data["mock"] is True

    def test_update_issue(self, adapter):
        """Test issue updating."""
        updated_issue = adapter.update_issue(
            owner="test-owner",
            repo="test-repo",
            issue_number=123,
            title="Updated Title",
            state=IssueState.CLOSED
        )
        assert updated_issue.title == "Updated Title"
        assert updated_issue.state == IssueState.CLOSED

    def test_add_issue_comment(self, adapter):
        """Test adding issue comment."""
        result = adapter.add_issue_comment(
            owner="test-owner",
            repo="test-repo",
            issue_number=123,
            body="Test comment"
        )
        assert result["body"] == "Test comment"
        assert result["mock"] is True

    def test_get_pull_request(self, adapter):
        """Test pull request retrieval."""
        pr = adapter.get_pull_request("test-owner", "test-repo", 456)
        assert pr.number == 456
        assert pr.title == "Mock PR #456"
        assert pr.state == PullRequestState.OPEN
        assert pr.platform_data["mock"] is True

    def test_list_pull_requests(self, adapter):
        """Test pull request listing."""
        prs = adapter.list_pull_requests("test-owner", "test-repo")
        assert len(prs) == 2  # Returns mock PRs 1, 2
        assert all(pr.platform_data["mock"] is True for pr in prs)

    def test_create_pull_request(self, adapter):
        """Test pull request creation."""
        pr = adapter.create_pull_request(
            owner="test-owner",
            repo="test-repo",
            title="Test PR",
            body="Test PR body",
            source_branch="feature/test",
            target_branch="main"
        )
        assert pr.title == "Test PR"
        assert pr.body == "Test PR body"
        assert pr.source_branch == "feature/test"
        assert pr.target_branch == "main"
        assert pr.platform_data["mock"] is True

    def test_update_pull_request(self, adapter):
        """Test pull request updating."""
        updated_pr = adapter.update_pull_request(
            owner="test-owner",
            repo="test-repo",
            pr_number=456,
            title="Updated PR Title",
            state=PullRequestState.CLOSED
        )
        assert updated_pr.title == "Updated PR Title"
        assert updated_pr.state == PullRequestState.CLOSED

    def test_merge_pull_request(self, adapter):
        """Test pull request merging."""
        result = adapter.merge_pull_request(
            owner="test-owner",
            repo="test-repo",
            pr_number=456,
            merge_strategy=MergeStrategy.SQUASH,
            commit_title="Test merge"
        )
        assert result["merged"] is True
        assert result["strategy"] == "squash"
        assert result["mock"] is True

    def test_get_pull_request_files(self, adapter):
        """Test getting pull request files."""
        files = adapter.get_pull_request_files("test-owner", "test-repo", 456)
        assert len(files) == 2
        assert files[0]["filename"] == "src/example.py"
        assert files[1]["filename"] == "tests/test_example.py"

    def test_label_operations(self, adapter):
        """Test label operations (mock - should not raise errors)."""
        # These are mock operations that do nothing but should not fail
        adapter.add_labels_to_issue("test-owner", "test-repo", 123, ["test"])
        adapter.remove_labels_from_issue("test-owner", "test-repo", 123, ["test"])

    def test_get_urls(self, adapter):
        """Test URL generation."""
        issue_url = adapter.get_issue_url("test-owner", "test-repo", 123)
        assert issue_url == "https://github.com/test-owner/test-repo/issues/123"

        pr_url = adapter.get_pull_request_url("test-owner", "test-repo", 456)
        assert pr_url == "https://github.com/test-owner/test-repo/pull/456"

    def test_invalid_config(self):
        """Test adapter with invalid configuration."""
        config = {
            "repo_owner": "test-owner",
            "repo_name": "test-repo",
            "project_root": "/nonexistent/path"
        }
        with pytest.raises(PlatformError):
            BasicGitAdapter(config)
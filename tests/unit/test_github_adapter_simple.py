"""Simplified unit tests for GitHub platform adapter."""

from unittest.mock import Mock, patch

import pytest

from devflow.adapters.base import IssueState, MergeStrategy, PullRequestState
from devflow.adapters.github.client import GitHubPlatformAdapter
from devflow.exceptions import PlatformError


class TestGitHubPlatformAdapter:
    """Test GitHubPlatformAdapter basic functionality."""

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

    def test_adapter_properties(self, adapter):
        """Test adapter properties."""
        assert isinstance(adapter.name, str)
        assert isinstance(adapter.display_name, str)
        assert isinstance(adapter.owner, str)
        assert isinstance(adapter.repo, str)
        assert isinstance(adapter.repo_full, str)

    def test_get_issue_url(self, adapter):
        """Test issue URL generation."""
        url = adapter.get_issue_url("test-owner", "test-repo", 123)
        assert url == "https://github.com/test-owner/test-repo/issues/123"

    def test_get_pull_request_url(self, adapter):
        """Test pull request URL generation."""
        url = adapter.get_pull_request_url("test-owner", "test-repo", 456)
        assert url == "https://github.com/test-owner/test-repo/pull/456"

    def test_url_generation_with_different_repos(self, adapter):
        """Test URL generation with different repository details."""
        issue_url = adapter.get_issue_url("other-owner", "other-repo", 789)
        assert issue_url == "https://github.com/other-owner/other-repo/issues/789"

        pr_url = adapter.get_pull_request_url("other-owner", "other-repo", 999)
        assert pr_url == "https://github.com/other-owner/other-repo/pull/999"

    @patch("subprocess.run")
    def test_validate_connection_success(self, mock_run, adapter):
        """Test successful connection validation."""
        # Mock successful gh auth status
        mock_run.return_value = Mock(returncode=0, stdout="github.com\n")

        result = adapter.validate_connection()
        assert result is True

        # Should call both auth status and repo view
        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            ["gh", "auth", "status"], capture_output=True, text=True, check=False, timeout=30
        )
        mock_run.assert_any_call(
            ["gh", "repo", "view", "test-owner/test-repo", "--json", "name"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    @patch("subprocess.run")
    def test_validate_connection_failure(self, mock_run, adapter):
        """Test failed connection validation."""
        # Mock failed gh auth status
        mock_run.return_value = Mock(returncode=1, stderr="Not logged in")

        # Expect a PlatformError to be raised, not False returned
        with pytest.raises(PlatformError, match="GitHub CLI not authenticated"):
            adapter.validate_connection()

    def test_adapter_configuration(self, adapter_config):
        """Test adapter configuration."""
        adapter = GitHubPlatformAdapter(adapter_config)

        assert adapter.owner == adapter_config["repo_owner"]
        assert adapter.repo == adapter_config["repo_name"]

    def test_repo_full_name_construction(self, adapter):
        """Test repository full name construction."""
        expected_full_name = f"{adapter.owner}/{adapter.repo}"
        assert adapter.repo_full == expected_full_name

    def test_adapter_name_constants(self, adapter):
        """Test adapter name constants."""
        assert adapter.name == "github"
        assert adapter.display_name == "GitHub"

    def test_url_patterns(self, adapter):
        """Test URL pattern generation."""
        # Test with various issue numbers
        for issue_num in [1, 123, 9999]:
            url = adapter.get_issue_url("owner", "repo", issue_num)
            assert url.endswith(f"/issues/{issue_num}")
            assert "github.com" in url

        # Test with various PR numbers
        for pr_num in [1, 456, 8888]:
            url = adapter.get_pull_request_url("owner", "repo", pr_num)
            assert url.endswith(f"/pull/{pr_num}")
            assert "github.com" in url

    def test_adapter_initialization_with_minimal_config(self):
        """Test adapter initialization with minimal configuration."""
        config = {"repo_owner": "minimal", "repo_name": "test", "project_root": "/tmp"}

        adapter = GitHubPlatformAdapter(config)
        assert adapter.owner == "minimal"
        assert adapter.repo == "test"
        assert adapter.repo_full == "minimal/test"

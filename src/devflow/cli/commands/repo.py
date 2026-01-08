"""Repository management commands."""

import subprocess
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Confirm, Prompt

from devflow.adapters.github.client import GitHubPlatformAdapter
from devflow.core.config import ProjectConfig, load_config
from devflow.exceptions import ConfigurationError, PlatformError

console = Console()


def create_repository(
    name: str,
    owner: Optional[str] = None,
    description: str = "",
    private: bool = False,
    setup_labels: bool = True
) -> dict:
    """Create a new GitHub repository.

    Args:
        name: Repository name
        owner: Repository owner (defaults to authenticated user)
        description: Repository description
        private: Create as private repository
        setup_labels: Set up DevFlow standard labels

    Returns:
        Repository creation result

    Raises:
        PlatformError: If repository creation fails
    """
    try:
        # Get authenticated user if no owner specified
        if not owner:
            result = subprocess.run(
                ["gh", "api", "/user", "--jq", ".login"],
                capture_output=True,
                text=True,
                check=True
            )
            owner = result.stdout.strip()

        # Create GitHub adapter
        adapter_config = {
            "repo_owner": owner,
            "repo_name": name
        }
        adapter = GitHubPlatformAdapter(adapter_config)

        console.print(f"[blue]Creating repository {owner}/{name}...[/blue]")

        # Create the repository
        repository = adapter.create_repository(
            owner=owner,
            repo=name,
            description=description,
            private=private
        )

        console.print(f"[green]✓ Repository created: {repository.url}[/green]")

        # Set up standard labels
        if setup_labels:
            console.print("[blue]Setting up DevFlow labels...[/blue]")
            try:
                adapter.setup_repository_labels(owner, name)
                console.print("[green]✓ Labels configured[/green]")
            except Exception as e:
                console.print(f"[yellow]⚠ Failed to setup labels: {e}[/yellow]")

        # Add git remote if we're in a git repository
        try:
            subprocess.run(
                ["git", "remote", "add", "origin", repository.ssh_url],
                check=False,  # Don't fail if remote already exists
                capture_output=True
            )
            console.print("[green]✓ Git remote added[/green]")
        except Exception:
            pass

        return {
            "success": True,
            "repository": repository.__dict__,
            "url": repository.url,
            "ssh_url": repository.ssh_url
        }

    except Exception as e:
        console.print(f"[red]✗ Repository creation failed: {str(e)}[/red]")
        raise PlatformError(f"Failed to create repository: {str(e)}") from e


def connect_repository(owner: str, repo: str, update_config: bool = True) -> dict:
    """Connect to an existing GitHub repository.

    Args:
        owner: Repository owner
        repo: Repository name
        update_config: Update DevFlow configuration

    Returns:
        Connection result

    Raises:
        PlatformError: If connection fails
    """
    try:
        console.print(f"[blue]Connecting to {owner}/{repo}...[/blue]")

        # Create adapter and validate connection
        adapter_config = {
            "repo_owner": owner,
            "repo_name": repo
        }
        adapter = GitHubPlatformAdapter(adapter_config)

        # Test connection and get repository info
        if not adapter.validate_connection():
            raise PlatformError("Failed to connect to repository")

        repository = adapter.get_repository(owner, repo)
        console.print(f"[green]✓ Connected to: {repository.full_name}[/green]")
        console.print(f"  Description: {repository.description}")
        console.print(f"  Default branch: {repository.default_branch}")

        # Update DevFlow configuration if requested
        if update_config:
            try:
                config = load_config()
                config.repo_owner = owner
                config.repo_name = repo
                config.base_branch = repository.default_branch

                config.save_to_file(Path("devflow.yaml"))
                console.print("[green]✓ DevFlow configuration updated[/green]")

            except ConfigurationError:
                console.print("[yellow]⚠ No DevFlow configuration found[/yellow]")
                console.print("Run 'devflow init' to create one")

        # Add git remote if we're in a git repository
        try:
            # Check if we're in a git repository
            subprocess.run(["git", "status"], check=True, capture_output=True)

            # Add remote
            subprocess.run(
                ["git", "remote", "add", "origin", repository.ssh_url],
                check=False,  # Don't fail if remote already exists
                capture_output=True
            )
            console.print("[green]✓ Git remote configured[/green]")

        except subprocess.CalledProcessError:
            console.print("[dim]Not in a git repository - skipping remote setup[/dim]")

        return {
            "success": True,
            "repository": repository.__dict__,
            "owner": owner,
            "repo": repo,
            "url": repository.url
        }

    except Exception as e:
        console.print(f"[red]✗ Connection failed: {str(e)}[/red]")
        raise PlatformError(f"Failed to connect to repository: {str(e)}") from e


def validate_repository_setup(
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    check_labels: bool = True,
    check_permissions: bool = True
) -> dict:
    """Validate repository setup for DevFlow.

    Args:
        owner: Repository owner (from config if not specified)
        repo: Repository name (from config if not specified)
        check_labels: Check for required labels
        check_permissions: Check repository permissions

    Returns:
        Validation results

    Raises:
        ConfigurationError: If repository not configured
    """
    try:
        # Get repository info from config if not provided
        if not owner or not repo:
            try:
                config = load_config()
                owner = owner or config.repo_owner
                repo = repo or config.repo_name
            except ConfigurationError:
                raise ConfigurationError("No repository configured. Use 'devflow repo connect' first.")

        if not owner or not repo:
            raise ConfigurationError("Repository owner and name must be specified")

        console.print(f"[blue]Validating repository setup: {owner}/{repo}[/blue]")

        adapter_config = {
            "repo_owner": owner,
            "repo_name": repo
        }
        adapter = GitHubPlatformAdapter(adapter_config)

        validation_results = []

        # Basic connection test
        try:
            if adapter.validate_connection():
                validation_results.append({
                    "check": "Repository Access",
                    "status": "✓",
                    "message": "Can access repository"
                })
            else:
                validation_results.append({
                    "check": "Repository Access",
                    "status": "✗",
                    "message": "Cannot access repository"
                })
        except Exception as e:
            validation_results.append({
                "check": "Repository Access",
                "status": "✗",
                "message": str(e)
            })

        # Check permissions
        if check_permissions:
            try:
                # Try to list issues to test read permissions
                issues = adapter.list_issues(owner, repo, limit=1)
                validation_results.append({
                    "check": "Read Permissions",
                    "status": "✓",
                    "message": "Can read issues and PRs"
                })

                # Try to create a test label to check write permissions (then delete it)
                try:
                    subprocess.run([
                        "gh", "label", "create", "devflow-test-label",
                        "--repo", f"{owner}/{repo}",
                        "--color", "000000",
                        "--description", "Test label"
                    ], check=True, capture_output=True)

                    subprocess.run([
                        "gh", "label", "delete", "devflow-test-label",
                        "--repo", f"{owner}/{repo}",
                        "--yes"
                    ], check=True, capture_output=True)

                    validation_results.append({
                        "check": "Write Permissions",
                        "status": "✓",
                        "message": "Can create issues, PRs, and labels"
                    })
                except subprocess.CalledProcessError:
                    validation_results.append({
                        "check": "Write Permissions",
                        "status": "✗",
                        "message": "Cannot create/modify repository resources"
                    })

            except Exception as e:
                validation_results.append({
                    "check": "Permissions",
                    "status": "✗",
                    "message": str(e)
                })

        # Check for DevFlow labels
        if check_labels:
            try:
                result = subprocess.run([
                    "gh", "label", "list",
                    "--repo", f"{owner}/{repo}",
                    "--json", "name"
                ], check=True, capture_output=True, text=True)

                import json
                existing_labels = {label["name"] for label in json.loads(result.stdout)}

                required_labels = [
                    "bug", "enhancement", "documentation",
                    "automated-fix", "needs-human-review"
                ]

                missing_labels = [label for label in required_labels if label not in existing_labels]

                if not missing_labels:
                    validation_results.append({
                        "check": "DevFlow Labels",
                        "status": "✓",
                        "message": "All required labels present"
                    })
                else:
                    validation_results.append({
                        "check": "DevFlow Labels",
                        "status": "⚠",
                        "message": f"Missing labels: {', '.join(missing_labels)}"
                    })

            except Exception as e:
                validation_results.append({
                    "check": "Labels",
                    "status": "✗",
                    "message": str(e)
                })

        # Display results
        from rich.table import Table
        table = Table(title=f"Repository Validation: {owner}/{repo}")
        table.add_column("Check", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Details")

        all_passed = True
        for result in validation_results:
            table.add_row(result["check"], result["status"], result["message"])
            if result["status"] == "✗":
                all_passed = False

        console.print(table)

        if all_passed:
            console.print(f"\n[green]✓ Repository {owner}/{repo} is ready for DevFlow![/green]")
        else:
            console.print(f"\n[yellow]⚠ Repository {owner}/{repo} has some issues[/yellow]")
            console.print("Consider running: devflow repo setup-labels")

        return {
            "success": all_passed,
            "results": validation_results,
            "owner": owner,
            "repo": repo
        }

    except Exception as e:
        console.print(f"[red]✗ Validation failed: {str(e)}[/red]")
        raise


def setup_repository_labels(
    owner: Optional[str] = None,
    repo: Optional[str] = None
) -> dict:
    """Set up DevFlow standard labels in repository.

    Args:
        owner: Repository owner (from config if not specified)
        repo: Repository name (from config if not specified)

    Returns:
        Setup result

    Raises:
        ConfigurationError: If repository not configured
    """
    try:
        # Get repository info from config if not provided
        if not owner or not repo:
            try:
                config = load_config()
                owner = owner or config.repo_owner
                repo = repo or config.repo_name
            except ConfigurationError:
                raise ConfigurationError("No repository configured. Use 'devflow repo connect' first.")

        if not owner or not repo:
            raise ConfigurationError("Repository owner and name must be specified")

        console.print(f"[blue]Setting up labels for {owner}/{repo}...[/blue]")

        adapter_config = {
            "repo_owner": owner,
            "repo_name": repo
        }
        adapter = GitHubPlatformAdapter(adapter_config)

        adapter.setup_repository_labels(owner, repo)

        console.print("[green]✓ DevFlow labels configured successfully[/green]")

        return {
            "success": True,
            "owner": owner,
            "repo": repo
        }

    except Exception as e:
        console.print(f"[red]✗ Label setup failed: {str(e)}[/red]")
        raise PlatformError(f"Failed to setup labels: {str(e)}") from e
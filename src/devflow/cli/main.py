"""Main CLI entry point for DevFlow.

This module provides the command-line interface for DevFlow with comprehensive
validation, error handling, and user-friendly output formatting.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from devflow import __version__
from devflow.core.config import MaturityConfig, ProjectConfig, load_config
from devflow.exceptions import ConfigurationError, DevFlowError, ValidationError

# Rich console for beautiful output
console = Console()


# Configure logging with Rich
def setup_logging(level: str = "INFO") -> None:
    """Setup logging with Rich formatting.

    Args:
        level: Logging level
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def handle_error(error: Exception, show_traceback: bool = False) -> None:
    """Handle and display errors in a user-friendly way.

    Args:
        error: Exception to handle
        show_traceback: Whether to show full traceback
    """
    if isinstance(error, DevFlowError):
        console.print(f"\n[red]Error:[/red] {error.message}")

        if error.context:
            console.print("\n[yellow]Context:[/yellow]")
            for key, value in error.context.items():
                console.print(f"  {key}: {value}")

        if hasattr(error, "suggestions") and error.suggestions:
            console.print("\n[blue]Suggestions:[/blue]")
            for suggestion in error.suggestions:
                console.print(f"  • {suggestion}")
    else:
        console.print(f"\n[red]Unexpected error:[/red] {str(error)}")

    if show_traceback:
        console.print_exception()


def validate_project_context() -> Optional[ProjectConfig]:
    """Validate that we're in a valid project context.

    Returns:
        Project configuration if valid, None otherwise
    """
    try:
        return load_config()
    except ConfigurationError:
        return None


def require_project_context() -> ProjectConfig:
    """Require valid project context or exit.

    Returns:
        Project configuration

    Raises:
        click.ClickException: If no valid project found
    """
    config = validate_project_context()
    if not config:
        console.print(
            "\n[red]Error:[/red] No DevFlow project found in current directory or parents."
        )
        console.print("\n[blue]To initialize a new project:[/blue]")
        console.print("  devflow init")
        console.print("\n[blue]To specify a config file:[/blue]")
        console.print("  devflow --config-file path/to/devflow.yaml <command>")
        raise click.ClickException("Project not found")

    return config


# Custom Click group with error handling
class DevFlowGroup(click.Group):
    """Custom Click group with enhanced error handling."""

    def invoke(self, ctx: click.Context) -> None:
        """Invoke command with error handling."""
        try:
            return super().invoke(ctx)
        except DevFlowError as e:
            handle_error(e, ctx.obj.get("debug", False) if ctx.obj else False)
            sys.exit(1)
        except Exception as e:
            handle_error(e, ctx.obj.get("debug", False) if ctx.obj else False)
            sys.exit(1)


@click.group(cls=DevFlowGroup)
@click.option(
    "--config-file", type=click.Path(exists=True, path_type=Path), help="Path to configuration file"
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Set logging level",
)
@click.option("--debug", is_flag=True, help="Enable debug mode with full tracebacks")
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx: click.Context, config_file: Optional[Path], log_level: str, debug: bool) -> None:
    """DevFlow - Intelligent Developer Workflow Automation.

    A sophisticated automation tool that streamlines the development lifecycle
    with AI-powered assistance and multi-platform support.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Store global options
    ctx.obj["config_file"] = config_file
    ctx.obj["log_level"] = log_level
    ctx.obj["debug"] = debug

    # Setup logging
    setup_logging(log_level)

    # Display welcome message for main command
    if ctx.invoked_subcommand is None:
        console.print(
            Panel.fit(
                f"[bold blue]DevFlow v{__version__}[/bold blue]\n"
                "Intelligent Developer Workflow Automation",
                title="Welcome to DevFlow",
            )
        )


@cli.command()
@click.option("--project-name", help="Project name (defaults to directory name)")
@click.option(
    "--maturity-level",
    type=click.Choice(["prototype", "early_stage", "stable", "mature"]),
    default="early_stage",
    help="Project maturity level",
)
@click.option(
    "--platform",
    type=click.Choice(["github", "gitlab", "bitbucket"]),
    default="github",
    help="Primary platform",
)
@click.option("--force", is_flag=True, help="Force initialization even if config exists")
@click.pass_context
def init(
    ctx: click.Context, project_name: Optional[str], maturity_level: str, platform: str, force: bool
) -> None:
    """Initialize a new DevFlow project.

    This command creates a new DevFlow configuration file and sets up
    the project for automated workflows.
    """
    from devflow.cli.commands.init import initialize_project

    console.print("[bold blue]Initializing DevFlow project...[/bold blue]")

    try:
        config = initialize_project(
            project_name=project_name,
            maturity_level=maturity_level,
            platform=platform,
            force=force,
            config_file=ctx.obj.get("config_file"),
        )

        console.print("\n[green]✓[/green] Project initialized successfully!")
        console.print(f"  Project: {config.project_name}")
        console.print(f"  Maturity: {config.maturity_level}")
        console.print(f"  Platform: {config.platforms.primary}")

        # Show next steps
        console.print("\n[bold]Next steps:[/bold]")
        console.print("  1. Review and customize: devflow.yaml")
        console.print("  2. Validate setup: devflow validate")
        console.print("  3. Process your first issue: devflow process --issue <number>")

    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Project initialization failed")


@cli.command()
@click.pass_context
def validate(ctx: click.Context) -> None:
    """Validate DevFlow configuration and environment.

    This command checks the project configuration, platform connectivity,
    and required tools to ensure everything is properly set up.
    """
    from devflow.cli.commands.validate import validate_environment

    console.print("[bold blue]Validating DevFlow environment...[/bold blue]")

    try:
        config = require_project_context()
        validation_results = validate_environment(config)

        # Display results
        table = Table(title="Validation Results")
        table.add_column("Component", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Details")

        for result in validation_results:
            status = "[green]✓[/green]" if result["passed"] else "[red]✗[/red]"
            table.add_row(result["component"], status, result["message"])

        console.print(table)

        # Summary
        passed = sum(1 for r in validation_results if r["passed"])
        total = len(validation_results)

        if passed == total:
            console.print(f"\n[green]All {total} validations passed![/green]")
        else:
            failed = total - passed
            console.print(f"\n[yellow]{failed} of {total} validations failed.[/yellow]")
            console.print("Please fix the issues above before proceeding.")

    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Validation failed")


@cli.command()
@click.option("--issue", type=int, help="Issue number to process")
@click.option("--auto", is_flag=True, help="Run in fully automated mode")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
@click.pass_context
def process(ctx: click.Context, issue: Optional[int], auto: bool, dry_run: bool) -> None:
    """Process an issue through the DevFlow pipeline.

    This command runs the complete automation pipeline for an issue:
    validation → implementation → review → finalization.
    """
    from devflow.cli.commands.process import process_issue

    config = require_project_context()

    if not issue:
        console.print("[yellow]No issue specified.[/yellow]")
        console.print("Use: devflow process --issue <number>")
        return

    console.print(f"[bold blue]Processing issue #{issue}...[/bold blue]")

    if dry_run:
        console.print("[yellow]Running in dry-run mode - no changes will be made[/yellow]")

    try:
        result = process_issue(config=config, issue_number=issue, auto_mode=auto, dry_run=dry_run)

        # Display results
        if result["success"]:
            console.print(f"\n[green]✓[/green] Issue #{issue} processed successfully!")
            if result.get("pull_request"):
                pr = result["pull_request"]
                console.print(f"  Pull Request: {pr['url']}")
                console.print(f"  Status: {pr['status']}")
        else:
            console.print(f"\n[red]✗[/red] Issue #{issue} processing failed.")
            if result.get("error"):
                console.print(f"  Error: {result['error']}")

    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Issue processing failed")


@cli.command()
@click.option(
    "--format", type=click.Choice(["table", "json", "yaml"]), default="table", help="Output format"
)
@click.pass_context
def status(ctx: click.Context, format: str) -> None:
    """Show DevFlow project status.

    This command displays the current status of workflows, issues,
    and project configuration.
    """
    from devflow.cli.commands.status import show_status

    config = require_project_context()

    console.print("[bold blue]DevFlow Project Status[/bold blue]")

    try:
        status_data = show_status(config, format)

        if format == "table":
            # Project info
            info_table = Table(title="Project Information")
            info_table.add_column("Property", style="cyan")
            info_table.add_column("Value")

            info_table.add_row("Name", status_data["project"]["name"])
            info_table.add_row("Maturity", status_data["project"]["maturity_level"])
            info_table.add_row("Platform", status_data["project"]["platform"])
            info_table.add_row("Repository", status_data["project"]["repository"])

            console.print(info_table)

            # Active workflows
            if status_data["workflows"]:
                workflow_table = Table(title="Active Workflows")
                workflow_table.add_column("Issue", style="cyan")
                workflow_table.add_column("Status")
                workflow_table.add_column("Stage")
                workflow_table.add_column("Updated")

                for workflow in status_data["workflows"]:
                    workflow_table.add_row(
                        f"#{workflow['issue_number']}",
                        workflow["status"],
                        workflow["stage"],
                        workflow["updated_at"],
                    )

                console.print(workflow_table)
            else:
                console.print("\n[dim]No active workflows[/dim]")

        elif format == "json":
            import json

            console.print(json.dumps(status_data, indent=2))
        elif format == "yaml":
            import yaml

            console.print(yaml.dump(status_data, default_flow_style=False))

    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Status retrieval failed")


@cli.command()
@click.option("--completed", is_flag=True, help="Clean up completed workflows")
@click.option("--force", is_flag=True, help="Force cleanup without confirmation")
@click.option("--dry-run", is_flag=True, help="Show what would be cleaned up")
@click.pass_context
def cleanup(ctx: click.Context, completed: bool, force: bool, dry_run: bool) -> None:
    """Clean up DevFlow workflows and temporary files.

    This command removes completed workflows, temporary files,
    and orphaned resources.
    """
    from devflow.cli.commands.cleanup import cleanup_workflows

    config = require_project_context()

    console.print("[bold blue]Cleaning up DevFlow resources...[/bold blue]")

    if dry_run:
        console.print("[yellow]Running in dry-run mode - no changes will be made[/yellow]")

    try:
        result = cleanup_workflows(
            config=config, completed_only=completed, force=force, dry_run=dry_run
        )

        # Display results
        console.print(f"\n[green]Cleanup completed![/green]")
        console.print(f"  Workflows cleaned: {result['workflows_cleaned']}")
        console.print(f"  Files removed: {result['files_removed']}")
        console.print(f"  Space freed: {result['space_freed']}")

    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Cleanup failed")


@cli.command()
@click.argument("key")
@click.argument("value", required=False)
@click.option("--unset", is_flag=True, help="Remove the configuration key")
@click.option("--list", is_flag=True, help="List all configuration values")
@click.pass_context
def config(
    ctx: click.Context, key: Optional[str], value: Optional[str], unset: bool, list: bool
) -> None:
    """Manage DevFlow configuration.

    Examples:
        devflow config --list                    # List all settings
        devflow config maturity_level            # Get a setting
        devflow config maturity_level stable     # Set a setting
        devflow config --unset some.key          # Remove a setting
    """
    from devflow.cli.commands.config import manage_config

    if list:
        console.print("[bold blue]DevFlow Configuration[/bold blue]")

        try:
            config_data = require_project_context()
            settings = config_data.get_effective_settings()

            table = Table(title="Current Configuration")
            table.add_column("Setting", style="cyan")
            table.add_column("Value")
            table.add_column("Source")

            for setting_key, setting_value in settings.items():
                table.add_row(setting_key, str(setting_value), "project")

            console.print(table)

        except Exception as e:
            handle_error(e, ctx.obj.get("debug", False))
            raise click.ClickException("Configuration retrieval failed")

        return

    if not key:
        console.print("[red]Error:[/red] Key is required")
        console.print("Use: devflow config <key> [value]")
        return

    try:
        result = manage_config(
            key=key, value=value, unset=unset, config_file=ctx.obj.get("config_file")
        )

        if unset:
            console.print(f"[green]✓[/green] Unset {key}")
        elif value:
            console.print(f"[green]✓[/green] Set {key} = {value}")
        else:
            console.print(f"{key} = {result}")

    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Configuration management failed")


@cli.group(name="repo")
@click.pass_context
def repo_group(ctx: click.Context) -> None:
    """Manage GitHub repositories."""
    pass


@repo_group.command(name="create")
@click.option("--name", required=True, help="Repository name")
@click.option("--owner", help="Repository owner (defaults to authenticated user)")
@click.option("--description", default="", help="Repository description")
@click.option("--private", is_flag=True, help="Create as private repository")
@click.option("--no-labels", is_flag=True, help="Skip setting up DevFlow labels")
@click.pass_context
def repo_create(
    ctx: click.Context,
    name: str,
    owner: Optional[str],
    description: str,
    private: bool,
    no_labels: bool,
) -> None:
    """Create a new GitHub repository."""
    from devflow.cli.commands.repo import create_repository

    try:
        result = create_repository(
            name=name,
            owner=owner,
            description=description,
            private=private,
            setup_labels=not no_labels,
        )

        console.print(f"\n[green]Repository created successfully![/green]")
        console.print(f"URL: {result['url']}")
        console.print(f"SSH: {result['ssh_url']}")

    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Repository creation failed")


@repo_group.command(name="connect")
@click.argument("repository")
@click.option("--no-config-update", is_flag=True, help="Don't update DevFlow configuration")
@click.pass_context
def repo_connect(ctx: click.Context, repository: str, no_config_update: bool) -> None:
    """Connect to an existing GitHub repository.

    REPOSITORY should be in format: owner/repo
    """
    from devflow.cli.commands.repo import connect_repository

    try:
        if "/" not in repository:
            raise click.BadParameter("Repository must be in format: owner/repo")

        owner, repo = repository.split("/", 1)

        result = connect_repository(owner=owner, repo=repo, update_config=not no_config_update)

        console.print(f"\n[green]Connected to repository![/green]")
        console.print(f"Repository: {result['repository']['full_name']}")
        console.print(f"URL: {result['url']}")

    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Repository connection failed")


@repo_group.command(name="validate")
@click.option("--repository", help="Repository in format owner/repo (uses config if not specified)")
@click.option("--no-labels", is_flag=True, help="Skip label validation")
@click.option("--no-permissions", is_flag=True, help="Skip permission checks")
@click.pass_context
def repo_validate(
    ctx: click.Context, repository: Optional[str], no_labels: bool, no_permissions: bool
) -> None:
    """Validate repository setup for DevFlow."""
    from devflow.cli.commands.repo import validate_repository_setup

    try:
        owner = None
        repo = None

        if repository:
            if "/" not in repository:
                raise click.BadParameter("Repository must be in format: owner/repo")
            owner, repo = repository.split("/", 1)

        result = validate_repository_setup(
            owner=owner, repo=repo, check_labels=not no_labels, check_permissions=not no_permissions
        )

        if not result["success"]:
            raise click.ClickException("Repository validation failed")

    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Repository validation failed")


@repo_group.command(name="setup-labels")
@click.option("--repository", help="Repository in format owner/repo (uses config if not specified)")
@click.pass_context
def repo_setup_labels(ctx: click.Context, repository: Optional[str]) -> None:
    """Set up DevFlow standard labels in repository."""
    from devflow.cli.commands.repo import setup_repository_labels

    try:
        owner = None
        repo = None

        if repository:
            if "/" not in repository:
                raise click.BadParameter("Repository must be in format: owner/repo")
            owner, repo = repository.split("/", 1)

        result = setup_repository_labels(owner=owner, repo=repo)

        console.print(f"\n[green]Labels configured for {result['owner']}/{result['repo']}![/green]")

    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Label setup failed")


@cli.group(name="autofix")
@click.pass_context
def autofix_group(ctx: click.Context) -> None:
    """Auto-fix CI failures and review feedback."""
    pass


@autofix_group.command(name="pr")
@click.argument("pr_number", type=int)
@click.option("--max-iterations", default=3, help="Maximum auto-fix iterations", show_default=True)
@click.option(
    "--working-dir",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    help="Working directory (default: current directory)",
)
@click.option("--dry-run", is_flag=True, help="Show what would be fixed without making changes")
@click.pass_context
def autofix_pr(
    ctx: click.Context, pr_number: int, max_iterations: int, working_dir: str, dry_run: bool
) -> None:
    """Auto-fix issues for a specific pull request."""
    from devflow.cli.commands.autofix import pr as autofix_pr_cmd

    try:
        autofix_pr_cmd.callback(pr_number, max_iterations, working_dir, dry_run)
    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Auto-fix failed")


@autofix_group.command(name="monitor")
@click.option(
    "--working-dir",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    help="Working directory (default: current directory)",
)
@click.option("--max-prs", default=10, help="Maximum number of PRs to check", show_default=True)
@click.pass_context
def autofix_monitor(ctx: click.Context, working_dir: str, max_prs: int) -> None:
    """Monitor open PRs and auto-fix any CI failures."""
    from devflow.cli.commands.autofix import monitor as autofix_monitor_cmd

    try:
        autofix_monitor_cmd.callback(working_dir, max_prs)
    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Auto-fix monitoring failed")


@autofix_group.command(name="status")
@click.argument("pr_number", type=int)
@click.option(
    "--working-dir",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    help="Working directory (default: current directory)",
)
@click.pass_context
def autofix_status(ctx: click.Context, pr_number: int, working_dir: str) -> None:
    """Check auto-fix status for a pull request."""
    from devflow.cli.commands.autofix import status as autofix_status_cmd

    try:
        autofix_status_cmd.callback(pr_number, working_dir)
    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Auto-fix status check failed")


@cli.command()
@click.argument("pr_number", type=int)
@click.option("--max-cycles", default=10, help="Maximum monitoring cycles", show_default=True)
@click.option(
    "--working-dir",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    help="Working directory (default: current directory)",
)
@click.pass_context
def monitor(ctx: click.Context, pr_number: int, max_cycles: int, working_dir: str) -> None:
    """Start continuous monitoring for a specific PR.

    This command starts the continuous monitoring system that:
    - Watches CI status continuously
    - Applies auto-fixes when CI fails
    - Posts validation status when complete
    - Marks as ready-for-human when all tests pass

    Examples:
        devflow monitor 8
        devflow monitor 8 --max-cycles 5
    """
    from devflow.cli.commands.monitor import pr as monitor_pr_cmd

    try:
        monitor_pr_cmd.callback(pr_number, max_cycles, working_dir)
    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Continuous monitoring failed")


@cli.command()
@click.pass_context
def presets(ctx: click.Context) -> None:
    """Show available maturity level presets.

    This command displays all available project maturity presets
    with their configuration details.
    """
    console.print("[bold blue]DevFlow Maturity Presets[/bold blue]")

    try:
        presets_data = MaturityConfig.list_presets()

        for level, preset in presets_data.items():
            # Create panel for each preset
            content = Text()
            content.append(f"{preset['description']}\n\n", style="italic")
            content.append(
                f"Coverage: {preset['min_coverage']}% min, {preset['coverage_goal']}% goal\n"
            )
            content.append(f"Security: {preset['security_level']}\n")
            content.append(f"Review: {preset['review_strictness']}\n")
            content.append(
                f"Breaking changes: {'allowed' if preset['allow_breaking_changes'] else 'forbidden'}\n"
            )
            content.append(
                f"Changelog: {'required' if preset['require_changelog'] else 'optional'}\n"
            )
            content.append(
                f"Migration guide: {'required' if preset['require_migration_guide'] else 'optional'}"
            )

            panel = Panel(
                content,
                title=f"[bold]{level.title()}[/bold]",
                border_style="blue" if level == "early_stage" else "dim",
            )
            console.print(panel)

    except Exception as e:
        handle_error(e, ctx.obj.get("debug", False))
        raise click.ClickException("Preset listing failed")


def main() -> None:
    """Main entry point for the CLI."""
    try:
        cli(standalone_mode=False)
    except click.ClickException as e:
        e.show()
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Unexpected error:[/red] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

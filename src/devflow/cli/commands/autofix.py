"""Auto-fix command implementation for DevFlow CLI."""

import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from devflow.adapters.github.client import GitHubPlatformAdapter
from devflow.agents.claude import ClaudeAgentProvider
from devflow.core.auto_fix import AutoFixEngine
from devflow.core.config import ProjectConfig
from devflow.exceptions import ConfigurationError, PlatformError

console = Console()
logger = logging.getLogger(__name__)


@click.group()
def autofix():
    """Auto-fix CI failures and review feedback."""
    pass


@autofix.command()
@click.argument('pr_number', type=int)
@click.option(
    '--max-iterations',
    default=3,
    help='Maximum auto-fix iterations',
    show_default=True
)
@click.option(
    '--working-dir',
    type=click.Path(exists=True, file_okay=False),
    default='.',
    help='Working directory (default: current directory)'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='Show what would be fixed without making changes'
)
def pr(pr_number: int, max_iterations: int, working_dir: str, dry_run: bool):
    """Auto-fix issues for a specific pull request.

    This command analyzes CI failures and review feedback for a pull request
    and automatically applies fixes using AI.

    Examples:
        devflow autofix pr 123
        devflow autofix pr 123 --max-iterations 5
        devflow autofix pr 123 --dry-run
    """
    try:
        console.print(f"[bold blue]🔧 Auto-fixing PR #{pr_number}[/bold blue]")

        if dry_run:
            console.print("[yellow]🏃‍♂️ DRY RUN - No changes will be made[/yellow]")

        # Load configuration
        config = _load_config(working_dir)

        # Initialize platform adapter
        platform_adapter = _create_platform_adapter(config)

        # Initialize auto-fix engine
        auto_fix_engine = _create_auto_fix_engine(platform_adapter, config, working_dir)

        if dry_run:
            # For dry run, just detect feedback items
            console.print("[blue]Detecting feedback items...[/blue]")
            feedback_items = auto_fix_engine._detect_all_feedback(pr_number)

            if not feedback_items:
                console.print("[green]✓ No issues detected that need auto-fixing[/green]")
                return

            console.print(f"[yellow]Found {len(feedback_items)} issues to fix:[/yellow]")

            table = Table()
            table.add_column("Type", style="cyan")
            table.add_column("Priority", style="yellow")
            table.add_column("Title", style="green")
            table.add_column("File", style="blue")

            for item in feedback_items:
                table.add_row(
                    item.type.value,
                    item.priority.value,
                    item.title,
                    item.file_path or "N/A"
                )

            console.print(table)
            console.print(f"[blue]Would run {max_iterations} auto-fix iterations[/blue]")

        else:
            # Run actual auto-fix
            result = auto_fix_engine.run_auto_fix_cycle(pr_number, max_iterations)

            if result.success:
                console.print(f"[green]✅ Auto-fix completed successfully![/green]")
                console.print(f"Applied {len(result.fixes_applied)} fixes")
                console.print(f"Modified {len(result.files_modified)} files")

                if result.fixes_applied:
                    console.print("\n[bold]Fixes applied:[/bold]")
                    for fix in result.fixes_applied:
                        console.print(f"  • {fix}")

                if result.files_modified:
                    console.print("\n[bold]Files modified:[/bold]")
                    for file_path in result.files_modified:
                        console.print(f"  • {file_path}")

            else:
                console.print(f"[red]❌ Auto-fix failed: {result.error_message}[/red]")

                if result.fixes_applied:
                    console.print(f"[yellow]Partial fixes applied: {len(result.fixes_applied)}[/yellow]")
                    for fix in result.fixes_applied:
                        console.print(f"  • {fix}")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise click.ClickException(str(e))


@autofix.command()
@click.option(
    '--working-dir',
    type=click.Path(exists=True, file_okay=False),
    default='.',
    help='Working directory (default: current directory)'
)
@click.option(
    '--max-prs',
    default=10,
    help='Maximum number of PRs to check',
    show_default=True
)
def monitor(working_dir: str, max_prs: int):
    """Monitor open PRs and auto-fix any CI failures.

    This command continuously monitors open pull requests for CI failures
    and automatically applies fixes when detected.

    Examples:
        devflow autofix monitor
        devflow autofix monitor --max-prs 5
    """
    try:
        console.print("[bold blue]🔍 Monitoring PRs for auto-fix opportunities[/bold blue]")

        # Load configuration
        config = _load_config(working_dir)

        # Initialize platform adapter
        platform_adapter = _create_platform_adapter(config)

        # Get open PRs
        console.print("[blue]Fetching open pull requests...[/blue]")

        prs = platform_adapter.list_pull_requests(
            owner=config.repo_owner,
            repo=config.repo_name,
            limit=max_prs
        )

        if not prs:
            console.print("[green]No open pull requests found[/green]")
            return

        console.print(f"[blue]Found {len(prs)} open pull requests[/blue]")

        # Initialize auto-fix engine
        auto_fix_engine = _create_auto_fix_engine(platform_adapter, config, working_dir)

        results = []

        for pr in prs:
            console.print(f"\n[cyan]Checking PR #{pr.number}: {pr.title}[/cyan]")

            try:
                # Quick check for feedback items
                feedback_items = auto_fix_engine._detect_all_feedback(pr.number)

                if not feedback_items:
                    console.print(f"  [green]✓ No issues found[/green]")
                    results.append({
                        'pr': pr.number,
                        'status': 'clean',
                        'fixes': 0
                    })
                    continue

                console.print(f"  [yellow]Found {len(feedback_items)} issues[/yellow]")

                # Run auto-fix
                result = auto_fix_engine.run_auto_fix_cycle(pr.number, max_iterations=2)

                if result.success:
                    console.print(f"  [green]✅ Applied {len(result.fixes_applied)} fixes[/green]")
                    results.append({
                        'pr': pr.number,
                        'status': 'fixed',
                        'fixes': len(result.fixes_applied)
                    })
                else:
                    console.print(f"  [red]❌ Auto-fix failed[/red]")
                    results.append({
                        'pr': pr.number,
                        'status': 'failed',
                        'fixes': 0
                    })

            except Exception as e:
                console.print(f"  [red]Error processing PR: {str(e)}[/red]")
                results.append({
                    'pr': pr.number,
                    'status': 'error',
                    'fixes': 0
                })

        # Summary
        console.print(f"\n[bold]Summary:[/bold]")

        table = Table()
        table.add_column("PR #", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Fixes Applied", style="yellow", justify="right")

        for result in results:
            status_color = {
                'clean': 'green',
                'fixed': 'green',
                'failed': 'red',
                'error': 'red'
            }.get(result['status'], 'yellow')

            table.add_row(
                str(result['pr']),
                f"[{status_color}]{result['status']}[/{status_color}]",
                str(result['fixes'])
            )

        console.print(table)

        total_fixes = sum(r['fixes'] for r in results)
        console.print(f"\n[green]Total fixes applied: {total_fixes}[/green]")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise click.ClickException(str(e))


@autofix.command()
@click.argument('pr_number', type=int)
@click.option(
    '--working-dir',
    type=click.Path(exists=True, file_okay=False),
    default='.',
    help='Working directory (default: current directory)'
)
def status(pr_number: int, working_dir: str):
    """Check auto-fix status for a pull request.

    Shows what issues would be auto-fixed without making changes.

    Examples:
        devflow autofix status 123
    """
    try:
        console.print(f"[bold blue]🔍 Checking auto-fix status for PR #{pr_number}[/bold blue]")

        # Load configuration
        config = _load_config(working_dir)

        # Initialize platform adapter
        platform_adapter = _create_platform_adapter(config)

        # Initialize auto-fix engine
        auto_fix_engine = _create_auto_fix_engine(platform_adapter, config, working_dir)

        # Detect feedback items
        console.print("[blue]Analyzing feedback and CI failures...[/blue]")
        feedback_items = auto_fix_engine._detect_all_feedback(pr_number)

        if not feedback_items:
            console.print("[green]✅ No issues detected that need auto-fixing[/green]")
            return

        console.print(f"[yellow]Found {len(feedback_items)} issues that can be auto-fixed:[/yellow]")

        # Group by type and priority
        grouped = {}
        for item in feedback_items:
            key = f"{item.type.value}|{item.priority.value}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(item)

        for group_key, items in grouped.items():
            type_val, priority_val = group_key.split('|')
            console.print(f"\n[bold]{type_val.title()} - {priority_val.title()} Priority ({len(items)} items):[/bold]")

            for item in items:
                location = f" [{item.file_path}:{item.line_number}]" if item.file_path and item.line_number else ""
                console.print(f"  • {item.title}{location}")
                if item.description:
                    console.print(f"    {item.description[:100]}{'...' if len(item.description) > 100 else ''}")
                if item.suggestion:
                    console.print(f"    💡 {item.suggestion}")

        console.print(f"\n[blue]💡 Run 'devflow autofix pr {pr_number}' to apply these fixes[/blue]")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise click.ClickException(str(e))


def _load_config(working_dir: str) -> ProjectConfig:
    """Load project configuration."""
    project_root = Path(working_dir).absolute()
    config_file = project_root / "devflow.yaml"

    if not config_file.exists():
        raise ConfigurationError(f"DevFlow configuration not found: {config_file}")

    return ProjectConfig.from_file(config_file)


def _create_platform_adapter(config: ProjectConfig) -> GitHubPlatformAdapter:
    """Create and validate platform adapter."""
    adapter_config = {
        "repo_owner": config.repo_owner,
        "repo_name": config.repo_name
    }

    adapter = GitHubPlatformAdapter(adapter_config)

    if not adapter.validate_connection():
        raise PlatformError("Failed to connect to GitHub", platform="github")

    return adapter


def _create_auto_fix_engine(
    platform_adapter: GitHubPlatformAdapter,
    config: ProjectConfig,
    working_dir: str
) -> AutoFixEngine:
    """Create auto-fix engine with proper configuration."""
    # Create a mock agent for now - in real usage would use proper agent coordinator
    agent_config = {
        "model": config.agents.claude_model,
        "max_tokens": 8192,
        "temperature": 0.1
    }

    claude_agent = ClaudeAgentProvider(agent_config)

    return AutoFixEngine(
        platform_adapter=platform_adapter,
        agent_provider=claude_agent,
        working_directory=working_dir
    )
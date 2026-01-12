"""Continuous PR monitoring CLI commands."""

import logging
from pathlib import Path

import click
from rich.console import Console

from devflow.adapters.github.client import GitHubPlatformAdapter
from devflow.agents.claude import ClaudeAgentProvider
from devflow.core.auto_fix import AutoFixEngine
from devflow.core.config import ProjectConfig
from devflow.core.continuous_monitor import ContinuousPRMonitor
from devflow.exceptions import ConfigurationError, PlatformError

console = Console()
logger = logging.getLogger(__name__)


@click.group()
def monitor():
    """Continuous PR monitoring and auto-fix."""
    pass


@monitor.command()
@click.argument("pr_number", type=int)
@click.option("--max-cycles", default=10, help="Maximum monitoring cycles", show_default=True)
@click.option(
    "--working-dir",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    help="Working directory (default: current directory)",
)
def pr(pr_number: int, max_cycles: int, working_dir: str):
    """Start continuous monitoring for a specific PR.

    This command starts the continuous monitoring system that:
    - Watches CI status continuously
    - Applies auto-fixes when CI fails
    - Posts validation status when complete
    - Marks as ready-for-human when all tests pass

    Examples:
        devflow monitor pr 8
        devflow monitor pr 8 --max-cycles 5
    """
    try:
        console.print(
            f"[bold blue]🔍 Starting continuous monitoring for PR #{pr_number}[/bold blue]"
        )

        # Load configuration
        config = _load_config(working_dir)

        # Initialize adapters
        platform_adapter = _create_platform_adapter(config)
        auto_fix_engine = _create_auto_fix_engine(platform_adapter, config, working_dir)

        # Create continuous monitor
        monitor_system = ContinuousPRMonitor(
            platform_adapter=platform_adapter, auto_fix_engine=auto_fix_engine, check_interval=300
        )

        # Start monitoring
        monitor_system.start_monitoring(pr_number)

        console.print("[green]✓ Monitoring started[/green]")
        console.print(f"[blue]Running up to {max_cycles} monitoring cycles...[/blue]")

        # Run monitoring cycles
        results = monitor_system.run_monitoring_cycle(max_cycles)

        # Display results
        console.print("\n[bold]📊 Monitoring Results:[/bold]")

        for cycle_name, cycle_results in results.items():
            console.print(f"\n[cyan]{cycle_name.replace('_', ' ').title()}:[/cyan]")

            for pr_num, pr_result in cycle_results.items():
                status = pr_result.get("status", "unknown")

                if status == "ready_for_human":
                    console.print(f"  PR #{pr_num}: [green]✅ Ready for human review[/green]")
                elif status == "auto_fix_applied":
                    fixes = len(pr_result.get("fixes_applied", []))
                    console.print(f"  PR #{pr_num}: [yellow]🔧 Applied {fixes} auto-fixes[/yellow]")
                elif status == "needs_human_intervention":
                    console.print(f"  PR #{pr_num}: [red]⚠️ Needs human intervention[/red]")
                else:
                    console.print(f"  PR #{pr_num}: [blue]ℹ️ {status}[/blue]")

        console.print(f"\n[green]✓ Continuous monitoring completed for PR #{pr_number}[/green]")

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
    adapter_config = {"repo_owner": config.repo_owner, "repo_name": config.repo_name}

    adapter = GitHubPlatformAdapter(adapter_config)

    if not adapter.validate_connection():
        raise PlatformError("Failed to connect to GitHub", platform="github")

    return adapter


def _create_auto_fix_engine(
    platform_adapter: GitHubPlatformAdapter, config: ProjectConfig, working_dir: str
) -> AutoFixEngine:
    """Create auto-fix engine with proper configuration."""
    # Use real Claude agent for production monitoring
    from devflow.agents.claude import ClaudeAgentProvider

    agent_config = {"model": config.agents.claude_model, "max_tokens": 4000, "temperature": 0.1}

    claude_agent = ClaudeAgentProvider(agent_config)

    return AutoFixEngine(
        platform_adapter=platform_adapter,
        agent_provider=claude_agent,
        working_directory=working_dir,
    )

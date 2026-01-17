"""Issue processing command."""

import logging
from typing import Any, Dict

from rich.console import Console

from devflow.adapters.git.basic import BasicGitAdapter
from devflow.adapters.github.client import GitHubPlatformAdapter
from devflow.agents.base import MultiAgentCoordinator
from devflow.agents.claude import ClaudeAgentProvider
from devflow.agents.mock import MockAgentProvider
from devflow.core.config import ProjectConfig
from devflow.core.state_manager import StateManager
from devflow.core.workflow_engine import WorkflowEngine
from devflow.exceptions import AgentError, PlatformError, WorkflowError

console = Console()
logger = logging.getLogger(__name__)


def process_issue(
    config: ProjectConfig, issue_number: int, auto_mode: bool = False, dry_run: bool = False
) -> Dict[str, Any]:
    """Process an issue through the DevFlow pipeline.

    Args:
        config: Project configuration
        issue_number: Issue number to process
        auto_mode: Run in fully automated mode
        dry_run: Show what would be done without making changes

    Returns:
        Processing results

    Raises:
        WorkflowError: If processing fails
    """
    console.print(f"\n[bold]🚀 Starting DevFlow automation for issue #{issue_number}[/bold]")

    try:
        # Initialize platform adapter (use basic git adapter for dry-run mode)
        platform_adapter = _create_platform_adapter(config, dry_run=dry_run)

        # Initialize agents (skip validation in dry-run mode)
        agent_coordinator = _create_agent_coordinator(config, skip_validation=dry_run)

        # Initialize state manager (disabled for now due to threading issues)
        # TODO: Fix StateManager threading deadlock in future release
        state_manager = None  # StateManager(config)

        # Create workflow engine
        workflow_engine = WorkflowEngine(
            config=config,
            platform_adapter=platform_adapter,
            agent_coordinator=agent_coordinator,
            state_manager=state_manager,
        )

        # Validate environment before processing
        console.print("\n[cyan]Validating environment...[/cyan]")
        if not workflow_engine.validate_environment():
            raise WorkflowError(
                "Environment validation failed - fix issues before proceeding",
                workflow_id=f"issue-{issue_number}",
            )

        # Process the issue
        result = workflow_engine.process_issue(
            issue_number=issue_number, auto_mode=auto_mode, dry_run=dry_run
        )

        console.print(f"\n[green]✓ Workflow completed for issue #{issue_number}[/green]")
        return result

    except (AgentError, PlatformError) as e:
        logger.error(f"Service error during processing: {str(e)}")
        raise WorkflowError(f"Service error: {str(e)}", workflow_id=f"issue-{issue_number}") from e

    except Exception as e:
        logger.error(f"Unexpected error during processing: {str(e)}")
        raise WorkflowError(
            f"Failed to process issue #{issue_number}: {str(e)}",
            workflow_id=f"issue-{issue_number}",
        ) from e


def _create_platform_adapter(config: ProjectConfig, dry_run: bool = False):
    """Create platform adapter based on configuration.

    Args:
        config: Project configuration
        dry_run: Use basic git adapter for dry-run mode

    Returns:
        Configured platform adapter

    Raises:
        PlatformError: If adapter creation fails
    """
    try:
        adapter_config = {
            "repo_owner": config.repo_owner,
            "repo_name": config.repo_name,
            "project_root": str(config.project_root),
        }

        if dry_run:
            # Use basic git adapter for dry-run mode
            console.print("[yellow]🧪 Using basic git adapter for dry-run mode[/yellow]")
            adapter = BasicGitAdapter(adapter_config)
        else:
            # Use full GitHub adapter for real operations
            adapter = GitHubPlatformAdapter(adapter_config)

        # Validate connection
        if not adapter.validate_connection():
            raise PlatformError(
                f"Failed to connect to repository: {config.repo_owner}/{config.repo_name}",
                platform=adapter.name,
            )

        console.print(f"[green]✓ {adapter.display_name} adapter initialized[/green]")
        return adapter

    except Exception as e:
        raise PlatformError(
            f"Failed to create platform adapter: {str(e)}", platform="unknown"
        ) from e


def _create_agent_coordinator(
    config: ProjectConfig, skip_validation: bool = False
) -> MultiAgentCoordinator:
    """Create agent coordinator with configured agents.

    Args:
        config: Project configuration
        skip_validation: Use mock agents for dry-run mode

    Returns:
        Configured agent coordinator

    Raises:
        AgentError: If agent creation fails
    """
    try:
        agents = []

        if skip_validation:
            # Use mock agent for dry-run mode
            console.print("[yellow]🧪 Using mock agent for dry-run mode[/yellow]")
            mock_config = {"mock_mode": True, "simulate_failures": False}
            try:
                mock_agent = MockAgentProvider(mock_config)
                agents.append(mock_agent)
                console.print("[yellow]✓ Mock agent initialized[/yellow]")
            except Exception as e:
                console.print(f"[red]✗ Failed to initialize mock agent: {e}[/red]")
                raise AgentError(f"Failed to initialize mock agent: {str(e)}")

        else:
            # Add Claude agent if configured
            if config.agents.primary == "claude" or "claude" in config.agents.review_sources:
                claude_config = {"use_claude_cli": True, "model": config.agents.claude_model}

                try:
                    claude_agent = ClaudeAgentProvider(claude_config)
                    agents.append(claude_agent)
                    console.print("[green]✓ Claude agent initialized[/green]")
                except Exception as e:
                    console.print(f"[yellow]⚠ Failed to initialize Claude agent: {e}[/yellow]")

            if not agents:
                raise AgentError(
                    "No AI agents could be initialized. Check your configuration and service availability.",
                    operation="agent_initialization",
                )

        return MultiAgentCoordinator(agents)

    except Exception as e:
        if isinstance(e, AgentError):
            raise
        raise AgentError(
            f"Failed to create agent coordinator: {str(e)}", operation="coordinator_creation"
        ) from e

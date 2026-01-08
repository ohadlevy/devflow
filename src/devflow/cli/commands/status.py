"""Status command implementation."""

from datetime import datetime
from typing import Dict, Any

from devflow.core.config import ProjectConfig


def show_status(config: ProjectConfig, format: str = "table") -> Dict[str, Any]:
    """Show DevFlow project status.

    Args:
        config: Project configuration
        format: Output format (table, json, yaml)

    Returns:
        Status information
    """
    # Gather project information
    project_info = {
        'name': config.project_name,
        'maturity_level': config.maturity_level.value if hasattr(config.maturity_level, 'value') else str(config.maturity_level),
        'platform': config.platforms.primary,
        'repository': f"{config.repo_owner}/{config.repo_name}" if config.repo_owner and config.repo_name else "Not configured"
    }

    # Get actual workflow status from running processes
    workflows = []

    # Check for actual running DevFlow processes and active worktrees
    try:
        import subprocess

        # Check for active git worktrees with devflow pattern
        result = subprocess.run(['git', 'worktree', 'list'],
                              capture_output=True, text=True,
                              cwd=config.project_root)

        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if '/tmp/devflow-worktree-' in line:
                    # Extract issue number from worktree path
                    parts = line.split('/tmp/devflow-worktree-')
                    if len(parts) > 1:
                        issue_num = parts[1].split()[0]
                        try:
                            issue_number = int(issue_num)
                            workflows.append({
                                'issue_number': issue_number,
                                'status': 'in_progress',
                                'stage': 'implementation',
                                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                        except ValueError:
                            pass  # Skip invalid issue numbers
    except Exception:
        pass  # Fallback to empty list if git commands fail

    # If no active workflows found, show a helpful message
    if not workflows:
        workflows = [{
            'issue_number': 'None',
            'status': 'No active workflows',
            'stage': 'Ready for new issues',
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }]

    # Compile status data
    status_data = {
        'project': project_info,
        'workflows': workflows,
        'statistics': {
            'total_workflows': len(workflows),
            'active_workflows': len([w for w in workflows if w['status'] == 'in_progress']),
            'completed_today': 0  # TODO: Calculate from actual data
        },
        'configuration': {
            'maturity_preset': config.maturity_preset.__dict__ if hasattr(config, 'maturity_preset') else {},
            'agent_config': config.agents.model_dump() if hasattr(config.agents, 'model_dump') else config.agents.__dict__,
            'platform_config': config.platforms.model_dump() if hasattr(config.platforms, 'model_dump') else config.platforms.__dict__
        }
    }

    return status_data
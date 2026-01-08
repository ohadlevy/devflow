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
        'maturity_level': config.maturity_level.value,
        'platform': config.platforms.primary,
        'repository': f"{config.repo_owner}/{config.repo_name}" if config.repo_owner and config.repo_name else "Not configured"
    }

    # TODO: Get actual workflow status from state manager
    # For now, return mock data
    workflows = [
        {
            'issue_number': 123,
            'status': 'in_progress',
            'stage': 'implementation',
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'issue_number': 124,
            'status': 'review',
            'stage': 'code_review',
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    ]

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
            'agent_config': config.agents.dict(),
            'platform_config': config.platforms.dict()
        }
    }

    return status_data
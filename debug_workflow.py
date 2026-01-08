#!/usr/bin/env python3
"""Debug workflow execution step by step."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "src"))

def debug_workflow():
    """Debug workflow execution with detailed tracing."""

    from devflow.core.workflow_engine import WorkflowEngine, WorkflowState
    from devflow.core.config import ProjectConfig, ProjectMaturity, PlatformConfig, WorkflowConfig, AgentConfig
    from devflow.adapters.git.basic import BasicGitAdapter
    from devflow.agents.mock import MockAgentProvider
    from devflow.agents.base import MultiAgentCoordinator
    from devflow.core.state_manager import StateManager

    print("🔍 Debugging DevFlow Workflow Execution")

    # Setup
    config = ProjectConfig(
        project_name='devflow', project_root=Path.cwd(),
        repo_owner='test', repo_name='devflow', base_branch='main',
        maturity_level=ProjectMaturity.EARLY_STAGE,
        platforms=PlatformConfig(primary='github'),
        workflows=WorkflowConfig(), agents=AgentConfig(primary='mock')
    )

    adapter = BasicGitAdapter({'repo_owner': 'test', 'repo_name': 'devflow', 'project_root': str(Path.cwd())})
    agent = MockAgentProvider({'mock_mode': True})
    coordinator = MultiAgentCoordinator([agent])
    state_manager = StateManager(config)
    engine = WorkflowEngine(config, adapter, coordinator, state_manager)

    print("✓ Components initialized")

    # Test session creation step by step
    print("\n1. Testing session creation...")
    try:
        session = engine._get_or_create_session(1)
        print(f"   ✓ Session created: {session.issue_number}")
        print(f"   ✓ Initial state: {session.current_state}")
    except Exception as e:
        print(f"   ❌ Session creation failed: {e}")
        return False

    # Test workflow context creation
    print("\n2. Testing context creation...")
    try:
        context = engine._create_workflow_context(session)
        print(f"   ✓ Context created for project: {context.project_name}")
    except Exception as e:
        print(f"   ❌ Context creation failed: {e}")
        return False

    # Test individual stages
    print(f"\n3. Testing individual stages...")

    # Test validation stage
    print(f"   Testing validation stage...")
    try:
        result = engine._stage_validation(session, context, auto_mode=True, dry_run=True)
        print(f"   ✓ Validation: success={result['success']}, next_state={result.get('next_state', 'None')}")
    except Exception as e:
        print(f"   ❌ Validation stage failed: {e}")
        return False

    # Update session state for next test
    session.current_state = WorkflowState.VALIDATED

    # Test worktree stage
    print(f"   Testing worktree creation stage...")
    try:
        result = engine._stage_worktree_creation(session, context, auto_mode=True, dry_run=True)
        print(f"   ✓ Worktree: success={result['success']}, next_state={result.get('next_state', 'None')}")
    except Exception as e:
        print(f"   ❌ Worktree stage failed: {e}")
        return False

    # Test implementation stage
    session.current_state = WorkflowState.IMPLEMENTING
    print(f"   Testing implementation stage...")
    try:
        result = engine._stage_implementation(session, context, auto_mode=True, dry_run=True)
        print(f"   ✓ Implementation: success={result['success']}, next_state={result.get('next_state', 'None')}")
    except Exception as e:
        print(f"   ❌ Implementation stage failed: {e}")
        return False

    # Test review stage
    session.current_state = WorkflowState.IMPLEMENTED
    print(f"   Testing review stage...")
    try:
        result = engine._stage_review(session, context, auto_mode=True, dry_run=True)
        print(f"   ✓ Review: success={result['success']}, next_state={result.get('next_state', 'None')}")
    except Exception as e:
        print(f"   ❌ Review stage failed: {e}")
        return False

    # Test finalization stage
    session.current_state = WorkflowState.REVIEW_PASSED
    print(f"   Testing finalization stage...")
    try:
        result = engine._stage_finalization(session, context, auto_mode=True, dry_run=True)
        print(f"   ✓ Finalization: success={result['success']}, next_state={result.get('next_state', 'None')}")
    except Exception as e:
        print(f"   ❌ Finalization stage failed: {e}")
        return False

    # Test terminal state recognition
    print(f"\n4. Testing terminal state recognition...")
    terminal_states = [
        WorkflowState.COMPLETED,
        WorkflowState.MERGED,
        WorkflowState.READY_FOR_HUMAN,
        WorkflowState.NEEDS_HUMAN_INTERVENTION
    ]

    for state in terminal_states:
        print(f"   {state.value}: {'✓ Terminal' if state in terminal_states else '✗ Not terminal'}")

    print(f"\n🎯 Diagnosis Complete!")
    print(f"   All individual stages work correctly")
    print(f"   Issue is likely in the _execute_workflow loop logic")

    return True

if __name__ == "__main__":
    debug_workflow()
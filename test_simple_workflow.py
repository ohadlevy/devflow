#!/usr/bin/env python3
"""
Simple workflow test to debug step by step.
"""

import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_simple_workflow():
    """Test simple workflow components step by step."""
    print("🔬 Testing Simple Workflow Components...")

    try:
        # Import components
        from devflow.core.config import ProjectConfig, ProjectMaturity, PlatformConfig, WorkflowConfig, AgentConfig
        from devflow.adapters.git.basic import BasicGitAdapter
        from devflow.agents.mock import MockAgentProvider
        from devflow.agents.base import MultiAgentCoordinator
        from devflow.core.state_manager import StateManager
        from devflow.core.workflow_engine import WorkflowEngine

        print("✓ All imports successful")

        # Create test configuration
        config = ProjectConfig(
            project_name="devflow-test",
            project_root=Path.cwd(),
            repo_owner="test-owner",
            repo_name="test-repo",
            base_branch="main",
            maturity_level=ProjectMaturity.EARLY_STAGE,
            platforms=PlatformConfig(primary="github"),
            workflows=WorkflowConfig(),
            agents=AgentConfig(primary="claude", claude_model="claude-3.5-sonnet")
        )
        print("✓ Configuration created")

        # Test basic adapter
        adapter_config = {
            "repo_owner": config.repo_owner,
            "repo_name": config.repo_name,
            "project_root": str(config.project_root)
        }
        adapter = BasicGitAdapter(adapter_config)
        print(f"✓ {adapter.display_name} adapter created")

        # Validate adapter connection
        if adapter.validate_connection():
            print("✓ Adapter connection validated")
        else:
            print("⚠ Adapter connection failed")

        # Test mock agent
        mock_config = {"mock_mode": True, "simulate_failures": False}
        mock_agent = MockAgentProvider(mock_config)
        print(f"✓ {mock_agent.display_name} agent created")

        # Validate mock agent
        if mock_agent.validate_connection():
            print("✓ Mock agent connection validated")
        else:
            print("⚠ Mock agent connection failed")

        # Create agent coordinator
        coordinator = MultiAgentCoordinator([mock_agent])
        print("✓ Agent coordinator created")

        # Create state manager
        state_manager = StateManager(config)
        print("✓ State manager created")

        # Create workflow engine
        workflow_engine = WorkflowEngine(
            config=config,
            platform_adapter=adapter,
            agent_coordinator=coordinator,
            state_manager=state_manager
        )
        print("✓ Workflow engine created")

        # Test environment validation
        print("\n🔍 Testing environment validation...")
        if workflow_engine.validate_environment():
            print("✓ Environment validation passed!")
        else:
            print("❌ Environment validation failed")
            return False

        print("\n🎉 All simple workflow components working!")
        return True

    except Exception as e:
        print(f"❌ Simple workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_simple_workflow()
    sys.exit(0 if success else 1)
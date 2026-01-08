#!/usr/bin/env python3
"""
End-to-end workflow test demonstrating issue processing.

This test shows the complete DevFlow workflow in dry-run mode
without requiring external services.
"""

import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from devflow.core.config import ProjectConfig, ProjectMaturity, PlatformConfig, WorkflowConfig, AgentConfig
from devflow.cli.commands.process import process_issue

def test_workflow_dry_run():
    """Test the complete workflow in dry-run mode."""
    print("🚀 Testing DevFlow Workflow (Dry Run)...")

    try:
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
        print("✓ Test configuration created")

        # Test dry-run workflow processing
        print("\n📋 Starting workflow dry-run for issue #123...")

        result = process_issue(
            config=config,
            issue_number=123,
            auto_mode=True,
            dry_run=True
        )

        # Verify dry-run results
        if result['success']:
            print("✓ Workflow dry-run completed successfully!")
            print(f"  Stages completed: {', '.join(result['stages_completed'])}")
            print(f"  Current state: {result['current_state']}")

            if result.get('pull_request'):
                pr = result['pull_request']
                print(f"  Pull Request: #{pr['number']} ({pr['status']})")
                print(f"  URL: {pr['url']}")
        else:
            print(f"❌ Workflow failed: {result.get('error')}")
            return False

        print("\n🎉 End-to-end workflow test completed!")
        print("DevFlow can successfully orchestrate the complete automation pipeline.")
        return True

    except Exception as e:
        print(f"❌ Workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_workflow_interactive():
    """Test workflow in interactive mode (dry-run)."""
    print("\n🤖 Testing Interactive Workflow Mode...")

    try:
        # Create configuration for interactive mode
        config = ProjectConfig(
            project_name="devflow-interactive",
            project_root=Path.cwd(),
            repo_owner="test-owner",
            repo_name="test-repo",
            base_branch="main",
            maturity_level=ProjectMaturity.STABLE,  # Higher maturity for stricter validation
            platforms=PlatformConfig(primary="github"),
            workflows=WorkflowConfig(),
            agents=AgentConfig(primary="claude", claude_model="claude-3.5-sonnet")
        )

        print("✓ Interactive mode configuration created")

        # Test interactive mode (dry-run)
        result = process_issue(
            config=config,
            issue_number=456,
            auto_mode=False,  # Interactive mode
            dry_run=True      # But still dry-run to avoid prompts
        )

        if result['success']:
            print("✓ Interactive workflow simulation completed!")
            return True
        else:
            print(f"⚠ Interactive workflow had issues: {result.get('error')}")
            return False

    except Exception as e:
        print(f"❌ Interactive workflow test failed: {e}")
        return False

if __name__ == "__main__":
    success1 = test_workflow_dry_run()
    success2 = test_workflow_interactive()

    if success1 and success2:
        print("\n🎊 All workflow tests passed!")
        print("DevFlow automation pipeline is working end-to-end.")
    else:
        print("\n❌ Some workflow tests failed.")

    sys.exit(0 if (success1 and success2) else 1)
# DevFlow - Intelligent Developer Workflow Automation

[![PyPI version](https://badge.fury.io/py/devflow.svg)](https://badge.fury.io/py/devflow)
[![Python Support](https://img.shields.io/pypi/pyversions/devflow.svg)](https://pypi.org/project/devflow/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

DevFlow is a sophisticated developer workflow automation tool that streamlines the entire development lifecycle from issue validation to code review and deployment. With AI-powered assistance and multi-platform support, DevFlow helps teams maintain high code quality while accelerating development velocity.

## 🌟 Key Features

### Intelligent Automation
- **Multi-stage Pipeline**: Automated validation → implementation → review → finalization workflow
- **AI-powered Code Review**: Integration with Claude, GPT, and other AI providers for intelligent code analysis
- **Maturity-based Configuration**: Adapts review standards and requirements based on project maturity (prototype → stable → mature)
- **Context-aware Processing**: Preserves session context for efficient iterative improvements

### Multi-platform Support
- **GitHub Integration**: Full support for issues, pull requests, and GitHub Actions
- **GitLab Support**: Merge requests, CI/CD pipelines, and issue tracking
- **Extensible Platform System**: Plugin architecture for adding new platforms (Bitbucket, Azure DevOps, etc.)

### Advanced Code Review
- **Multi-source Review Merging**: Combines feedback from multiple review sources with intelligent conflict resolution
- **Severity Classification**: Automatically categorizes issues by impact and blocks critical problems
- **Human-AI Collaboration**: Seamlessly handles human reviewer input alongside automated feedback
- **Follow-up Issue Creation**: Automatically creates technical debt issues for non-blocking improvements

### Enterprise-Ready
- **Persistent State Management**: Tracks workflow progress with error recovery and rollback capabilities
- **Git Worktree Management**: Isolated development environments with automatic cleanup
- **Comprehensive Logging**: Detailed audit trails and debugging information
- **Configuration Management**: Hierarchical configuration with environment-specific overrides

## 🚀 Quick Start

### Installation

```bash
# Install from PyPI
pip install devflow

# Or install with all optional dependencies
pip install devflow[dev,docs]

# Verify installation
devflow --version
```

### Initial Setup

```bash
# Initialize DevFlow in your project
cd your-project
devflow init

# Configure your project maturity level and preferences
devflow config set maturity early_stage
devflow config set platforms.primary github

# Validate setup and permissions
devflow validate
```

### Basic Usage

```bash
# Process a specific issue
devflow process --issue 123

# Monitor workflow status
devflow status

# Clean up completed workflows
devflow cleanup --completed
```

## 📖 Documentation

- **[Getting Started Guide](docs/getting-started.md)**: Complete setup and first workflow
- **[Configuration Reference](docs/configuration.md)**: All configuration options and examples
- **[Plugin Development](docs/plugins.md)**: How to create custom adapters and agents
- **[Migration Guide](docs/migration.md)**: Migrating from embedded automation systems
- **[API Reference](docs/api/)**: Complete API documentation

## 🎯 Project Maturity Levels

DevFlow adapts its behavior based on your project's maturity:

| Maturity | Coverage | Review Strictness | Breaking Changes | Use Case |
|----------|----------|------------------|------------------|-----------|
| **Prototype** | 30% | Lenient | Allowed | Proof of concepts, rapid iteration |
| **Early Stage** | 40% | Moderate | Allowed | Growing codebase, small teams |
| **Stable** | 70% | Strict | With notice | Production systems, careful evolution |
| **Mature** | 85% | Very strict | Forbidden | Wide adoption, stable APIs |

## 🔧 Configuration Example

```yaml
# devflow.yaml
project:
  name: "my-awesome-project"
  maturity_level: "stable"

platforms:
  primary: "github"
  issue_tracking: "github"
  git_provider: "github"

agents:
  primary: "claude"
  review_sources: ["claude", "copilot"]

workflows:
  validation:
    enabled: true
    timeout: 180
    refinement_enabled: true

  implementation:
    max_iterations: 3
    commit_strategy: "squash"
    context_preservation: true

  review:
    multi_source_merging: true
    severity_classification: "maturity_based"
    human_override_detection: true
    followup_issue_creation: true
```

## 🤖 AI Agent Integration

DevFlow supports multiple AI providers through a plugin system:

```python
# Custom AI agent plugin
from devflow.agents.base import AgentProvider

class CustomAIAgent(AgentProvider):
    def validate_issue(self, issue: Issue) -> ValidationResult:
        # Custom validation logic
        pass

    def implement_changes(self, context: WorkflowContext) -> ImplementationResult:
        # Custom implementation logic
        pass
```

## 🌍 Multi-platform Support

```python
# Custom platform adapter
from devflow.adapters.base import PlatformAdapter

class CustomPlatformAdapter(PlatformAdapter):
    def create_pull_request(self, changes: Changes) -> PullRequest:
        # Platform-specific PR creation
        pass

    def get_review_status(self, pr_id: str) -> ReviewStatus:
        # Platform-specific review handling
        pass
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Quick Development Setup

```bash
# Clone the repository
git clone https://github.com/devflow-org/devflow.git
cd devflow

# Set up development environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run linting
black src/ tests/
isort src/ tests/
flake8 src/ tests/
mypy src/
```

## 📊 Workflow Analytics

DevFlow tracks workflow performance and provides insights:

- **Success Rates**: Track automation effectiveness across different issue types
- **Review Accuracy**: Monitor AI agent performance and improvement over time
- **Bottleneck Detection**: Identify workflow stages that need optimization
- **Quality Metrics**: Measure code quality trends and technical debt

## 🔒 Security & Privacy

- **Local Processing**: Sensitive code analysis can be performed locally
- **Configurable Data Sharing**: Control what information is shared with external services
- **Audit Logging**: Complete audit trail of all automation actions
- **Permission Management**: Fine-grained control over repository and platform access

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by modern DevOps practices and AI-assisted development
- Built with love by the developer community for the developer community
- Special thanks to all contributors and early adopters

---

**Made with ❤️ for developers who love automation**
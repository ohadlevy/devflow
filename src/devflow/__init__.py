"""DevFlow - Intelligent Developer Workflow Automation.

A sophisticated automation tool that streamlines the development lifecycle
with AI-powered assistance and multi-platform support.
"""

__version__ = "0.1.0"
__author__ = "DevFlow Contributors"
__email__ = "devflow@example.com"
__license__ = "MIT"

from devflow.core.config import ProjectConfig
from devflow.exceptions import DevFlowError, ValidationError

__all__ = [
    "__version__",
    "ProjectConfig",
    "DevFlowError",
    "ValidationError",
]

"""Mission Control UX - Beautiful dashboard for multi-agent workflows.

Provides real-time visibility into multiple agents working on an issue
with context sharing and parallel coordination.
"""

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich.live import Live


class AgentStatus(str, Enum):
    """Agent execution status."""
    PENDING = "pending"
    STARTING = "starting"
    ANALYZING = "analyzing"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentProgress:
    """Progress tracking for individual agents."""
    agent_id: str
    agent_type: str
    display_name: str
    emoji: str
    status: AgentStatus
    progress_pct: int
    current_task: str
    files_processed: List[str]
    context_shared: bool
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def duration(self) -> str:
        """Get formatted duration."""
        if not self.started_at:
            return "Not started"

        end_time = self.completed_at or datetime.now()
        duration = end_time - self.started_at

        if duration.total_seconds() < 60:
            return f"{duration.total_seconds():.1f}s"
        else:
            return f"{duration.total_seconds() / 60:.1f}m"

    @property
    def status_color(self) -> str:
        """Get color for status display."""
        colors = {
            AgentStatus.PENDING: "dim",
            AgentStatus.STARTING: "yellow",
            AgentStatus.ANALYZING: "blue",
            AgentStatus.IMPLEMENTING: "green",
            AgentStatus.TESTING: "cyan",
            AgentStatus.COMPLETING: "magenta",
            AgentStatus.COMPLETED: "bright_green",
            AgentStatus.FAILED: "red"
        }
        return colors.get(self.status, "white")


class MissionControl:
    """Mission Control dashboard for multi-agent workflows."""

    def __init__(self, issue_number: int):
        """Initialize mission control."""
        self.issue_number = issue_number
        self.agents: Dict[str, AgentProgress] = {}
        self.console = Console()
        self.layout = Layout()
        self.start_time = datetime.now()
        self._setup_layout()

        # Context sharing metrics
        self.context_reuse_count = 0
        self.time_saved_seconds = 0.0

    def _setup_layout(self):
        """Setup the Rich layout structure."""
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=4)
        )

        self.layout["main"].split_row(
            Layout(name="agents", ratio=2),
            Layout(name="context", ratio=1)
        )

    def register_agent(
        self,
        agent_id: str,
        agent_type: str,
        display_name: str,
        emoji: str
    ) -> None:
        """Register a new agent."""
        self.agents[agent_id] = AgentProgress(
            agent_id=agent_id,
            agent_type=agent_type,
            display_name=display_name,
            emoji=emoji,
            status=AgentStatus.PENDING,
            progress_pct=0,
            current_task="Waiting to start...",
            files_processed=[],
            context_shared=False
        )

    def start_agent(self, agent_id: str, initial_task: str = "") -> None:
        """Mark agent as started."""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            agent.status = AgentStatus.STARTING
            agent.started_at = datetime.now()
            agent.current_task = initial_task or "Initializing..."

    def update_agent_progress(
        self,
        agent_id: str,
        status: AgentStatus,
        progress_pct: int,
        current_task: str,
        files_processed: Optional[List[str]] = None
    ) -> None:
        """Update agent progress."""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            agent.status = status
            agent.progress_pct = progress_pct
            agent.current_task = current_task

            if files_processed:
                agent.files_processed.extend(files_processed)

            if status == AgentStatus.COMPLETED:
                agent.completed_at = datetime.now()

    def mark_context_shared(self, agent_id: str, time_saved: float = 0.0) -> None:
        """Mark that agent used shared context."""
        if agent_id in self.agents:
            self.agents[agent_id].context_shared = True
            self.context_reuse_count += 1
            self.time_saved_seconds += time_saved

    def get_header_panel(self) -> Panel:
        """Generate header panel."""
        total_duration = datetime.now() - self.start_time

        title = f"🚀 DevFlow Mission Control - Issue #{self.issue_number}"

        stats_text = Text()
        stats_text.append(f"⏱️  Runtime: {total_duration.total_seconds():.1f}s  ", style="dim")
        stats_text.append(f"🔄 Context Reuse: {self.context_reuse_count}  ", style="green")
        stats_text.append(f"⚡ Time Saved: {self.time_saved_seconds:.1f}s", style="bright_green")

        return Panel(
            stats_text,
            title=title,
            border_style="blue",
            padding=(0, 1)
        )

    def get_agents_panel(self) -> Panel:
        """Generate agents progress panel."""
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Agent", width=18)
        table.add_column("Status", width=12)
        table.add_column("Progress", width=20)
        table.add_column("Current Task", width=30)
        table.add_column("Duration", width=8)

        for agent in self.agents.values():
            # Progress bar
            if agent.status == AgentStatus.COMPLETED:
                progress_bar = "[green]████████████████████[/green] 100%"
            elif agent.status == AgentStatus.FAILED:
                progress_bar = "[red]✗ Failed[/red]"
            elif agent.status == AgentStatus.PENDING:
                progress_bar = "[dim]░░░░░░░░░░░░░░░░░░░░[/dim] 0%"
            else:
                filled = int(agent.progress_pct / 5)  # 20 chars total
                bar = "█" * filled + "░" * (20 - filled)
                progress_bar = f"[{agent.status_color}]{bar}[/{agent.status_color}] {agent.progress_pct}%"

            # Agent name with context indicator
            agent_name = f"{agent.emoji} {agent.display_name}"
            if agent.context_shared:
                agent_name += " 🔗"

            # Status with color
            status_text = f"[{agent.status_color}]{agent.status.value.title()}[/{agent.status_color}]"

            table.add_row(
                agent_name,
                status_text,
                progress_bar,
                agent.current_task[:30] + "..." if len(agent.current_task) > 30 else agent.current_task,
                agent.duration
            )

        return Panel(
            table,
            title="🤖 Agent Status",
            border_style="green"
        )

    def get_context_panel(self) -> Panel:
        """Generate context sharing panel."""
        context_table = Table(show_header=True, header_style="bold cyan")
        context_table.add_column("Metric", width=15)
        context_table.add_column("Value", width=10)

        # Calculate files analyzed
        total_files = set()
        for agent in self.agents.values():
            total_files.update(agent.files_processed)

        context_table.add_row("Files Analyzed", str(len(total_files)))
        context_table.add_row("Context Reuses", str(self.context_reuse_count))
        context_table.add_row("Time Saved", f"{self.time_saved_seconds:.1f}s")

        # Efficiency calculation
        total_time = (datetime.now() - self.start_time).total_seconds()
        if total_time > 0:
            efficiency = (self.time_saved_seconds / total_time) * 100
            context_table.add_row("Efficiency", f"{efficiency:.0f}%")

        return Panel(
            context_table,
            title="📊 Context Sharing",
            border_style="cyan"
        )

    def get_footer_panel(self) -> Panel:
        """Generate footer panel with tips."""
        footer_text = Text()
        footer_text.append("💡 ", style="yellow")
        footer_text.append("Multiple agents work in parallel sharing context to eliminate redundant analysis. ", style="dim")
        footer_text.append("🔗 indicates context reuse.", style="blue")

        return Panel(
            footer_text,
            border_style="dim"
        )

    def render(self) -> Layout:
        """Render the complete mission control layout."""
        self.layout["header"].update(self.get_header_panel())
        self.layout["agents"].update(self.get_agents_panel())
        self.layout["context"].update(self.get_context_panel())
        self.layout["footer"].update(self.get_footer_panel())

        return self.layout

    def show_summary(self) -> None:
        """Show final summary after workflow completion."""
        total_duration = (datetime.now() - self.start_time).total_seconds()

        self.console.print("\n" + "="*70)
        self.console.print(f"🎉 [bold green]DevFlow Mission Control Summary - Issue #{self.issue_number}[/bold green]")
        self.console.print("="*70)

        # Agent results
        completed = sum(1 for agent in self.agents.values() if agent.status == AgentStatus.COMPLETED)
        failed = sum(1 for agent in self.agents.values() if agent.status == AgentStatus.FAILED)

        self.console.print(f"📊 Agents: {completed} completed, {failed} failed")

        # Time savings
        self.console.print(f"⏱️  Total Runtime: {total_duration:.1f}s")
        self.console.print(f"⚡ Time Saved by Context Reuse: {self.time_saved_seconds:.1f}s")
        self.console.print(f"🎯 Efficiency Gain: {(self.time_saved_seconds/total_duration)*100:.0f}%")

        # Files analyzed
        total_files = set()
        for agent in self.agents.values():
            total_files.update(agent.files_processed)
        self.console.print(f"📁 Unique Files Analyzed: {len(total_files)}")

        self.console.print("="*70 + "\n")


class LiveMissionControl:
    """Live updating mission control display."""

    def __init__(self, mission_control: MissionControl):
        """Initialize live display."""
        self.mission_control = mission_control
        self.live = Live(
            mission_control.render(),
            console=mission_control.console,
            refresh_per_second=2,
            screen=False
        )

    def __enter__(self):
        """Enter live display context."""
        self.live.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit live display context."""
        self.live.stop()

    def update(self):
        """Update the live display."""
        self.live.update(self.mission_control.render())
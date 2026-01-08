"""Agent Context Manager - Preserves analysis between workflow stages.

This system eliminates redundant file reading and codebase exploration
by sharing context between validation, implementation, and review agents.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Context preserved from agent analysis."""
    agent_type: str
    stage: str
    files_analyzed: Set[str]
    codebase_summary: str
    key_insights: List[str]
    analysis_timestamp: str
    execution_time: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'agent_type': self.agent_type,
            'stage': self.stage,
            'files_analyzed': list(self.files_analyzed),
            'codebase_summary': self.codebase_summary,
            'key_insights': self.key_insights,
            'analysis_timestamp': self.analysis_timestamp,
            'execution_time': self.execution_time
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentContext':
        """Create from dictionary."""
        return cls(
            agent_type=data['agent_type'],
            stage=data['stage'],
            files_analyzed=set(data['files_analyzed']),
            codebase_summary=data['codebase_summary'],
            key_insights=data['key_insights'],
            analysis_timestamp=data['analysis_timestamp'],
            execution_time=data['execution_time']
        )


class ContextManager:
    """Manages context sharing between workflow stages and agents."""

    def __init__(self, issue_number: int):
        """Initialize context manager for an issue."""
        self.issue_number = issue_number
        self.contexts: Dict[str, AgentContext] = {}
        self.shared_files: Set[str] = set()
        self.created_at = datetime.now().isoformat()

    def save_context(self, context: AgentContext) -> None:
        """Save context from an agent."""
        self.contexts[f"{context.stage}_{context.agent_type}"] = context
        self.shared_files.update(context.files_analyzed)

        logger.info(
            f"Saved context from {context.agent_type} at {context.stage}: "
            f"{len(context.files_analyzed)} files analyzed"
        )

    def get_context_summary(self, target_stage: str) -> str:
        """Get context summary for a target stage to avoid re-analysis."""
        if not self.contexts:
            return "No previous context available."

        # Find most relevant previous context
        relevant_contexts = [
            ctx for ctx in self.contexts.values()
            if self._is_relevant_context(ctx.stage, target_stage)
        ]

        if not relevant_contexts:
            return "No relevant previous context found."

        # Create comprehensive summary
        summary_parts = []

        # Files already analyzed
        all_files = set()
        for ctx in relevant_contexts:
            all_files.update(ctx.files_analyzed)

        if all_files:
            summary_parts.append(f"FILES ALREADY ANALYZED ({len(all_files)} total):")
            for file_path in sorted(all_files)[:15]:  # Show first 15
                summary_parts.append(f"  ✓ {file_path}")
            if len(all_files) > 15:
                summary_parts.append(f"  ... and {len(all_files) - 15} more files")

        # Key insights from previous stages
        summary_parts.append("\nKEY INSIGHTS FROM PREVIOUS ANALYSIS:")
        for ctx in relevant_contexts:
            summary_parts.append(f"\nFrom {ctx.agent_type} ({ctx.stage}):")
            summary_parts.append(f"  {ctx.codebase_summary}")
            for insight in ctx.key_insights[:3]:  # Top 3 insights
                summary_parts.append(f"  • {insight}")

        # Time savings
        total_time_saved = sum(ctx.execution_time for ctx in relevant_contexts)
        summary_parts.append(f"\n⏱️ ESTIMATED TIME SAVED: {total_time_saved:.1f} seconds")
        summary_parts.append("   (You can focus on implementation instead of re-exploring)")

        return "\n".join(summary_parts)

    def _is_relevant_context(self, source_stage: str, target_stage: str) -> bool:
        """Check if context from source stage is relevant for target stage."""
        stage_flow = {
            'validation': ['implementation', 'review'],
            'implementation': ['review', 'finalization'],
            'review': ['finalization', 'implementation']  # For iteration
        }

        return target_stage in stage_flow.get(source_stage, [])

    def get_files_to_avoid_reading(self) -> Set[str]:
        """Get files that have already been analyzed to avoid redundant reads."""
        return self.shared_files.copy()

    def extract_context_from_transcript(
        self,
        transcript: str,
        agent_type: str,
        stage: str,
        execution_time: float
    ) -> AgentContext:
        """Extract structured context from agent transcript."""

        # Extract files that were read
        files_analyzed = set()
        lines = transcript.split('\n')
        for line in lines:
            if '📖 Reading' in line and '.py' in line:
                # Extract filename from "📖 Reading filename.py"
                parts = line.split('📖 Reading ')
                if len(parts) > 1:
                    filename = parts[1].strip()
                    files_analyzed.add(filename)

        # Extract key insights from AI thinking
        insights = []
        for line in lines:
            if line.startswith('💭') and len(line) > 10:
                thought = line[2:].strip()
                if any(keyword in thought.lower() for keyword in
                      ['understand', 'implement', 'need', 'pattern', 'structure']):
                    insights.append(thought[:100] + '...' if len(thought) > 100 else thought)

        # Create summary from transcript
        summary = f"Agent analyzed {len(files_analyzed)} files and provided {len(insights)} key insights"

        return AgentContext(
            agent_type=agent_type,
            stage=stage,
            files_analyzed=files_analyzed,
            codebase_summary=summary,
            key_insights=insights[:5],  # Top 5 insights
            analysis_timestamp=datetime.now().isoformat(),
            execution_time=execution_time
        )
"""
Structured Activity Logger for R&D Simulation.
Logs every agent action with rich metadata to JSONL files
and provides real-time colored terminal output.
"""

import json
import os
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.markdown import Markdown
from rich import box


# Agent color scheme for terminal output
AGENT_COLORS = {
    "sarah_chen": "bold bright_magenta",
    "james_okafor": "bold bright_blue",
    "maya_rodriguez": "bold bright_green",
    "alex_kim": "bold bright_yellow",
    "priya_sharma": "blue",
    "marcus_webb": "green",
    "lena_voronova": "yellow",
    "tom_park": "cyan",
    "zara_ahmed": "bright_red",
}

ROUND_NAMES = {
    1: "🎯 Strategic Decomposition",
    2: "📋 Department Planning",
    3: "⚡ Execution (Individual Work)",
    4: "🤝 Cross-Department Collaboration",
    5: "🔧 Refinement",
    6: "🔄 Reflection & Synthesis",
    7: "📊 Final Report",
}


class SimulationLogger:
    """
    Logs simulation activity to JSONL files and provides
    rich terminal output with colored formatting.
    """

    def __init__(self, workspace_dir: str, verbose: bool = False):
        self.workspace_dir = workspace_dir
        self.verbose = verbose
        self.console = Console()
        self.log_dir = os.path.join(workspace_dir, "logs")
        os.makedirs(self.log_dir, exist_ok=True)

        self.activity_log = os.path.join(self.log_dir, "activity_log.jsonl")
        self.decision_log = os.path.join(self.log_dir, "decision_log.jsonl")

        # Stats tracking
        self.action_count = 0
        self.api_call_count = 0
        self.start_time = datetime.now()

    def log_round_start(self, round_number: int):
        """Log and display the start of a simulation round."""
        round_name = ROUND_NAMES.get(round_number, f"Round {round_number}")
        self.console.print()
        self.console.rule(f"[bold white] ROUND {round_number}: {round_name} ", style="bright_cyan")
        self.console.print()

        self._write_activity({
            "event": "round_start",
            "round": round_number,
            "round_name": round_name,
            "timestamp": datetime.now().isoformat(),
        })

    def log_round_end(self, round_number: int):
        """Log the end of a simulation round."""
        self.console.print()
        self.console.print(f"  [dim]✓ Round {round_number} complete[/dim]")
        self.console.print()

        self._write_activity({
            "event": "round_end",
            "round": round_number,
            "timestamp": datetime.now().isoformat(),
        })

    def log_agent_action(
        self,
        agent_id: str,
        agent_name: str,
        agent_role: str,
        action: str,
        task: str,
        assigned_by: str = "",
        reason: str = "",
        output_summary: str = "",
        full_output: str = "",
        round_number: int = 0,
        department: str = "",
    ):
        """Log an agent's action with full metadata."""
        self.action_count += 1
        self.api_call_count += 1

        color = AGENT_COLORS.get(agent_id, "white")

        # Terminal output
        self.console.print(
            f"  [{color}]▸ {agent_name}[/{color}] [dim]({agent_role})[/dim]"
        )
        self.console.print(f"    [dim]Action:[/dim] {action}")
        if assigned_by:
            self.console.print(f"    [dim]Assigned by:[/dim] {assigned_by}")

        if self.verbose and full_output:
            self.console.print()
            self.console.print(
                Panel(
                    full_output,
                    title=f"[{color}]{agent_name}'s Response[/{color}]",
                    border_style=color.replace("bold ", ""),
                    padding=(1, 2),
                )
            )
        elif output_summary:
            self.console.print(f"    [dim]Output:[/dim] {output_summary}")

        self.console.print()

        # JSONL log
        self._write_activity({
            "event": "agent_action",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "agent_role": agent_role,
            "department": department,
            "action": action,
            "task": task,
            "assigned_by": assigned_by,
            "reason": reason,
            "output_summary": output_summary,
            "round": round_number,
            "timestamp": datetime.now().isoformat(),
        })

    def log_communication(
        self,
        from_agent: str,
        to_agent: str,
        msg_type: str,
        content_preview: str,
        round_number: int = 0,
    ):
        """Log inter-agent communication."""
        from_color = AGENT_COLORS.get(from_agent, "white")
        to_color = AGENT_COLORS.get(to_agent, "white")

        icon = {
            "task_assignment": "📋",
            "question": "❓",
            "response": "💬",
            "deliverable": "📦",
            "escalation": "⚠️",
        }.get(msg_type, "💬")

        self.console.print(
            f"  {icon} [{from_color}]{from_agent}[/{from_color}] → "
            f"[{to_color}]{to_agent}[/{to_color}]: "
            f"[dim]{content_preview[:120]}[/dim]"
        )

    def log_reflection(
        self,
        agent_id: str,
        agent_name: str,
        reflection_preview: str,
        round_number: int = 0,
    ):
        """Log an agent's reflection."""
        color = AGENT_COLORS.get(agent_id, "white")
        self.console.print(
            f"  🔄 [{color}]{agent_name}[/{color}] reflects: "
            f"[italic dim]{reflection_preview[:150]}...[/italic dim]"
        )

        self._write_activity({
            "event": "reflection",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "reflection_preview": reflection_preview,
            "round": round_number,
            "timestamp": datetime.now().isoformat(),
        })

    def log_decision(
        self,
        agent_id: str,
        agent_name: str,
        decision: str,
        reasoning: str,
        round_number: int = 0,
    ):
        """Log a decision with its reasoning."""
        entry = {
            "event": "decision",
            "agent_id": agent_id,
            "agent_name": agent_name,
            "decision": decision,
            "reasoning": reasoning,
            "round": round_number,
            "timestamp": datetime.now().isoformat(),
        }
        with open(self.decision_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def log_simulation_start(self, prompt: str, agent_count: int):
        """Log simulation start."""
        self.console.print()
        self.console.print(
            Panel(
                f"[bold]Prompt:[/bold] {prompt}\n\n"
                f"[bold]Agents:[/bold] {agent_count}\n"
                f"[bold]Model:[/bold] Gemini 3 Flash Preview\n"
                f"[bold]Start:[/bold] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                title="[bold bright_cyan]🏢 R&D Department Simulation[/bold bright_cyan]",
                border_style="bright_cyan",
                padding=(1, 2),
            )
        )
        self.console.print()

    def log_simulation_end(self):
        """Log simulation completion with stats."""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        self.console.print()
        self.console.print(
            Panel(
                f"[bold]Duration:[/bold] {elapsed:.1f}s\n"
                f"[bold]Total Actions:[/bold] {self.action_count}\n"
                f"[bold]API Calls:[/bold] {self.api_call_count}\n"
                f"[bold]Logs:[/bold] {self.log_dir}",
                title="[bold bright_green]✅ Simulation Complete[/bold bright_green]",
                border_style="bright_green",
                padding=(1, 2),
            )
        )
        self.console.print()

    def _write_activity(self, entry: dict):
        """Write an entry to the activity log."""
        with open(self.activity_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

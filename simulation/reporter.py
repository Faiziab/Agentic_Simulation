"""
Report Generator for R&D Simulation.
Produces a comprehensive Markdown report documenting the full
simulation timeline, agent contributions, and decision audit trail.
"""

import json
import os
from datetime import datetime
from typing import Optional


class ReportGenerator:
    """
    Generates the final simulation report from logs and outputs.
    """

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.log_dir = os.path.join(workspace_dir, "logs")
        self.report_dir = os.path.join(workspace_dir, "reports")
        os.makedirs(self.report_dir, exist_ok=True)

    def generate(self, prompt: str, agents: dict, round_outputs: dict, message_board) -> str:
        """Generate the full simulation report."""
        report_path = os.path.join(self.report_dir, "simulation_report.md")

        sections = [
            self._header(prompt),
            self._agent_roster(agents),
            self._timeline(round_outputs, agents),
            self._communication_analysis(message_board),
            self._agent_contributions(agents, round_outputs),
            self._reflection_summary(agents),
            self._memory_statistics(agents),
            self._decision_audit_trail(),
        ]

        content = "\n\n---\n\n".join(sections)

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)

        return report_path

    def _header(self, prompt: str) -> str:
        return f"""# 🏢 R&D Department Simulation Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Initiative:** {prompt}
**Model:** gemini-3-flash-preview
"""

    def _agent_roster(self, agents: dict) -> str:
        lines = ["## 👥 Agent Roster\n"]
        lines.append("| Agent | Role | Level | Department | Memories |")
        lines.append("|-------|------|-------|------------|----------|")

        for aid, agent in agents.items():
            level_name = {1: "Executive", 2: "Dept Lead", 3: "Senior IC", 4: "Junior IC"}.get(
                agent.level, "?"
            )
            dept = agent.department or "All"
            mem_count = len(agent.memory_stream)
            lines.append(
                f"| {agent.name} | {agent.title} | L{agent.level} ({level_name}) | {dept} | {mem_count} |"
            )

        return "\n".join(lines)

    def _timeline(self, round_outputs: dict, agents: dict) -> str:
        lines = ["## 📅 Simulation Timeline\n"]

        round_names = {
            1: "Strategic Decomposition",
            2: "Department Planning",
            3: "Execution (Individual Work)",
            4: "Cross-Department Collaboration",
            5: "Refinement",
            6: "Reflection & Synthesis",
            7: "Final Report",
        }

        for round_num in sorted(round_outputs.keys()):
            round_name = round_names.get(round_num, f"Round {round_num}")
            outputs = round_outputs[round_num]
            lines.append(f"### Round {round_num}: {round_name}\n")

            for output in outputs:
                agent_name = output.get("agent_name", "Unknown")
                agent_role = output.get("agent_role", "")
                response = output.get("response", output.get("reflection", ""))

                lines.append(f"**{agent_name}** ({agent_role}):\n")
                lines.append(f"{response}")
                lines.append("")

        return "\n".join(lines)

    def _communication_analysis(self, message_board) -> str:
        lines = ["## 💬 Communication Analysis\n"]

        messages = message_board.get_all()
        lines.append(f"**Total Messages:** {len(messages)}\n")

        # By type
        type_counts: dict[str, int] = {}
        for m in messages:
            type_counts[m.msg_type] = type_counts.get(m.msg_type, 0) + 1

        lines.append("### Message Types\n")
        lines.append("| Type | Count |")
        lines.append("|------|-------|")
        for mt, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            icon = {
                "task_assignment": "📋",
                "question": "❓",
                "response": "💬",
                "deliverable": "📦",
                "escalation": "⚠️",
            }.get(mt, "•")
            lines.append(f"| {icon} {mt} | {count} |")

        # Cross-department messages
        cross_dept = [m for m in messages if m.channel == "cross_department"]
        if cross_dept:
            lines.append(f"\n### Cross-Department Communications ({len(cross_dept)})\n")
            for m in cross_dept:
                lines.append(f"- **{m.from_agent}** → **{m.to_agent}**: {m.content}")

        return "\n".join(lines)

    def _agent_contributions(self, agents: dict, round_outputs: dict) -> str:
        lines = ["## 📊 Agent Contributions\n"]

        for aid, agent in agents.items():
            contribution_count = 0
            for outputs in round_outputs.values():
                contribution_count += sum(
                    1 for o in outputs
                    if o.get("agent_id") == aid
                )

            if contribution_count > 0:
                lines.append(f"### {agent.name} ({agent.title})")
                lines.append(f"- **Contributions:** {contribution_count} actions")
                lines.append(f"- **Department:** {agent.department or 'Executive'}")
                lines.append(f"- **Memories formed:** {len(agent.memory_stream)}")

                reflections = agent.memory_stream.get_reflections()
                if reflections:
                    lines.append(f"- **Reflections:** {len(reflections)}")
                    latest = reflections[-1]
                    lines.append(f"- **Latest insight:** {latest.content}")
                lines.append("")

        return "\n".join(lines)

    def _reflection_summary(self, agents: dict) -> str:
        lines = ["## 🔄 Reflection Summary\n"]
        lines.append("Key insights generated during the reflection phase:\n")

        for aid, agent in agents.items():
            insights = agent.memory_stream.get_by_type("insight")
            reflections = agent.memory_stream.get_by_type("reflection")

            all_thinking = insights + reflections
            if all_thinking:
                lines.append(f"### {agent.name}\n")
                for mem in all_thinking[-2:]:  # Last 2
                    lines.append(f"> {mem.content}")
                    lines.append("")

        return "\n".join(lines)

    def _memory_statistics(self, agents: dict) -> str:
        lines = ["## 🧠 Memory Statistics\n"]
        lines.append("| Agent | Total | Observations | Actions | Communications | Reflections | Insights |")
        lines.append("|-------|-------|-------------|---------|---------------|------------|----------|")

        for aid, agent in agents.items():
            total = len(agent.memory_stream)
            obs = len(agent.memory_stream.get_by_type("observation", n=999))
            acts = len(agent.memory_stream.get_by_type("action", n=999))
            comms = len(agent.memory_stream.get_by_type("communication", n=999))
            refs = len(agent.memory_stream.get_by_type("reflection", n=999))
            ins = len(agent.memory_stream.get_by_type("insight", n=999))
            lines.append(
                f"| {agent.name} | {total} | {obs} | {acts} | {comms} | {refs} | {ins} |"
            )

        return "\n".join(lines)

    def _decision_audit_trail(self) -> str:
        lines = ["## 📋 Decision Audit Trail\n"]

        decision_log = os.path.join(self.log_dir, "decision_log.jsonl")
        if os.path.exists(decision_log):
            with open(decision_log, "r", encoding="utf-8") as f:
                decisions = [json.loads(line) for line in f if line.strip()]

            if decisions:
                for d in decisions:
                    lines.append(
                        f"- **{d.get('agent_name', '?')}** (Round {d.get('round', '?')}): "
                        f"{d.get('decision', '?')}\n"
                        f"  *Reasoning:* {d.get('reasoning', 'N/A')}"
                    )
                    lines.append("")
            else:
                lines.append("*No explicit decisions logged.*")
        else:
            lines.append("*Decision log not found.*")

        return "\n".join(lines)

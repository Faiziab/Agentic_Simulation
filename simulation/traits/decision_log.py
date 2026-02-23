"""
Decision Log Trait.
Auto-tracks key decisions made during the simulation to
prevent "goldfish memory" — agents always have context on
what was already decided and by whom.
"""

import os
import re
from simulation.traits import BaseTrait


# Patterns that signal a decision or recommendation
DECISION_PATTERNS = [
    r"(?:we should|I recommend|the approach is|decided to|my recommendation is)",
    r"(?:propose|proposing|suggested approach)",
    r"(?:VOTE:|voted to|the vote result)",
    r"(?:going forward|the plan is|strategy is)",
    r"(?:prioritize|focus on|key decision)",
    r"(?:selected|chosen|opted for|choosing)",
    r"(?:concluded that|conclusion is|bottom line)",
]


def _extract_decisions(text: str, agent_name: str, round_number: int) -> list[dict]:
    """Extract decision-like statements from text."""
    decisions = []
    sentences = re.split(r'[.!?\n]', text)

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20 or len(sentence) > 300:
            continue

        for pattern in DECISION_PATTERNS:
            if re.search(pattern, sentence, re.IGNORECASE):
                decisions.append({
                    "round": round_number,
                    "agent": agent_name,
                    "decision": sentence.strip()[:200],
                })
                break  # Don't double-count the same sentence

    return decisions[:3]  # Cap at 3 decisions per action


class DecisionLogTrait(BaseTrait):
    name = "decision_log"
    description = "Tracks key decisions across the simulation for continuity"

    def __init__(self, **kwargs):
        self.decisions: list[dict] = []
        self.workspace_dir: str = kwargs.get("workspace_dir", "")

    def on_act_postprocess(self, agent, result: dict, round_number: int) -> dict:
        """Extract decisions from agent output."""
        response = result.get("response", "")
        agent_name = getattr(agent, "name", agent.agent_id)

        new_decisions = _extract_decisions(response, agent_name, round_number)
        self.decisions.extend(new_decisions)

        if new_decisions:
            result["decisions_logged"] = len(new_decisions)

        return result

    def on_think_prompt(self, agent, task: str, round_number: int) -> str:
        """Inject recent decisions into the thinking prompt for context."""
        if not self.decisions:
            return ""

        # Show last 8 decisions (most recent)
        recent = self.decisions[-8:]

        lines = ["\nDECISIONS MADE SO FAR (for continuity — build on these, don't repeat or contradict without reason):"]
        for d in recent:
            lines.append(f"  - Round {d['round']}, {d['agent']}: \"{d['decision'][:120]}\"")
        lines.append("")

        return "\n".join(lines)

    def on_simulation_end(self, agent):
        """Save decision log to workspace on first call."""
        if not self.workspace_dir or not self.decisions:
            return

        report_path = os.path.join(self.workspace_dir, "reports", "decision_log.md")

        # Only write once (first agent to trigger this)
        if os.path.exists(report_path):
            return

        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(self.format_report())

    def format_report(self) -> str:
        """Format the full decision log as markdown."""
        if not self.decisions:
            return "## Decision Log\n\nNo decisions were tracked."

        lines = ["## Decision Log\n"]
        lines.append(f"**Total decisions tracked:** {len(self.decisions)}\n")

        # Group by round
        rounds: dict[int, list[dict]] = {}
        for d in self.decisions:
            rounds.setdefault(d["round"], []).append(d)

        for round_num in sorted(rounds.keys()):
            lines.append(f"### Round {round_num}\n")
            for d in rounds[round_num]:
                lines.append(f"- **{d['agent']}**: {d['decision']}")
            lines.append("")

        return "\n".join(lines)

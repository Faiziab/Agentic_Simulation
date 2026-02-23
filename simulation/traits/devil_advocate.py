"""
Devil's Advocate Trait.
Prevents groupthink by encouraging agents to challenge claims
that conflict with their expertise. Tracks disagreement events.
"""

import re
from simulation.traits import BaseTrait


# Disagreement markers — signals the agent actually challenged something
DISAGREEMENT_MARKERS = [
    r"\bhowever\b",
    r"\bI disagree\b",
    r"\bthis overlooks\b",
    r"\bcounterpoint\b",
    r"\bpush back\b",
    r"\bchallenge\b",
    r"\bnot convinced\b",
    r"\bskeptical\b",
    r"\bcontrary\b",
    r"\bunderestimates?\b",
    r"\boverestimates?\b",
    r"\brisk.{0,20}not.{0,20}address",
    r"\bignores?\b",
    r"\bmissing\b.*\bperspective\b",
    r"\balternative\b.*\bapproach\b",
    r"\bwhat about\b",
    r"\bbut\b.*\bconsider\b",
]


class DevilAdvocateTrait(BaseTrait):
    name = "devil_advocate"
    description = "Encourages agents to challenge weak claims and prevent groupthink"

    def __init__(self, **kwargs):
        self.disagreement_events: list[dict] = []
        self.rounds_active: dict[str, int] = {}  # agent_id -> rounds where challenged

    def on_think_prompt(self, agent, task: str, round_number: int) -> str:
        """Inject contrarian thinking instructions based on agent level."""
        level = getattr(agent, "level", 3)

        # Stronger instruction for senior agents, milder for juniors
        if level <= 2:
            return """
CRITICAL THINKING DIRECTIVE:
You are expected to challenge assumptions, question weak evidence, and push back
on conclusions that lack rigorous support. When you see claims from other team members:
- If a claim conflicts with your expertise, EXPLICITLY disagree and explain why
- If evidence is thin, say so directly: "This needs stronger evidence because..."
- If a risk is being downplayed, escalate it: "We are underestimating..."
- Don't agree just for consensus — constructive disagreement drives better outcomes

When you challenge something, prefix it with: CHALLENGE: [your objection]
"""
        elif level == 3:
            return """
CRITICAL THINKING:
You should respectfully challenge claims that conflict with your area of expertise.
If you see weak evidence or flawed reasoning, point it out constructively.
Don't hesitate to offer alternative perspectives — your expertise matters.

When you challenge something, prefix it with: CHALLENGE: [your objection]
"""
        else:
            return ""  # Juniors don't get this trait

    def on_act_postprocess(self, agent, result: dict, round_number: int) -> dict:
        """Track whether the agent actually challenged anything."""
        response = result.get("response", "")

        challenges_found = []
        for pattern in DISAGREEMENT_MARKERS:
            matches = re.findall(pattern, response, re.IGNORECASE)
            challenges_found.extend(matches)

        # Check for explicit CHALLENGE: prefix
        explicit_challenges = re.findall(
            r"CHALLENGE:\s*(.+?)(?:\n|$)", response, re.IGNORECASE
        )
        challenges_found.extend(explicit_challenges)

        challenge_count = len(challenges_found)
        result["challenges_raised"] = challenge_count
        result["challenge_details"] = challenges_found[:5]  # Cap at 5

        if challenge_count > 0:
            self.disagreement_events.append({
                "round": round_number,
                "agent_id": agent.agent_id,
                "agent_name": agent.name,
                "count": challenge_count,
                "samples": challenges_found[:3],
            })

            # Store in memory — the agent remembers they pushed back
            agent.memory_stream.add_memory(
                content=f"Raised {challenge_count} challenge(s) during discussion",
                memory_type="action",
                importance=7,
                source="self",
                round_number=round_number,
            )

        return result

    def get_summary(self) -> dict:
        """Get summary of disagreement activity."""
        if not self.disagreement_events:
            return {"total_challenges": 0, "agents_who_challenged": []}

        total = sum(e["count"] for e in self.disagreement_events)
        agents = list(set(e["agent_name"] for e in self.disagreement_events))
        return {
            "total_challenges": total,
            "agents_who_challenged": agents,
            "events": self.disagreement_events,
        }

    def format_report(self) -> str:
        """Format disagreement report as markdown."""
        summary = self.get_summary()
        if summary["total_challenges"] == 0:
            return "## Devil's Advocate Report\n\nNo challenges were raised during the simulation."

        lines = ["## Devil's Advocate Report\n"]
        lines.append(f"**Total challenges raised:** {summary['total_challenges']}")
        lines.append(f"**Agents who challenged:** {', '.join(summary['agents_who_challenged'])}\n")

        lines.append("| Round | Agent | Challenges | Sample |")
        lines.append("|-------|-------|-----------|--------|")
        for event in self.disagreement_events:
            sample = event["samples"][0][:60] if event["samples"] else "—"
            lines.append(
                f"| {event['round']} | {event['agent_name']} | "
                f"{event['count']} | {sample} |"
            )

        return "\n".join(lines)

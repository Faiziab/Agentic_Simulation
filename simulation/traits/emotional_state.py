"""
Emotional State / Morale Trait.
Tracks a dynamic mood (0.0–1.0) per agent that shifts based on
events like praise, criticism, being ignored, and task alignment.
Mood influences how agents think and communicate.
"""

import re
from simulation.traits import BaseTrait


# Keywords that signal praise (used to detect if lead praised an IC's work)
PRAISE_KEYWORDS = [
    r"\bexcellent\b", r"\bgreat work\b", r"\bwell done\b", r"\bimpressive\b",
    r"\bstrong analysis\b", r"\bexactly what\b", r"\bspot on\b", r"\bgood job\b",
    r"\boutstanding\b", r"\bthorough\b", r"\bexcellent work\b", r"\bhighly effective\b",
    r"\bcommend\b", r"\bappreciate\b", r"\bhighlight\b.*\bcontribution\b",
]

# Keywords that signal criticism
CRITICISM_KEYWORDS = [
    r"\bneeds improvement\b", r"\binsufficient\b", r"\bweak\b", r"\bflawed\b",
    r"\bmissing\b", r"\binadequate\b", r"\boverlooked\b", r"\bdisappointing\b",
    r"\bnot.{0,10}convincing\b", r"\blacks?\b.*\bdepth\b", r"\bsuperficial\b",
    r"\bflagged\b", r"\bneeds review\b", r"\bincomplete\b",
]


def _count_keyword_matches(text: str, patterns: list[str]) -> int:
    """Count how many keyword patterns match in the text."""
    count = 0
    text_lower = text.lower()
    for pattern in patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            count += 1
    return count


class EmotionalStateTrait(BaseTrait):
    name = "emotional_state"
    description = "Tracks dynamic agent mood that shifts based on praise, criticism, and events"

    def __init__(self, **kwargs):
        # agent_id -> mood (0.0 = very low, 1.0 = very high)
        self.moods: dict[str, float] = {}
        self.mood_history: list[dict] = []  # Log of all mood changes
        self.DEFAULT_MOOD = 0.6  # Slightly positive default

    def _ensure_agent(self, agent_id: str):
        """Initialize mood for an agent if not tracked yet."""
        if agent_id not in self.moods:
            self.moods[agent_id] = self.DEFAULT_MOOD

    def _shift_mood(self, agent_id: str, delta: float, reason: str, round_number: int):
        """Shift mood by delta, clamped to [0.05, 1.0]."""
        self._ensure_agent(agent_id)
        old_mood = self.moods[agent_id]

        # Frustration spiral: negative events hit harder when mood is already low
        if delta < 0 and old_mood < 0.3:
            delta *= 1.5

        # Positivity boost: positive events feel better from a low starting point
        if delta > 0 and old_mood < 0.4:
            delta *= 1.2

        new_mood = max(0.05, min(1.0, old_mood + delta))
        self.moods[agent_id] = new_mood

        self.mood_history.append({
            "agent_id": agent_id,
            "round": round_number,
            "old_mood": round(old_mood, 2),
            "new_mood": round(new_mood, 2),
            "delta": round(delta, 2),
            "reason": reason,
        })

    def on_perceive(self, agent, context: str, round_number: int) -> str:
        """Detect if the task aligns with agent expertise → small mood boost."""
        self._ensure_agent(agent.agent_id)

        expertise = getattr(agent, "expertise", [])
        if expertise and context:
            context_lower = context.lower()
            matches = sum(1 for exp in expertise if exp.lower() in context_lower)
            if matches >= 2:
                self._shift_mood(
                    agent.agent_id, 0.05,
                    f"Task aligns with expertise ({matches} matches)",
                    round_number,
                )

        return ""

    def on_think_prompt(self, agent, task: str, round_number: int) -> str:
        """Inject mood-contextual instruction into the thinking prompt."""
        self._ensure_agent(agent.agent_id)
        mood = self.moods[agent.agent_id]

        # Only inject at extreme moods — neutral range gets no injection
        if mood >= 0.75:
            return (
                "\nEMOTIONAL CONTEXT: You're feeling confident and energized. "
                "Your recent contributions have been well-received by the team. "
                "Channel this momentum — be bold in your recommendations.\n"
            )
        elif mood >= 0.55:
            # Neutral — no injection
            return ""
        elif mood >= 0.35:
            return (
                "\nEMOTIONAL CONTEXT: You're feeling somewhat cautious. "
                "Some of your recent contributions didn't get the traction you expected. "
                "You might want to double-check your reasoning before committing to bold claims.\n"
            )
        else:
            return (
                "\nEMOTIONAL CONTEXT: You're feeling undervalued — your recent work "
                "was either overlooked or received critical feedback. This is affecting "
                "your willingness to take risks. You may be more defensive or cautious "
                "than usual. Be aware of this but don't let it paralyze you.\n"
            )

    def on_act_postprocess(self, agent, result: dict, round_number: int) -> dict:
        """Detect praise/criticism in the response context and adjust mood."""
        self._ensure_agent(agent.agent_id)

        response = result.get("response", "")
        task = result.get("task", "")

        # Check if this response contains praise directed at the agent
        praise_count = _count_keyword_matches(task + " " + response, PRAISE_KEYWORDS)
        if praise_count >= 2:
            self._shift_mood(
                agent.agent_id, 0.12,
                f"Received praise ({praise_count} positive signals)",
                round_number,
            )

        # Check if this response contains criticism
        criticism_count = _count_keyword_matches(task, CRITICISM_KEYWORDS)
        if criticism_count >= 2:
            self._shift_mood(
                agent.agent_id, -0.10,
                f"Received criticism ({criticism_count} negative signals)",
                round_number,
            )

        # Check if this agent's work was fact-check flagged
        flagged = result.get("confidence_level")
        if flagged == "low" or flagged == "very_low":
            self._shift_mood(
                agent.agent_id, -0.08,
                "Low confidence in own output",
                round_number,
            )

        result["mood"] = round(self.moods[agent.agent_id], 2)
        result["mood_label"] = self._mood_to_label(self.moods[agent.agent_id])
        return result

    def on_round_end(self, agent, round_number: int):
        """Check if agent contributed this round — no activity = slight mood drop."""
        self._ensure_agent(agent.agent_id)
        recent = agent.memory_stream.get_by_round(round_number)

        if not recent or len(recent) == 0:
            self._shift_mood(
                agent.agent_id, -0.06,
                "Was not consulted or included this round",
                round_number,
            )

    @staticmethod
    def _mood_to_label(mood: float) -> str:
        """Convert mood float to a human-readable label."""
        if mood >= 0.8:
            return "energized"
        elif mood >= 0.65:
            return "positive"
        elif mood >= 0.45:
            return "neutral"
        elif mood >= 0.3:
            return "cautious"
        else:
            return "frustrated"

    def get_mood(self, agent_id: str) -> float:
        """Get current mood for an agent."""
        return self.moods.get(agent_id, self.DEFAULT_MOOD)

    def format_report(self) -> str:
        """Format morale report as markdown."""
        if not self.moods:
            return "## Morale Report\n\nNo mood data collected."

        lines = ["## Morale Report\n"]

        # Current mood table
        lines.append("### Final Mood State\n")
        lines.append("| Agent | Mood | Label |")
        lines.append("|-------|------|-------|")
        for agent_id, mood in sorted(self.moods.items(), key=lambda x: -x[1]):
            bar = "●" * int(mood * 10) + "○" * (10 - int(mood * 10))
            label = self._mood_to_label(mood)
            emoji = {"energized": "🔥", "positive": "😊", "neutral": "😐",
                     "cautious": "😟", "frustrated": "😤"}.get(label, "❓")
            lines.append(f"| {agent_id} | {bar} {mood:.0%} | {emoji} {label} |")

        # Significant mood shifts
        significant = [h for h in self.mood_history if abs(h["delta"]) >= 0.08]
        if significant:
            lines.append("\n### Significant Mood Shifts\n")
            for h in significant:
                direction = "📈" if h["delta"] > 0 else "📉"
                lines.append(
                    f"- {direction} **{h['agent_id']}** Round {h['round']}: "
                    f"{h['old_mood']:.0%} → {h['new_mood']:.0%} ({h['reason']})"
                )

        return "\n".join(lines)

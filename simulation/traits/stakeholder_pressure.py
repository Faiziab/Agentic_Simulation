"""
Stakeholder Pressure Trait.
Injects external pressure events mid-simulation to force agents
to adapt and reprioritize. Pressure is scoped by hierarchy level
(strategic for executives, operational for leads, execution for ICs).
"""

import random
from simulation.traits import BaseTrait


# Pressure events pool — mapped to the rounds they trigger at
# Each event has a scope (which hierarchy levels feel it) and intensity
PRESSURE_EVENTS = {
    2: {
        "event": "The CEO just asked for a 2-week progress checkpoint — she wants to "
                 "see a clear go/no-go framework before investing further resources.",
        "scope": {
            1: "Frame your strategic decomposition with a clear go/no-go framework. The board is watching.",
            2: "Your department plan needs to show quick wins. Leadership wants visible progress in 2 weeks.",
            3: "Focus on the highest-impact deliverable first. Time pressure means we can't do everything.",
            4: "Prioritize speed over perfection. We need a rapid prototype or analysis to show progress.",
        },
    },
    3: {
        "event": "A competitor just announced a similar product. The market window may be smaller than expected.",
        "scope": {
            1: "Factor competitive urgency into your prioritization. Are we still differentiated?",
            2: "Consider how the competitive landscape changes your department's priorities. Speed matters.",
            3: "Your analysis needs to address: how is our approach different from what the competitor is doing?",
            4: "When researching, keep an eye on the competitive angle — what makes our approach unique?",
        },
    },
    5: {
        "event": "Budget review is next week. Finance is asking every department to justify costs "
                 "and show ROI potential.",
        "scope": {
            1: "Your synthesis must include a clear ROI argument. Finance needs numbers.",
            2: "Include cost estimates and resource justification in your department output.",
            3: "Be mindful of cost in your recommendations. Propose the most cost-effective path.",
            4: "Consider budget constraints in your work. Flag anything that seems expensive.",
        },
    },
    6: {
        "event": "A key early adopter customer expressed strong interest in the capability — "
                 "they want a demo by end of next quarter.",
        "scope": {
            1: "A customer is ready to pilot. Factor this into your strategic recommendation — timing is everything.",
            2: "A potential pilot customer is waiting. Your department's output should be demo-ready.",
            3: "Think about what a customer pilot would require. Your work needs to be practical, not theoretical.",
            4: "Help make the work demo-ready. Focus on concrete, presentable deliverables.",
        },
    },
}

# Alternate pressure events for variety across simulation runs
ALTERNATE_EVENTS = {
    3: {
        "event": "The CTO raised concerns about technical debt — she wants to ensure any new "
                 "initiative doesn't create maintenance burdens.",
        "scope": {
            1: "Address technical sustainability in your decomposition. The CTO is watching for tech debt risks.",
            2: "Your plan must address: how do we build this without creating technical debt?",
            3: "Evaluate maintainability and operational overhead in your analysis.",
            4: "Consider long-term maintenance when designing or researching solutions.",
        },
    },
    5: {
        "event": "The Head of Engineering from a peer division offered to lend 2 engineers for "
                 "3 months if we can show a solid plan.",
        "scope": {
            1: "We have a chance to get extra engineering resources. Make the case in your synthesis.",
            2: "If we can justify additional headcount, we might get 2 more engineers. Plan accordingly.",
            3: "Additional engineering support is possible. What could we accomplish with more resources?",
            4: "Extra help might be available. Think about what you'd do with more bandwidth.",
        },
    },
}


class StakeholderPressureTrait(BaseTrait):
    name = "stakeholder_pressure"
    description = "Injects external pressure events to force agents to adapt and reprioritize"

    def __init__(self, **kwargs):
        self.active_events: list[dict] = []
        self.acknowledged: dict[str, list[int]] = {}  # agent_id -> [rounds where addressed]

        # Randomly choose between primary and alternate events for variety
        self.event_pool = dict(PRESSURE_EVENTS)
        for round_num, alt_event in ALTERNATE_EVENTS.items():
            if random.random() < 0.35:  # 35% chance to use alternate
                self.event_pool[round_num] = alt_event

    def on_perceive(self, agent, context: str, round_number: int) -> str:
        """Inject pressure event into agent's perception if one is active for this round."""
        event = self.event_pool.get(round_number)
        if not event:
            return ""

        level = getattr(agent, "level", 3)
        level_message = event["scope"].get(level)
        if not level_message:
            return ""

        # Record the event
        if not any(e["round"] == round_number for e in self.active_events):
            self.active_events.append({
                "round": round_number,
                "event": event["event"],
            })

        return f"""
⚠️ EXTERNAL PRESSURE — NEW DEVELOPMENT:
{event['event']}

What this means for you: {level_message}
Factor this into your current work. Acknowledge it explicitly in your response.
"""

    def on_act_postprocess(self, agent, result: dict, round_number: int) -> dict:
        """Track whether agents acknowledged the pressure event."""
        if round_number not in self.event_pool:
            return result

        response = result.get("response", "").lower()
        event = self.event_pool[round_number]

        # Check for acknowledgment signals
        acknowledgment_signals = [
            "competitor", "budget", "ceo", "customer", "pilot",
            "timeline", "deadline", "pressure", "urgency",
            "cost", "roi", "demo", "go/no-go", "progress",
            "tech debt", "maintenance", "resources",
        ]
        acknowledged = any(signal in response for signal in acknowledgment_signals)

        if acknowledged:
            self.acknowledged.setdefault(agent.agent_id, []).append(round_number)
            result["pressure_acknowledged"] = True
        else:
            result["pressure_acknowledged"] = False

        return result

    def format_report(self) -> str:
        """Format pressure events report as markdown."""
        if not self.active_events:
            return "## Stakeholder Pressure Report\n\nNo pressure events were triggered."

        lines = ["## Stakeholder Pressure Report\n"]
        lines.append(f"**Events triggered:** {len(self.active_events)}\n")

        for event in self.active_events:
            lines.append(f"### Round {event['round']}")
            lines.append(f"📢 *{event['event']}*\n")

        # Acknowledgment summary
        if self.acknowledged:
            lines.append("### Agent Responses\n")
            lines.append("| Agent | Rounds Acknowledged |")
            lines.append("|-------|-------------------|")
            for agent_id, rounds in sorted(self.acknowledged.items()):
                lines.append(f"| {agent_id} | {', '.join(str(r) for r in rounds)} |")
        else:
            lines.append("*No agents explicitly acknowledged the pressure events.*")

        return "\n".join(lines)

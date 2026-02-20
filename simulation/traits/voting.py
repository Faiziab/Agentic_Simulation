"""
Voting & Consensus Trait.
Agents vote on decisions with weighted ballots.
Hierarchy level and expertise relevance affect vote weight.
"""

from typing import Optional
from simulation.traits import BaseTrait


class VotingBallot:
    """A single agent's vote."""

    def __init__(self, agent_id: str, agent_name: str, vote: str,
                 reasoning: str, weight: float = 1.0):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.vote = vote  # "support", "oppose", "abstain"
        self.reasoning = reasoning
        self.weight = weight

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "vote": self.vote,
            "reasoning": self.reasoning,
            "weight": self.weight,
        }


class VotingSession:
    """Manages a single vote on a topic."""

    def __init__(self, topic: str, options: list[str] | None = None,
                 round_number: int = 0):
        self.topic = topic
        self.options = options or ["support", "oppose", "abstain"]
        self.round_number = round_number
        self.ballots: list[VotingBallot] = []
        self.result: Optional[dict] = None

    def cast_vote(self, ballot: VotingBallot):
        """Cast a vote."""
        self.ballots.append(ballot)

    def tally(self) -> dict:
        """Count votes and determine outcome."""
        weighted_counts = {}
        for option in self.options:
            weighted_counts[option] = 0.0

        for ballot in self.ballots:
            if ballot.vote in weighted_counts:
                weighted_counts[ballot.vote] += ballot.weight

        # Determine winner
        winner = max(weighted_counts, key=weighted_counts.get)
        total_weight = sum(weighted_counts.values())

        self.result = {
            "topic": self.topic,
            "winner": winner,
            "weighted_counts": weighted_counts,
            "total_weight": total_weight,
            "margin": weighted_counts[winner] / total_weight if total_weight > 0 else 0,
            "ballots": [b.to_dict() for b in self.ballots],
            "unanimous": len(set(b.vote for b in self.ballots if b.vote != "abstain")) <= 1,
            "dissenting": [
                b.to_dict() for b in self.ballots
                if b.vote != winner and b.vote != "abstain"
            ],
            "round": self.round_number,
        }
        return self.result


# Hierarchy level → vote weight multiplier
LEVEL_WEIGHTS = {
    1: 3.0,   # VP — highest weight
    2: 2.0,   # Department Leads
    3: 1.5,   # Senior ICs
    4: 1.0,   # Junior ICs
}


class VotingTrait(BaseTrait):
    name = "voting"
    description = "Agents vote on key decisions with weighted ballots"

    def __init__(self, **kwargs):
        self.sessions: list[VotingSession] = []

    def create_session(self, topic: str, round_number: int = 0) -> VotingSession:
        """Create a new voting session."""
        session = VotingSession(topic=topic, round_number=round_number)
        self.sessions.append(session)
        return session

    def build_vote_prompt(self, agent_name: str, agent_role: str,
                          topic: str, context: str = "") -> str:
        """Build a prompt asking an agent to vote."""
        return f"""VOTING SESSION — Your vote is required.

TOPIC: {topic}

{f"CONTEXT: {context}" if context else ""}

As {agent_name} ({agent_role}), you must cast your vote.

Respond in EXACTLY this format:
VOTE: [support / oppose / abstain]
REASONING: [your rationale in 2-3 sentences, based on your expertise and the evidence]
CONCERNS: [any concerns even if you voted support, or "None"]
"""

    def parse_vote(self, response: str) -> tuple[str, str]:
        """Parse vote and reasoning from response."""
        vote = "abstain"
        reasoning = ""

        for line in response.split("\n"):
            line_stripped = line.strip().upper()
            if line_stripped.startswith("VOTE:"):
                vote_text = line.strip()[5:].strip().lower()
                if "support" in vote_text:
                    vote = "support"
                elif "oppose" in vote_text:
                    vote = "oppose"
                else:
                    vote = "abstain"
            elif line.strip().upper().startswith("REASONING:"):
                reasoning = line.strip()[10:].strip()

        return vote, reasoning

    def get_weight(self, agent_level: int) -> float:
        """Get vote weight based on hierarchy level."""
        return LEVEL_WEIGHTS.get(agent_level, 1.0)

    def get_all_results(self) -> list[dict]:
        """Get results of all voting sessions."""
        return [s.result for s in self.sessions if s.result]

    def format_results(self) -> str:
        """Format all voting results as markdown."""
        if not self.sessions:
            return "No voting sessions were held."

        lines = ["## Voting Results\n"]
        for i, session in enumerate(self.sessions, 1):
            if not session.result:
                continue
            r = session.result
            lines.append(f"### Vote {i}: {r['topic']}")
            lines.append(f"**Outcome:** {r['winner'].upper()} "
                         f"(margin: {r['margin']:.0%})")
            lines.append(f"**Unanimous:** {'Yes' if r['unanimous'] else 'No'}\n")

            lines.append("| Voter | Vote | Weight | Reasoning |")
            lines.append("|-------|------|--------|-----------|")
            for b in r["ballots"]:
                lines.append(
                    f"| {b['agent_name']} | {b['vote']} | {b['weight']:.1f} | {b['reasoning'][:80]} |"
                )

            if r["dissenting"]:
                lines.append(f"\n**Dissenting opinions:**")
                for d in r["dissenting"]:
                    lines.append(f"- **{d['agent_name']}** ({d['vote']}): {d['reasoning']}")
            lines.append("")

        return "\n".join(lines)

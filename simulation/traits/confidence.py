"""
Confidence Scores Trait.
Agents rate their confidence (1-10) on each output.
Low confidence flags trigger review and are highlighted in reports.
"""

import re
from simulation.traits import BaseTrait


class ConfidenceTrait(BaseTrait):
    name = "confidence"
    description = "Agents self-rate confidence on each output (1-10)"

    def __init__(self, **kwargs):
        self.scores: list[dict] = []  # {round, score, task_preview, agent_id}

    def on_think_prompt(self, agent, task: str, round_number: int) -> str:
        """Inject confidence-rating instruction into the thinking prompt."""
        return """
CONFIDENCE RATING:
At the END of your response, you MUST include a confidence self-assessment:
CONFIDENCE: [X/10] — [brief reason]

Rating guide:
- 9-10: Very confident — well within my expertise, strong evidence
- 7-8: Confident — good understanding, minor uncertainties
- 5-6: Moderate — some assumptions made, would benefit from validation
- 3-4: Low — significant uncertainties, needs cross-checking
- 1-2: Very low — largely speculative, outside my core expertise
"""

    def on_act_postprocess(self, agent, result: dict, round_number: int) -> dict:
        """Extract confidence score from the response."""
        response = result.get("response", "")
        score = self._extract_score(response)

        result["confidence_score"] = score
        result["confidence_level"] = self._score_to_level(score)

        self.scores.append({
            "round": round_number,
            "score": score,
            "level": result["confidence_level"],
            "agent_id": agent.agent_id,
            "agent_name": agent.name,
            "task_preview": result.get("task", "")[:80],
        })

        # Store in memory if low confidence
        if score and score < 5:
            agent.memory_stream.add_memory(
                content=f"LOW CONFIDENCE ({score}/10) on task: {result.get('task', '')[:100]}",
                memory_type="observation",
                importance=8,
                source="self",
                round_number=round_number,
            )

        return result

    def _extract_score(self, response: str) -> int | None:
        """Parse confidence score from response text."""
        # Match patterns like "CONFIDENCE: 7/10" or "Confidence: 8/10"
        patterns = [
            r'CONFIDENCE:\s*(\d{1,2})\s*/\s*10',
            r'[Cc]onfidence:\s*(\d{1,2})\s*/\s*10',
            r'[Cc]onfidence\s+[Ss]core:\s*(\d{1,2})',
        ]
        for pattern in patterns:
            match = re.search(pattern, response)
            if match:
                score = int(match.group(1))
                return min(max(score, 1), 10)  # Clamp 1-10
        return None

    def _score_to_level(self, score: int | None) -> str:
        if score is None:
            return "unrated"
        if score >= 9:
            return "very_high"
        if score >= 7:
            return "high"
        if score >= 5:
            return "moderate"
        if score >= 3:
            return "low"
        return "very_low"

    def get_summary(self) -> dict:
        """Get summary of all confidence scores."""
        if not self.scores:
            return {"avg": None, "min": None, "max": None, "low_count": 0}

        valid = [s for s in self.scores if s["score"] is not None]
        if not valid:
            return {"avg": None, "min": None, "max": None, "low_count": 0}

        scores = [s["score"] for s in valid]
        return {
            "avg": sum(scores) / len(scores),
            "min": min(scores),
            "max": max(scores),
            "low_count": sum(1 for s in scores if s < 5),
            "scores": valid,
        }

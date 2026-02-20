"""
Hallucination / Fact Check Trait.
After agents produce output, a checker reviews claims
and flags unsupported or unverifiable statements.
"""

from simulation.traits import BaseTrait


class FactCheckResult:
    """Result of a fact-check on a single piece of content."""

    def __init__(self, source_agent: str, checker_agent: str,
                 content_preview: str, round_number: int):
        self.source_agent = source_agent
        self.checker_agent = checker_agent
        self.content_preview = content_preview
        self.round_number = round_number
        self.verified_claims: list[str] = []
        self.flagged_claims: list[str] = []
        self.review_notes: str = ""
        self.overall_rating: str = "pending"  # "reliable", "mostly_reliable", "needs_review"

    def to_dict(self) -> dict:
        return {
            "source_agent": self.source_agent,
            "checker_agent": self.checker_agent,
            "content_preview": self.content_preview[:100],
            "round": self.round_number,
            "verified_claims": self.verified_claims,
            "flagged_claims": self.flagged_claims,
            "review_notes": self.review_notes,
            "overall_rating": self.overall_rating,
        }


class FactCheckTrait(BaseTrait):
    name = "fact_check"
    description = "Cross-check claims between agents, flag unsupported statements"

    def __init__(self, **kwargs):
        self.results: list[FactCheckResult] = []

    def build_fact_check_prompt(self, checker_name: str, checker_role: str,
                                source_name: str, source_role: str,
                                content: str, knowledge_context: str = "") -> str:
        """Build prompt for fact-checking another agent's output."""
        return f"""FACT-CHECK REVIEW — You are reviewing {source_name}'s ({source_role}) work.

As {checker_name} ({checker_role}), critically review the following content for accuracy,
unsupported claims, and potential hallucinations.

CONTENT TO REVIEW:
{content[:3000]}

{f"RELEVANT KNOWLEDGE CONTEXT:{chr(10)}{knowledge_context}" if knowledge_context else ""}

Analyze the content and respond in EXACTLY this format:

VERIFIED CLAIMS:
- [list claims that appear well-supported and accurate]

FLAGGED CLAIMS:
- [list claims that seem unsupported, exaggerated, or potentially inaccurate]
- [explain WHY each claim is flagged]

OVERALL RATING: [reliable / mostly_reliable / needs_review]

REVIEW NOTES:
[Any additional observations about the quality and accuracy of the work]
"""

    def parse_fact_check(self, response: str) -> tuple[list[str], list[str], str, str]:
        """Parse fact-check response into structured data."""
        verified = []
        flagged = []
        rating = "pending"
        notes = ""

        current_section = ""
        for line in response.split("\n"):
            stripped = line.strip()

            if stripped.upper().startswith("VERIFIED CLAIMS"):
                current_section = "verified"
            elif stripped.upper().startswith("FLAGGED CLAIMS"):
                current_section = "flagged"
            elif stripped.upper().startswith("OVERALL RATING"):
                rating_text = stripped.split(":", 1)[-1].strip().lower()
                if "reliable" in rating_text and "mostly" not in rating_text and "needs" not in rating_text:
                    rating = "reliable"
                elif "mostly" in rating_text:
                    rating = "mostly_reliable"
                elif "needs" in rating_text or "review" in rating_text:
                    rating = "needs_review"
                current_section = ""
            elif stripped.upper().startswith("REVIEW NOTES"):
                current_section = "notes"
            elif stripped.startswith("-") and current_section == "verified":
                verified.append(stripped[1:].strip())
            elif stripped.startswith("-") and current_section == "flagged":
                flagged.append(stripped[1:].strip())
            elif current_section == "notes" and stripped:
                notes += stripped + " "

        return verified, flagged, rating, notes.strip()

    def record_result(self, source_agent: str, checker_agent: str,
                      content_preview: str, verified: list[str],
                      flagged: list[str], rating: str, notes: str,
                      round_number: int) -> FactCheckResult:
        """Record a fact-check result."""
        result = FactCheckResult(
            source_agent=source_agent,
            checker_agent=checker_agent,
            content_preview=content_preview,
            round_number=round_number,
        )
        result.verified_claims = verified
        result.flagged_claims = flagged
        result.overall_rating = rating
        result.review_notes = notes
        self.results.append(result)
        return result

    def get_flagged_count(self) -> int:
        """Get total number of flagged claims."""
        return sum(len(r.flagged_claims) for r in self.results)

    def format_report(self) -> str:
        """Format all fact-check results as markdown."""
        if not self.results:
            return "## Fact-Check Report\n\nNo fact-checks were performed."

        lines = ["## Fact-Check Report\n"]
        lines.append(f"**Total reviews:** {len(self.results)}")
        lines.append(f"**Total flagged claims:** {self.get_flagged_count()}\n")

        # Summary table
        lines.append("| Source | Checker | Rating | Verified | Flagged |")
        lines.append("|--------|---------|--------|----------|---------|")
        for r in self.results:
            rating_emoji = {"reliable": "✅", "mostly_reliable": "⚠️", "needs_review": "🔴"}.get(
                r.overall_rating, "❓"
            )
            lines.append(
                f"| {r.source_agent} | {r.checker_agent} | "
                f"{rating_emoji} {r.overall_rating} | "
                f"{len(r.verified_claims)} | {len(r.flagged_claims)} |"
            )

        # Detailed flagged claims
        flagged_results = [r for r in self.results if r.flagged_claims]
        if flagged_results:
            lines.append("\n### Flagged Claims Detail\n")
            for r in flagged_results:
                lines.append(f"**{r.source_agent}** (reviewed by {r.checker_agent}):")
                for claim in r.flagged_claims:
                    lines.append(f"  - 🔴 {claim}")
                if r.review_notes:
                    lines.append(f"  - *Notes: {r.review_notes}*")
                lines.append("")

        return "\n".join(lines)

"""
Skill Growth / Experience Trait.
Tracks agent expertise growth across simulation runs.
Agents earn XP in domains when they work on related tasks.
XP persists across runs and enhances agent prompts.
"""

import json
import os
import re
from simulation.traits import BaseTrait


# Predefined skill domains
SKILL_DOMAINS = [
    "ai_ml",
    "architecture",
    "data_engineering",
    "ux_research",
    "product_strategy",
    "security",
    "performance",
    "nlp",
    "cloud_infrastructure",
    "testing_qa",
    "market_analysis",
    "user_research",
]

# Keywords that map to domains
DOMAIN_KEYWORDS = {
    "ai_ml": ["ai", "machine learning", "ml", "neural", "model", "training", "deep learning",
              "llm", "embedding", "vector", "classification", "prediction"],
    "architecture": ["architecture", "system design", "scalability", "microservice",
                     "api", "infrastructure", "distributed", "design pattern"],
    "data_engineering": ["data pipeline", "etl", "database", "sql", "data lake",
                         "schema", "migration", "indexing", "query"],
    "ux_research": ["ux", "user experience", "usability", "wireframe", "mockup",
                    "accessibility", "interface", "interaction"],
    "product_strategy": ["product", "roadmap", "strategy", "market fit", "competitive",
                         "pricing", "launch", "go-to-market"],
    "security": ["security", "encryption", "authentication", "authorization",
                 "vulnerability", "compliance", "privacy", "gdpr"],
    "performance": ["performance", "latency", "throughput", "optimization",
                    "caching", "benchmark", "load test"],
    "nlp": ["nlp", "natural language", "text processing", "search", "semantic",
            "tokenization", "information retrieval"],
    "cloud_infrastructure": ["cloud", "aws", "gcp", "azure", "kubernetes", "docker",
                             "deployment", "devops", "ci/cd"],
    "testing_qa": ["test", "qa", "quality", "regression", "integration test",
                   "unit test", "coverage", "bug"],
    "market_analysis": ["market", "competitor", "industry", "trend", "TAM",
                        "growth", "segment", "analysis"],
    "user_research": ["user research", "interview", "survey", "persona",
                      "pain point", "user need", "feedback"],
}

# XP thresholds for level names
XP_LEVELS = [
    (0, "Novice"),
    (10, "Familiar"),
    (25, "Competent"),
    (50, "Proficient"),
    (100, "Expert"),
    (200, "Master"),
]


def xp_to_level(xp: int) -> str:
    """Convert XP to a level name."""
    level_name = "Novice"
    for threshold, name in XP_LEVELS:
        if xp >= threshold:
            level_name = name
    return level_name


class SkillGrowthTrait(BaseTrait):
    name = "skill_growth"
    description = "Track agent expertise growth across domains and simulation runs"

    def __init__(self, **kwargs):
        self.agent_skills: dict[str, dict[str, int]] = {}  # agent_id -> {domain -> xp}
        self.workspace_dir: str = kwargs.get("workspace_dir", "")
        self.level_ups: list[dict] = []  # Log of level-up events

    def _ensure_agent(self, agent_id: str):
        if agent_id not in self.agent_skills:
            self.agent_skills[agent_id] = {d: 0 for d in SKILL_DOMAINS}

    def load_skills(self, agent_id: str, workspace_dir: str):
        """Load persisted skills from a previous run."""
        self.workspace_dir = workspace_dir
        skills_dir = os.path.join(workspace_dir, "..", "skills")
        skills_file = os.path.join(skills_dir, f"{agent_id}.json")

        self._ensure_agent(agent_id)

        if os.path.exists(skills_file):
            with open(skills_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                self.agent_skills[agent_id].update(saved.get("skills", {}))

    def save_skills(self, agent_id: str, workspace_dir: str):
        """Persist skills to JSON."""
        skills_dir = os.path.join(workspace_dir, "..", "skills")
        os.makedirs(skills_dir, exist_ok=True)

        skills_file = os.path.join(skills_dir, f"{agent_id}.json")
        data = {
            "agent_id": agent_id,
            "skills": self.agent_skills.get(agent_id, {}),
        }
        with open(skills_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def on_think_prompt(self, agent, task: str, round_number: int) -> str:
        """Inject skill-based expertise bonuses into prompt."""
        self._ensure_agent(agent.agent_id)
        skills = self.agent_skills[agent.agent_id]

        # Find domains where agent has significant XP
        strong_domains = [
            (domain, xp, xp_to_level(xp))
            for domain, xp in skills.items()
            if xp >= 10  # At least "Familiar"
        ]

        if not strong_domains:
            return ""

        lines = ["\nYOUR ACCUMULATED EXPERTISE (from experience):"]
        for domain, xp, level in sorted(strong_domains, key=lambda x: -x[1]):
            domain_display = domain.replace("_", " ").title()
            lines.append(f"  - {domain_display}: {level} ({xp} XP)")
        lines.append("Leverage your strongest areas when relevant.\n")

        return "\n".join(lines)

    def on_act_postprocess(self, agent, result: dict, round_number: int) -> dict:
        """Award XP based on task content."""
        self._ensure_agent(agent.agent_id)
        response = result.get("response", "").lower()
        task = result.get("task", "").lower()
        combined = f"{task} {response}"

        xp_gained = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in combined)
            if matches >= 2:  # Need at least 2 keyword matches
                xp_amount = min(matches * 2, 10)  # Cap at 10 XP per action
                old_xp = self.agent_skills[agent.agent_id][domain]
                self.agent_skills[agent.agent_id][domain] += xp_amount
                new_xp = self.agent_skills[agent.agent_id][domain]
                xp_gained[domain] = xp_amount

                # Check for level-up
                old_level = xp_to_level(old_xp)
                new_level = xp_to_level(new_xp)
                if old_level != new_level:
                    self.level_ups.append({
                        "agent_id": agent.agent_id,
                        "agent_name": agent.name,
                        "domain": domain,
                        "old_level": old_level,
                        "new_level": new_level,
                        "xp": new_xp,
                        "round": round_number,
                    })

        if xp_gained:
            result["xp_gained"] = xp_gained

        return result

    def on_simulation_end(self, agent):
        """Persist skills at end of simulation."""
        if self.workspace_dir:
            self.save_skills(agent.agent_id, self.workspace_dir)

    def get_skill_report(self, agent_id: str) -> str:
        """Get a formatted skill report for an agent."""
        self._ensure_agent(agent_id)
        skills = self.agent_skills[agent_id]

        lines = []
        for domain, xp in sorted(skills.items(), key=lambda x: -x[1]):
            if xp > 0:
                level = xp_to_level(xp)
                bar = "█" * min(xp // 5, 20) + "░" * max(0, 20 - xp // 5)
                lines.append(f"  {domain.replace('_', ' ').title():25s} {bar} {level} ({xp} XP)")

        return "\n".join(lines) if lines else "  No skills developed yet."

    def format_all_skills(self) -> str:
        """Format skill report for all agents."""
        lines = ["## Skill Growth Report\n"]
        for agent_id in sorted(self.agent_skills.keys()):
            lines.append(f"### {agent_id}")
            lines.append(self.get_skill_report(agent_id))
            lines.append("")

        if self.level_ups:
            lines.append("### Level-Up Events")
            for lu in self.level_ups:
                lines.append(
                    f"- **{lu['agent_name']}** leveled up in "
                    f"**{lu['domain'].replace('_', ' ').title()}**: "
                    f"{lu['old_level']} → {lu['new_level']} (Round {lu['round']})"
                )

        return "\n".join(lines)

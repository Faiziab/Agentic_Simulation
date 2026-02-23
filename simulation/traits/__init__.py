"""
Modular Trait System for R&D Simulation.
Provides a plugin architecture where features can be independently
enabled/disabled per agent via YAML configuration.

Usage:
    registry = TraitRegistry()
    registry.register("confidence", ConfidenceTrait)
    registry.enable(agent, ["confidence", "voting"])
"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseTrait(ABC):
    """
    Base class for all agent traits.
    Traits plug into the agent's cognitive loop via lifecycle hooks.
    Override only the hooks you need — defaults are no-ops.
    """

    name: str = "base"
    description: str = "Base trait"

    def on_perceive(self, agent, context: str, round_number: int) -> str:
        """Called during perception. Return extra context to inject, or empty string."""
        return ""

    def on_think_prompt(self, agent, task: str, round_number: int) -> str:
        """Called before thinking. Return extra prompt text to inject, or empty string."""
        return ""

    def on_act_postprocess(self, agent, result: dict, round_number: int) -> dict:
        """Called after action. Can modify or enrich the result dict. Return it."""
        return result

    def on_round_end(self, agent, round_number: int):
        """Called at end of each round. Use for persistence, cleanup, etc."""
        pass

    def on_simulation_end(self, agent):
        """Called when the full simulation ends. Use for final persistence."""
        pass


class TraitRegistry:
    """
    Manages available traits and which traits are enabled per agent.
    Acts as the central registry for the plugin system.
    """

    def __init__(self):
        self._available: dict[str, type[BaseTrait]] = {}
        self._instances: dict[str, dict[str, BaseTrait]] = {}  # agent_id -> {trait_name -> instance}

    def register(self, name: str, trait_class: type[BaseTrait]):
        """Register a trait class by name."""
        self._available[name] = trait_class

    def enable(self, agent_id: str, trait_names: list[str], **kwargs) -> list[BaseTrait]:
        """Enable specific traits for an agent. Returns list of enabled trait instances."""
        if agent_id not in self._instances:
            self._instances[agent_id] = {}

        enabled = []
        for name in trait_names:
            if name in self._available and name not in self._instances[agent_id]:
                instance = self._available[name](**kwargs)
                self._instances[agent_id][name] = instance
                enabled.append(instance)

        return enabled

    def get_traits(self, agent_id: str) -> list[BaseTrait]:
        """Get all enabled trait instances for an agent."""
        return list(self._instances.get(agent_id, {}).values())

    def get_trait(self, agent_id: str, trait_name: str) -> Optional[BaseTrait]:
        """Get a specific trait instance for an agent."""
        return self._instances.get(agent_id, {}).get(trait_name)

    def has_trait(self, agent_id: str, trait_name: str) -> bool:
        """Check if an agent has a specific trait enabled."""
        return trait_name in self._instances.get(agent_id, {})

    # ── Lifecycle dispatch ──────────────────────────

    def call_on_perceive(self, agent_id: str, agent, context: str, round_number: int) -> str:
        """Call on_perceive on all enabled traits, return combined extra context."""
        extras = []
        for trait in self.get_traits(agent_id):
            extra = trait.on_perceive(agent, context, round_number)
            if extra:
                extras.append(extra)
        return "\n".join(extras)

    def call_on_think_prompt(self, agent_id: str, agent, task: str, round_number: int) -> str:
        """Call on_think_prompt on all enabled traits, return combined prompt additions."""
        extras = []
        for trait in self.get_traits(agent_id):
            extra = trait.on_think_prompt(agent, task, round_number)
            if extra:
                extras.append(extra)
        return "\n".join(extras)

    def call_on_act_postprocess(self, agent_id: str, agent, result: dict, round_number: int) -> dict:
        """Call on_act_postprocess on all enabled traits, chain result through each."""
        for trait in self.get_traits(agent_id):
            returned = trait.on_act_postprocess(agent, result, round_number)
            if returned is not None:
                result = returned
        return result

    def call_on_round_end(self, agent_id: str, agent, round_number: int):
        """Call on_round_end on all enabled traits."""
        for trait in self.get_traits(agent_id):
            trait.on_round_end(agent, round_number)

    def call_on_simulation_end(self, agent_id: str, agent):
        """Call on_simulation_end on all enabled traits."""
        for trait in self.get_traits(agent_id):
            trait.on_simulation_end(agent)

    @property
    def available_traits(self) -> list[str]:
        return list(self._available.keys())


# ── Global registry ─────────────────────────────────
# Import trait modules here to auto-register them.
# This allows engine.py to just import the registry.

def create_default_registry() -> TraitRegistry:
    """Create a registry with all available traits registered."""
    from simulation.traits.confidence import ConfidenceTrait
    from simulation.traits.voting import VotingTrait
    from simulation.traits.skill_growth import SkillGrowthTrait
    from simulation.traits.knowledge_graph import KnowledgeTrait
    from simulation.traits.fact_check import FactCheckTrait
    from simulation.traits.devil_advocate import DevilAdvocateTrait
    from simulation.traits.emotional_state import EmotionalStateTrait
    from simulation.traits.decision_log import DecisionLogTrait
    from simulation.traits.stakeholder_pressure import StakeholderPressureTrait

    registry = TraitRegistry()
    registry.register("confidence", ConfidenceTrait)
    registry.register("voting", VotingTrait)
    registry.register("skill_growth", SkillGrowthTrait)
    registry.register("knowledge_graph", KnowledgeTrait)
    registry.register("fact_check", FactCheckTrait)
    registry.register("devil_advocate", DevilAdvocateTrait)
    registry.register("emotional_state", EmotionalStateTrait)
    registry.register("decision_log", DecisionLogTrait)
    registry.register("stakeholder_pressure", StakeholderPressureTrait)

    return registry

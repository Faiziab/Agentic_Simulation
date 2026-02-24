"""
Agent class for R&D Simulation.
Each agent has a personality, cognitive loop (perceive → recall → think → act → reflect → learn),
and communicates via the shared message board.
Agents can optionally use tools (web search, file I/O, calculator) via Gemini function calling.
"""

import json
import os
import yaml
from typing import Optional
from google import genai
from google.genai import types

from simulation.memory import MemoryStream, WorkingMemory
from simulation.communication import MessageBoard
from simulation.traits import TraitRegistry, create_default_registry
from simulation.tools import resolve_tools


class Agent:
    """
    An AI agent with personality, memory, and cognitive capabilities.
    Uses Google Gemini for reasoning via system instructions.
    """

    def __init__(
        self,
        agent_id: str,
        profile: dict,
        org_structure: dict,
        workspace_dir: str,
        model_name: str = "gemini-2.5-flash",
        trait_registry: TraitRegistry | None = None,
    ):
        self.agent_id = agent_id
        self.profile = profile
        self.name = profile["name"]
        self.title = profile["title"]
        self.level = profile["level"]
        self.department = profile.get("department")
        self.personality = profile["personality"]
        self.org_structure = org_structure
        self.model_name = model_name
        self.trait_registry = trait_registry
        self.workspace_dir = workspace_dir

        # Cognitive components
        self.working_memory = WorkingMemory()
        self.memory_stream = MemoryStream(agent_id, workspace_dir)
        self.last_reflection: Optional[str] = None
        self.deliverables: list[str] = []
        self.shared_knowledge = None  # Set by engine for team knowledge pool

        # Build system instruction from personality
        self.system_instruction = self._build_system_instruction()

        # ── Tool Integration ─────────────────────────
        tools_enabled = profile.get("tools_enabled", [])
        self.native_tools, self.custom_functions = resolve_tools(
            tools_enabled, workspace_dir
        )
        self.has_tools = bool(self.native_tools or self.custom_functions)
        self.tool_call_count = 0  # Track tool usage for stats
        self.last_tools_used: list[dict] = []  # Tools used in last think() call

        # Gemini client
        self.client = genai.Client()

    def _build_system_instruction(self) -> str:
        """Build a rich system instruction from the agent's personality profile."""
        p = self.personality
        traits = ", ".join(p["traits"])
        expertise = ", ".join(p["expertise"])
        quirks = "\n".join(f"  - {q}" for q in p["quirks"])

        # Build reporting context
        reporting = self.org_structure.get("reporting_lines", {}).get(self.agent_id, {})
        reports_to = reporting.get("reports_to", "nobody")
        direct_reports = reporting.get("direct_reports", [])

        # Get names for reporting context
        agents_config = self.org_structure.get("_agent_profiles", {})
        reports_to_name = ""
        if reports_to and reports_to in agents_config:
            reports_to_name = f"{agents_config[reports_to]['name']} ({agents_config[reports_to]['title']})"

        direct_report_names = []
        for dr_id in direct_reports:
            if dr_id in agents_config:
                direct_report_names.append(
                    f"{agents_config[dr_id]['name']} ({agents_config[dr_id]['title']})"
                )

        instruction = f"""You are {self.name}, {self.title} at TechNova Inc. R&D Division.

PERSONALITY & TRAITS:
{traits}

COMMUNICATION STYLE:
{p['communication_style']}

DECISION-MAKING APPROACH:
{p['decision_approach']}

AREAS OF EXPERTISE:
{expertise}

BEHAVIORAL QUIRKS (you naturally exhibit these):
{quirks}

ORGANIZATIONAL POSITION:
- Level: {self.level} ({'Executive' if self.level == 1 else 'Department Lead' if self.level == 2 else 'Senior IC' if self.level == 3 else 'Junior IC'})
- Department: {self.department or 'Oversees all departments'}
- Reports to: {reports_to_name or 'Board of Directors'}
- Direct reports: {', '.join(direct_report_names) if direct_report_names else 'None'}

IMPORTANT RULES:
1. ALWAYS stay in character as {self.name}. Your responses should reflect your personality, communication style, and quirks.
2. When delegating tasks, be specific about what you need and why.
3. When collaborating, reference specific points from other agents' work.
4. When you need information from another department, explicitly state WHO you need it from and WHY.
5. Format cross-department requests as: CROSS_DEPT_REQUEST: [target_agent_id] - [your question/request]
6. Format deliverables clearly with headers and structured content.
7. Be genuine — if you're uncertain, say so in your characteristic way.
8. Think step by step before providing your response.

RESPONSE FORMAT:
Always structure your response with these sections:
## Thinking
(Your internal reasoning process — what you're considering, weighing, analyzing)

## Action
(What you're doing — the work product, analysis, recommendation, or delegation)

## Cross-Department Requests
(If you need input from agents in other departments, list them here. If none, write "None needed")
Format: TARGET_AGENT: [agent_id] | REQUEST: [what you need and why]

## Status
(Brief status update: what you accomplished and what's pending)
"""
        return instruction

    def perceive(self, context: str, round_number: int):
        """
        Perceive phase: absorb new context and add to working memory.
        Calls trait on_perceive hooks for extra context injection.
        """
        # Trait hook: inject extra context
        if self.trait_registry:
            extra = self.trait_registry.call_on_perceive(
                self.agent_id, self, context, round_number
            )
            if extra:
                context = f"{context}\n{extra}"

        self.working_memory.add(context)
        self.memory_stream.add_memory(
            content=f"Received context: {context[:200]}...",
            memory_type="observation",
            importance=5,
            source="environment",
            round_number=round_number,
        )

    def recall(self, query: str = "", n: int = 8) -> str:
        """
        Recall phase: retrieve relevant memories for the current context.
        Uses semantic search when a query is provided.
        """
        relevant_memories = self.memory_stream.retrieve(query=query, n=n)
        reflections = self.memory_stream.get_reflections()[-3:]  # Last 3 reflections

        context_parts = [self.memory_stream.format_for_context(relevant_memories)]

        if reflections:
            context_parts.append("\nPREVIOUS REFLECTIONS & INSIGHTS:")
            for ref in reflections:
                context_parts.append(f"  💡 {ref.content[:300]}")

        # Include shared team knowledge if available
        if self.shared_knowledge:
            team_knowledge = self.shared_knowledge.query(query or "recent findings", n=3)
            if team_knowledge:
                context_parts.append("\nTEAM KNOWLEDGE POOL:")
                for entry in team_knowledge:
                    context_parts.append(f"  🔗 [{entry.get('from_agent', '?')}] {entry.get('content', '')[:200]}")

        return "\n".join(context_parts)

    def think(self, task: str, additional_context: str = "", round_number: int = 0) -> str:
        """
        Think phase: use the LLM to reason about the task.
        Combines system instruction (personality) with working memory and recalled memories.
        If the agent has tools enabled, passes them to Gemini for automatic function calling.
        """
        # Build the full context
        recalled = self.recall(query=task)
        working = self.working_memory.get_context()

        prompt_parts = []
        if working:
            prompt_parts.append(working)
        if recalled and recalled != "No relevant memories.":
            prompt_parts.append(recalled)
        if additional_context:
            prompt_parts.append(f"\nADDITIONAL CONTEXT:\n{additional_context}")

        prompt_parts.append(f"\n\nTASK:\n{task}")

        # Trait hook: inject extra prompt content
        if self.trait_registry:
            trait_extra = self.trait_registry.call_on_think_prompt(
                self.agent_id, self, task, round_number
            )
            if trait_extra:
                prompt_parts.append(trait_extra)

        full_prompt = "\n\n".join(prompt_parts)

        # ── Build Gemini config with tools ────────────
        config = {
            "system_instruction": self.system_instruction,
            "temperature": 0.8,
            "max_output_tokens": 4096,
        }

        if self.has_tools:
            # Combine native tools and custom functions
            tools_list = []
            tools_list.extend(self.native_tools)       # types.Tool objects
            tools_list.extend(self.custom_functions)    # Python callables
            config["tools"] = tools_list

        # Call Gemini API
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config=config,
            )
            result = response.text
            if result is None:
                result = f"[Agent {self.name}: LLM returned empty response — possible safety filter or overloaded API]"

            # Track token usage for cost dashboard
            self.last_token_usage = {}
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                um = response.usage_metadata
                self.last_token_usage = {
                    'input': getattr(um, 'prompt_token_count', 0) or 0,
                    'output': getattr(um, 'candidates_token_count', 0) or 0,
                }

            # Track tool usage if tools were called
            self.last_tools_used = []  # Reset for this call
            if self.has_tools and hasattr(response, 'candidates') and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate, 'content') and candidate.content:
                        for part in candidate.content.parts:
                            if hasattr(part, 'function_call') and part.function_call:
                                self.tool_call_count += 1
                                tool_name = part.function_call.name
                                self.last_tools_used.append({
                                    "tool": tool_name,
                                    "time": __import__('datetime').datetime.now().strftime("%H:%M:%S"),
                                })
                                self.memory_stream.add_memory(
                                    content=f"Used tool: {tool_name}",
                                    memory_type="action",
                                    importance=5,
                                    source="tool",
                                    round_number=round_number,
                                )

        except Exception as e:
            error_msg = str(e)
            # Graceful fallback: if model doesn't support function calling,
            # retry without tools and disable them for future calls
            if self.has_tools and ("unsupported" in error_msg.lower()
                                   or "INVALID_ARGUMENT" in error_msg
                                   or "function calling" in error_msg.lower()):
                # Disable tools for this agent permanently (model can't handle them)
                self.has_tools = False
                self.native_tools = []
                self.custom_functions = []
                config.pop("tools", None)
                try:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=full_prompt,
                        config=config,
                    )
                    result = response.text
                    if result is None:
                        result = f"[Agent {self.name}: LLM returned empty response on retry]"
                except Exception as e2:
                    result = f"[Agent {self.name} encountered an error: {str(e2)}]"
            else:
                result = f"[Agent {self.name} encountered an error: {error_msg}]"

        # Store the action in memory
        self.memory_stream.add_memory(
            content=f"Worked on task: {task[:150]}. Produced response.",
            memory_type="action",
            importance=6,
            source="self",
            round_number=round_number,
        )

        return result

    def act(self, task: str, context: str = "", round_number: int = 0) -> dict:
        """
        Full cognitive cycle: perceive → recall → think → learn.
        Returns structured output with the response and any cross-dept requests.
        """
        # Perceive
        self.perceive(task, round_number)

        # Think (includes recall internally)
        self.working_memory.set_task(task, round_number=round_number)
        response = self.think(task, additional_context=context, round_number=round_number)

        # Guard against None response (LLM safety filter, empty response, etc.)
        if response is None:
            response = f"[Agent {self.name} produced no output for this task]"

        # Learn — store the output
        self.memory_stream.add_memory(
            content=f"Completed work: {response[:300]}",
            memory_type="action",
            importance=7,
            source="self",
            round_number=round_number,
        )

        # Parse cross-department requests
        cross_dept_requests = self._parse_cross_dept_requests(response)

        # Build result
        result = {
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "agent_role": self.title,
            "department": self.department,
            "round": round_number,
            "task": task,
            "response": response,
            "cross_dept_requests": cross_dept_requests,
            "tools_used": list(self.last_tools_used),
        }

        self.deliverables.append(response)

        # Trait hook: post-process the result
        if self.trait_registry:
            result = self.trait_registry.call_on_act_postprocess(
                self.agent_id, self, result, round_number
            )

        return result

    def _parse_cross_dept_requests(self, response: str) -> list[dict]:
        """Parse cross-department requests from the agent's response."""
        requests = []
        for line in response.split("\n"):
            line = line.strip()
            if "TARGET_AGENT:" in line and "REQUEST:" in line:
                try:
                    parts = line.split("|")
                    target = parts[0].split("TARGET_AGENT:")[1].strip()
                    request = parts[1].split("REQUEST:")[1].strip()
                    requests.append({"target": target, "request": request})
                except (IndexError, ValueError):
                    continue
            elif line.startswith("CROSS_DEPT_REQUEST:"):
                try:
                    rest = line[len("CROSS_DEPT_REQUEST:"):].strip()
                    if " - " in rest:
                        target, request = rest.split(" - ", 1)
                        requests.append({"target": target.strip(), "request": request.strip()})
                except (ValueError):
                    continue
        return requests

    def respond_to_message(self, message_content: str, from_agent: str, round_number: int = 0) -> str:
        """Respond to a message from another agent."""
        self.memory_stream.add_memory(
            content=f"Received message from {from_agent}: {message_content[:200]}",
            memory_type="communication",
            importance=6,
            related_agent=from_agent,
            round_number=round_number,
        )

        task = f"Respond to this message from {from_agent}: {message_content}"
        response = self.think(task, round_number=round_number)

        self.memory_stream.add_memory(
            content=f"Responded to {from_agent}: {response[:200]}",
            memory_type="communication",
            importance=5,
            related_agent=from_agent,
            round_number=round_number,
        )

        return response

    def get_memory_summary(self) -> str:
        """Get a summary of the agent's memory state."""
        total = len(self.memory_stream)
        by_type = {}
        for m in self.memory_stream.memories:
            by_type[m.memory_type] = by_type.get(m.memory_type, 0) + 1
        reflections = len(self.memory_stream.get_reflections())

        return (
            f"{self.name}: {total} memories "
            f"({', '.join(f'{k}:{v}' for k, v in by_type.items())}), "
            f"{reflections} reflections"
        )


# Default model tier mapping: hierarchy level → Gemini model
DEFAULT_MODEL_MAP = {
    1: "gemini-3-pro-preview",       # VP / Executive — deepest reasoning
    2: "gemini-3-flash-preview",     # Department Leads — fast + capable
    3: "gemini-3-flash-preview",     # Senior ICs — fast + capable
    4: "gemini-3-flash-preview",     # Junior ICs — fast
}

# All default trait names
ALL_TRAITS = ["confidence", "voting", "skill_growth", "knowledge_graph", "fact_check"]


def load_agents(
    config_dir: str,
    workspace_dir: str,
    model_name: str = "gemini-3-flash-preview",
    model_map: dict[int, str] | None = None,
) -> tuple[dict[str, "Agent"], TraitRegistry]:
    """Load all agents from config files.

    Args:
        config_dir: Path to config directory
        workspace_dir: Path to workspace directory
        model_name: Default model (used if no model_map or level not in map)
        model_map: Optional dict mapping hierarchy level (int) to model name.

    Returns:
        Tuple of (agents dict, trait_registry)
    """
    # Load configs
    with open(os.path.join(config_dir, "org_structure.yaml"), "r", encoding="utf-8") as f:
        org_structure = yaml.safe_load(f)

    with open(os.path.join(config_dir, "agent_profiles.yaml"), "r", encoding="utf-8") as f:
        profiles = yaml.safe_load(f)

    # Inject agent profiles into org structure for cross-referencing
    org_structure["_agent_profiles"] = profiles["agents"]

    # Create shared trait registry
    registry = create_default_registry()

    agents = {}
    for agent_id, profile in profiles["agents"].items():
        # Determine model for this agent based on hierarchy level
        agent_level = profile.get("level", 4)
        if model_map:
            agent_model = model_map.get(agent_level, model_name)
        else:
            agent_model = model_name

        agents[agent_id] = Agent(
            agent_id=agent_id,
            profile=profile,
            org_structure=org_structure,
            workspace_dir=workspace_dir,
            model_name=agent_model,
            trait_registry=registry,
        )

        # Enable traits for this agent based on profile config
        enabled_traits = profile.get("traits_enabled", ALL_TRAITS)
        registry.enable(agent_id, enabled_traits, workspace_dir=workspace_dir)

    return agents, registry


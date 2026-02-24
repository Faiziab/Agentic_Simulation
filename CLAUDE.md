# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Simulation

```bash
# Basic run
python run_simulation.py --prompt "Your strategic initiative here"

# With verbose terminal output
python run_simulation.py --prompt "..." --verbose

# With real-time NiceGUI dashboard at http://127.0.0.1:8420
python run_simulation.py --prompt "..." --live

# Use a specific Gemini model
python run_simulation.py --prompt "..." --model gemini-2.5-flash

# Use tiered models (Pro for VP, Flash for lower levels)
python run_simulation.py --prompt "..." --tiered-models

# List all previous runs
python run_simulation.py --list-runs
```

**Required environment variable:** `GOOGLE_API_KEY` (place in `.env` file or export).

**Install dependencies:** `pip install -r requirements.txt` (Python 3.10+)

## Architecture Overview

This is a multi-agent simulation of an R&D department hierarchy. **9 agents** across 4 levels all run on Google Gemini via the `google-genai` SDK.

### Agent Hierarchy
- **Level 1:** VP of R&D (Sarah Chen) — orchestrates and produces final synthesis
- **Level 2:** Department Leads (Research, Engineering, Product) — plan and synthesize
- **Level 3:** Senior ICs (Priya, Marcus, Lena) — execute and deliver
- **Level 4:** Junior ICs (Tom, Zara) — execute assigned tasks

### Core Data Flow
1. `run_simulation.py` parses CLI args → creates a unique `runs/<timestamp>_<slug>/` directory → instantiates `SimulationEngine`
2. `SimulationEngine` (`simulation/engine.py`) reads `config/pipeline.yaml` and executes each step sequentially, calling round methods (`_round_1_*` through `_round_7_*`)
3. Each round calls `agent.act()` or `agent.think()` on `Agent` instances (`simulation/agents.py`), which call Gemini with the agent's system instruction, memory context, and any trait-injected prompt additions
4. Agents communicate via `MessageBoard` (`simulation/communication.py`) — task assignments flow down the hierarchy, deliverables flow up
5. After the simulation, `ReportGenerator` (`simulation/reporter.py`) produces markdown reports in the run directory

### Key Relationships
- **`SimulationEngine`** owns all agents, the `MessageBoard`, `TraitRegistry`, `KnowledgeManager`, and optional `DashboardState`
- **`Agent`** holds a `MemoryStream`, `WorkingMemory`, `TraitRegistry` reference, and resolved tool callables
- **`TraitRegistry`** is a plugin system — it dispatches lifecycle hooks (`on_perceive`, `on_think_prompt`, `on_act_postprocess`, `on_round_end`, `on_simulation_end`) to each agent's enabled traits
- **`SharedKnowledge`** / `KnowledgeManager` provides department-level semantic memory (embeddings via `gemini-embedding-001`); agents auto-publish high-importance reflections to it at end of Round 6
- **`ChatChainRunner`** (`simulation/chat_chains.py`) handles multi-turn back-and-forth exchanges during Round 4 (cross-department collaboration)

### Concurrency
In `--live` mode, Rounds 2, 3, 5, and 6 run agents concurrently using `ThreadPoolExecutor`. In standard mode, agents run sequentially.

## Configuration Files

| File | What to Edit |
|------|-------------|
| `config/agent_profiles.yaml` | Agent personalities, `traits_enabled`, `tools_enabled` per agent |
| `config/org_structure.yaml` | Reporting lines, `direct_reports` hierarchy |
| `config/pipeline.yaml` | Round order, quality gate settings, auto-skip rules |

## Extending the System

### Adding a New Trait
1. Create `simulation/traits/my_trait.py` implementing `BaseTrait` — override only the lifecycle hooks you need
2. Register it in `create_default_registry()` in `simulation/traits/__init__.py`
3. Enable it per agent in `config/agent_profiles.yaml` under `traits_enabled`

### Adding a New Tool
1. Create a function in `simulation/tools/` with a Google-style docstring (Gemini uses it for function calling)
2. Add a case for it in `resolve_tools()` in `simulation/tools/__init__.py`
3. Enable it per agent in `config/agent_profiles.yaml` under `tools_enabled`

### Adding/Removing Pipeline Steps
Edit `config/pipeline.yaml`. Each step maps `method` to an engine method name. Set `auto_skip: true` if the step should be skipped when there's no applicable work. Set `pass_prompt: true` to forward the original prompt string.

## Output Structure

Each simulation run saves to `runs/<timestamp>_<slug>/`:
```
reports/final_synthesis.md      # VP's executive summary
reports/simulation_report.md    # Full multi-round report
reports/trait_reports.md        # Confidence, voting, skill growth, etc.
logs/activity_log.jsonl         # Every agent action with metadata
logs/communication_log.jsonl    # All inter-agent messages
memory/<agent_id>.jsonl         # Per-agent memory streams (JSONL)
reflections/<agent_id>_reflection.md
departments/<dept>/department_output.md
shared/task_board.md            # VP's strategic decomposition
knowledge/<dept>.jsonl          # Shared department knowledge pools
```

The `workspace/` directory at the repo root mirrors this structure and reflects the most recent run's live state during execution.

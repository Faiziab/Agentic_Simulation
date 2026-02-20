# 🏢 R&D Department Multi-Agent Simulation — Project Guide

A complete guide on how to set up, configure, run, and customize the multi-agent R&D simulation.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [CLI Reference](#cli-reference)
5. [How the Simulation Works](#how-the-simulation-works)
6. [Agent Configuration](#agent-configuration)
7. [Trait System (Addons)](#trait-system-addons)
8. [Tiered Models](#tiered-models)
9. [Understanding the Output](#understanding-the-output)
10. [Managing Past Runs](#managing-past-runs)
11. [Adding New Agents](#adding-new-agents)
12. [Project Structure](#project-structure)

---

## Prerequisites

- **Python 3.10+**
- **Google Gemini API Key** — Get one free at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

---

## Installation

```powershell
# 1. Clone or navigate to the project
cd d:\Testing\Agentic_testing

# 2. Create a virtual environment (recommended)
python -m venv venv
.\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up your API key (choose one method)

# Method A: Create a .env file (recommended)
echo GOOGLE_API_KEY=your-key-here > .env

# Method B: Set environment variable directly
$env:GOOGLE_API_KEY = "your-key-here"
```

### Dependencies

| Package | Purpose |
|---------|---------|
| `google-genai` | Gemini API client |
| `pyyaml` | YAML config parsing |
| `rich` | Pretty terminal output |
| `python-dotenv` | Load `.env` files |

---

## Quick Start

```powershell
# Basic run
python run_simulation.py --prompt "Investigate adding AI-powered search to our document management product"

# With verbose output (shows full agent responses)
python run_simulation.py --prompt "Evaluate building a recommendation engine" --verbose

# With tiered models (Pro for VP, Flash for rest)
python run_simulation.py --prompt "Design a real-time analytics dashboard" --tiered-models --verbose
```

The simulation takes approximately **2-5 minutes** and makes ~30-50 API calls.

---

## CLI Reference

```
python run_simulation.py [OPTIONS]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--prompt "..."` | **Required.** The strategic initiative for the R&D team to process | — |
| `--verbose` | Show full agent responses in the terminal | Off |
| `--model MODEL` | Gemini model name for all agents | `gemini-3-flash-preview` |
| `--tiered-models` | Use different models per hierarchy level | Off |
| `--list-runs` | List all previous simulation runs and exit | — |

### Examples

```powershell
# Standard run
python run_simulation.py --prompt "Should we build an AI chatbot for customer support?"

# Use a specific model for all agents
python run_simulation.py --prompt "..." --model gemini-2.0-flash

# Use tiered models (VP gets Pro, others get Flash)
python run_simulation.py --prompt "..." --tiered-models

# Verbose mode — see everything agents produce
python run_simulation.py --prompt "..." --verbose

# Review past simulation runs
python run_simulation.py --list-runs
```

---

## How the Simulation Works

The simulation runs through **7 rounds** plus 2 trait-driven bonus phases:

```
Round 1  →  Round 2  →  Round 3  →  🔍 Fact-Check  →  Round 4  →  Round 5  →  🗳️ Voting  →  Round 6  →  Round 7
```

| Round | Name | What Happens |
|-------|------|-------------|
| **1** | Strategic Decomposition | VP (Sarah) receives your prompt and breaks it into department objectives |
| **2** | Department Planning | Leads (James, Maya, Alex) plan tasks and assign work to their ICs |
| **3** | Execution | ICs (Priya, Marcus, Lena, Tom, Zara) do the actual research/engineering/product work |
| **3.5** | 🔍 Fact-Check | Leads review IC deliverables for unsupported claims (trait-driven) |
| **4** | Cross-Dept Collaboration | Agents from different departments have **multi-turn chat chain** conversations |
| **5** | Refinement | Leads review all deliverables and provide synthesis/feedback |
| **5.5** | 🗳️ Voting | VP + Leads vote on whether to proceed with the proposed approach |
| **6** | Reflection & Synthesis | All agents reflect on their work, generate insights |
| **7** | Final Report | VP produces the executive summary and final recommendation |

### Agent Hierarchy

```
Level 1 (VP)         Dr. Sarah Chen — VP of R&D
                     ├──────────────────┼──────────────────┐
Level 2 (Leads)      Dr. James Okafor   Maya Rodriguez      Alex Kim
                     Research Lead       Engineering Lead     Product Lead
                     ├──────────        ├──────────          ├──────────
Level 3 (Sr. ICs)    Dr. Priya Sharma   Marcus Webb          Lena Voronova
                     Sr. Research Sci.  Sr. SW Engineer      UX Researcher
                     ├──────────        ├──────────
Level 4 (Jr. ICs)    Tom Park           Zara Ahmed
                     Jr. Research Anl.  Jr. SW Engineer
```

Each agent has:
- **Distinct personality** — unique traits, quirks, communication style
- **Memory streams** — working, episodic, and semantic memory
- **Reflection** — self-assessment and insight generation
- **Configurable traits** — modular addon features (see below)

---

## Agent Configuration

All agent profiles live in `config/agent_profiles.yaml`. Each profile contains:

```yaml
sarah_chen:
  name: "Dr. Sarah Chen"
  title: "VP of Research & Development"
  level: 1                    # Hierarchy level (1=VP, 2=Lead, 3=Sr IC, 4=Jr IC)
  department: null            # null for VP, "research"/"engineering"/"product" for others
  personality:
    traits:                   # List of personality descriptors
      - "Strategic thinker"
      - "Decisive but inclusive"
    communication_style: >    # How this agent writes/speaks
      Concise and structured. Uses numbered lists...
    decision_approach: >      # How this agent makes decisions
      Weighs innovation potential against business reality...
    expertise:                # Domain expertise
      - "R&D strategy"
      - "Cross-functional alignment"
    quirks:                   # Behavioral quirks that make responses unique
      - "Always asks 'What's the biggest risk?'"
  traits_enabled:             # Which addon modules are active for this agent
    - confidence
    - voting
    - skill_growth
    - knowledge_graph
    - fact_check
```

The organizational structure (reporting lines, departments) is in `config/org_structure.yaml`.

---

## Trait System (Addons)

The simulation uses a **modular trait plugin system**. Each trait is a standalone feature that can be independently enabled or disabled per agent.

### Available Traits

| Trait | Key | What It Does |
|-------|-----|-------------|
| **Confidence Scores** | `confidence` | Agents rate their confidence (1-10) on every output. Low scores trigger reviews. |
| **Voting & Consensus** | `voting` | VP + Leads vote on the final recommendation after Round 5. Votes are weighted by hierarchy. |
| **Skill Growth** | `skill_growth` | Agents earn XP in domains (AI/ML, architecture, etc.) based on their work. XP persists across runs. |
| **Knowledge Graph** | `knowledge_graph` | Tracks what each agent knows. Enables smart "who should I ask?" routing. |
| **Hallucination Check** | `fact_check` | Leads review IC deliverables and flag unsupported claims. |

### Default Trait Assignments

| Role Level | Traits Enabled |
|-----------|----------------|
| **VP** (Level 1) | All 5 traits |
| **Department Leads** (Level 2) | All 5 traits |
| **Senior ICs** (Level 3) | `confidence`, `skill_growth`, `knowledge_graph` |
| **Junior ICs** (Level 4) | `confidence`, `skill_growth` |

### Customizing Traits

Edit an agent's `traits_enabled` list in `config/agent_profiles.yaml`:

```yaml
# Give a junior IC access to the knowledge graph
tom_park:
  traits_enabled:
    - confidence
    - skill_growth
    - knowledge_graph  # Added!

# Remove voting from a lead (they won't participate in votes)
james_okafor:
  traits_enabled:
    - confidence
    - skill_growth
    - knowledge_graph
    - fact_check
    # voting removed — James won't vote
```

### Trait Reports

After each run, trait data is saved to `reports/trait_reports.md` inside the run directory. This includes:
- Confidence score heatmap
- Voting session results and dissenting opinions
- Knowledge graph (who knows what)
- Skill growth XP progress bars
- Fact-check results (verified vs flagged claims)

---

## Tiered Models

By default, all agents use the same Gemini model. With `--tiered-models`, each hierarchy level gets a different model:

| Level | Role | Model | Why |
|-------|------|-------|-----|
| 1 | VP (Sarah) | `gemini-3-pro-preview` | Deepest reasoning for executive decisions |
| 2 | Leads (James, Maya, Alex) | `gemini-3-flash-preview` | Fast + capable for planning |
| 3 | Senior ICs (Priya, Marcus, Lena) | `gemini-3-flash-preview` | Fast for execution work |
| 4 | Junior ICs (Tom, Zara) | `gemini-3-flash-preview` | Fast for junior tasks |

```powershell
# Enable tiered models
python run_simulation.py --prompt "..." --tiered-models

# Override the non-VP model while keeping Pro for VP
python run_simulation.py --prompt "..." --tiered-models --model gemini-2.0-flash
```

To change the default model mapping, edit `DEFAULT_MODEL_MAP` in `simulation/agents.py`:

```python
DEFAULT_MODEL_MAP = {
    1: "gemini-3-pro-preview",       # VP
    2: "gemini-3-flash-preview",     # Leads
    3: "gemini-3-flash-preview",     # Senior ICs
    4: "gemini-3-flash-preview",     # Junior ICs
}
```

---

## Understanding the Output

Each simulation run is saved to a **timestamped directory** under `runs/`:

```
runs/
└── 2026-02-19_12-30_ai-powered-search-document/
    ├── run_metadata.json          # Run configuration and timestamp
    ├── reports/
    │   ├── final_synthesis.md     # VP's executive summary (the main output)
    │   ├── simulation_report.md   # Full detailed report with all agent outputs
    │   ├── chat_chains.md         # Multi-turn conversation transcripts
    │   └── trait_reports.md       # Confidence, voting, skills, knowledge, fact-checks
    ├── logs/
    │   ├── activity_log.jsonl     # Every agent action with metadata
    │   └── communication_log.jsonl # All inter-agent messages
    ├── memory/
    │   ├── sarah_chen.jsonl       # Per-agent memory streams
    │   ├── james_okafor.jsonl
    │   └── ...
    └── reflections/
        ├── sarah_chen.md          # Per-agent reflection outputs
        ├── james_okafor.md
        └── ...
```

### Key Files to Read

| Priority | File  | What You'll Find |
|----------|-------|-----------------|
| ⭐ 1st | `reports/final_synthesis.md` | The VP's executive recommendation — **start here** |
| 2nd | `reports/simulation_report.md` | Full report with all department analyses |
| 3rd | `reports/trait_reports.md` | Confidence scores, voting results, skill growth |
| 4th | `reports/chat_chains.md` | Cross-department conversation transcripts |

---

## Managing Past Runs

```powershell
# List all past simulations
python run_simulation.py --list-runs
```

This shows a table of all runs with timestamps, prompts, and models used. Each run is preserved in its own directory under `runs/`.

---

## Adding New Agents

To add a new agent to the simulation:

### Step 1: Add to `config/agent_profiles.yaml`

```yaml
  new_agent_id:
    name: "Agent Name"
    title: "Job Title"
    level: 3                     # 1=VP, 2=Lead, 3=Sr IC, 4=Jr IC
    department: "engineering"    # research, engineering, or product
    personality:
      traits:
        - "Key trait 1"
        - "Key trait 2"
      communication_style: >
        How this agent communicates...
      decision_approach: >
        How this agent makes decisions...
      expertise:
        - "Skill 1"
        - "Skill 2"
      quirks:
        - "Behavioral quirk 1"
    traits_enabled:              # Pick which addon modules to enable
      - confidence
      - skill_growth
      - knowledge_graph
```

### Step 2: Add reporting lines in `config/org_structure.yaml`

```yaml
reporting_lines:
  new_agent_id:
    reports_to: maya_rodriguez   # Their manager's ID
    direct_reports: []           # IDs of people they manage
```

Also add them to their manager's `direct_reports` list.

### Step 3: Run the simulation — the new agent will automatically participate!

---

## Project Structure

```
Agentic_testing/
├── .env                          # API key (GOOGLE_API_KEY=...)
├── requirements.txt              # Python dependencies
├── run_simulation.py             # CLI entry point
├── README.md                     # Quick overview
│
├── config/
│   ├── org_structure.yaml        # Hierarchy, departments, reporting lines
│   └── agent_profiles.yaml       # Personality profiles + trait config
│
├── simulation/
│   ├── __init__.py
│   ├── agents.py                 # Agent class with cognitive loop
│   ├── engine.py                 # 7-round simulation orchestrator
│   ├── communication.py          # MessageBoard for inter-agent messaging
│   ├── memory.py                 # Memory streams (working, episodic, semantic)
│   ├── reflection.py             # Reflection engine + insight generation
│   ├── chat_chains.py            # Multi-turn structured dialogues
│   ├── logger.py                 # JSONL logging + rich terminal output
│   ├── reporter.py               # Final report generator
│   └── traits/                   # Modular addon trait system
│       ├── __init__.py           # BaseTrait + TraitRegistry framework
│       ├── confidence.py         # Confidence scoring (1-10)
│       ├── voting.py             # Weighted voting sessions
│       ├── skill_growth.py       # XP tracking across domains
│       ├── knowledge_graph.py    # Agent-topic knowledge graph
│       └── fact_check.py         # Hallucination detection
│
├── docs/
│   ├── PROJECT_GUIDE.md          # This file
│   └── addon_modules.md          # Catalog of all possible addons
│
└── runs/                         # Auto-generated simulation outputs
    └── YYYY-MM-DD_HH-MM_slug/   # One directory per run
```

---

## Tips & Best Practices

1. **Start with `--verbose`** on your first run to see what each agent produces
2. **Use specific prompts** — "Investigate adding AI-powered search to our enterprise document management product" produces much better results than "add search"
3. **Use `--tiered-models`** for best quality output — the VP gets Pro-level reasoning
4. **Check `trait_reports.md`** to see confidence levels and voting outcomes
5. **Run multiple simulations** with the same prompt to see different agent dynamics
6. **Customize agent traits** in the YAML to experiment with different team configurations

---

*Built with Google Gemini, Rich, and a lot of YAML.* 🚀

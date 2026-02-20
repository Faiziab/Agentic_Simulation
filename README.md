# 🏢 R&D Department Multi-Agent Simulation

A Python-based simulation engine that replicates how a real R&D department processes strategic initiatives through a hierarchy of AI agents with distinct personalities, memory, tool use, and higher-level thinking.

## Architecture

```
                          ┌─────────────────────┐
           Level 1        │  VP of R&D (Sarah)  │
                          └──────────┬──────────┘
                    ┌────────────────┼────────────────┐
           ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
Level 2    │Research Lead │ │Engineering   │ │Product Lead  │
           │  (James)     │ │Lead (Maya)   │ │  (Alex)      │
           └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
           ┌──────┴───────┐ ┌──────┴───────┐ ┌──────┴───────┐
Level 3    │Sr. Researcher│ │Sr. Engineer  │ │UX Researcher │
           │  (Priya)     │ │  (Marcus)    │ │  (Lena)      │
           └──────┬───────┘ └──────┬───────┘ └──────────────┘
           ┌──────┴───────┐ ┌──────┴───────┐
Level 4    │Jr. Researcher│ │Jr. Engineer  │
           │  (Tom)       │ │  (Zara)      │
           └──────────────┘ └──────────────┘
```

**9 agents** across 4 hierarchy levels, each with:
- 🧠 **Memory Streams** — working, episodic, and semantic
- 🔄 **Reflection** — periodic self-assessment and insight generation
- 💬 **Open Communication** — direct messages, broadcast, cross-department
- 🎭 **Distinct Personalities** — unique traits, quirks, and communication styles
- 🛠️ **Tool Use** — web search, file I/O, calculations via Gemini function calling
- 📊 **Trait System** — confidence tracking, voting, skill growth, knowledge graphs, fact-checking

---

## Quick Start

### Prerequisites

- **Python 3.10+**
- **Google API Key** with Gemini access
- **Dependencies**: `google-genai`, `rich`, `pyyaml`

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd Agentic_testing

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up API key
# PowerShell
$env:GOOGLE_API_KEY = "your-key-here"

# Linux/Mac
export GOOGLE_API_KEY="your-key-here"
```

### Running a Simulation

```bash
# Basic run
python run_simulation.py --prompt "Investigate the feasibility of adding an AI-powered search feature to our enterprise document management product"

# With verbose output (full agent responses in terminal)
python run_simulation.py --prompt "..." --verbose

# With live tmux-style dashboard (real-time agent activity)
python run_simulation.py --prompt "..." --live

# With a custom model
python run_simulation.py --prompt "..." --model gemini-2.5-flash-preview-05-20

# With per-level model mapping (different models for different agent levels)
python run_simulation.py --prompt "..." --model-map '{"1": "gemini-2.5-pro-preview-05-06", "2": "gemini-2.5-flash-preview-05-20", "3": "gemini-2.0-flash", "4": "gemini-2.0-flash"}'
```

---

## CLI Reference

| Flag | Description | Default |
|------|-------------|---------|
| `--prompt` | The strategic initiative prompt (required) | — |
| `--verbose` | Show full agent responses in terminal | `False` |
| `--live` | Enable real-time tmux-style dashboard | `False` |
| `--model` | Gemini model name for all agents | `gemini-2.0-flash` |
| `--model-map` | JSON mapping agent levels to models | `None` |
| `--config-dir` | Directory with YAML config files | `./config` |
| `--workspace-dir` | Output workspace directory | `./workspace` |

---

## Simulation Pipeline

The simulation runs through a configurable pipeline defined in `config/pipeline.yaml`. Each step is either a standard round, a hook, or a quality gate.

| Step | Type | What Happens |
|------|------|-------------|
| 1. Strategic Decomposition | Round | VP decomposes prompt into department objectives |
| 2. Department Planning | Round | Leads plan tasks and assign to their teams |
| 3. Execution | Round | ICs work on assigned tasks (using tools if enabled) |
| 3.5 Fact-Check Pass | Hook | Agents with fact-check trait verify claims (auto-skip if none) |
| 4. Cross-Dept Collaboration | Round | Agents answer questions from other depts (auto-skip if empty) |
| 5. Refinement | Round | Leads review and synthesize team outputs |
| ⚡ Quality Gate | Gate | VP evaluates quality — can iterate back to step 3 (max 2x) |
| 5.5 Voting Session | Hook | Agents vote on proposals (auto-skip if no voting trait) |
| 6. Reflection & Synthesis | Round | All agents reflect, leads generate insights |
| 7. Final Report | Round | VP produces executive synthesis |

### Pipeline Features

- **Auto-skip**: Steps with `auto_skip: true` are skipped when there's no applicable work (e.g., no cross-department requests, no fact-check traits enabled)
- **Quality Gate**: The VP evaluates deliverables after Round 5. If quality is insufficient, the pipeline loops back to Execution (Round 3) for another iteration, up to a configurable maximum
- **Configurable**: Edit `config/pipeline.yaml` to reorder, add, or remove steps

---

## Agent Tools

Agents can use real tools during execution, powered by Gemini's function calling. Tools are assigned per agent in `config/agent_profiles.yaml`.

| Tool | Description | Assigned To |
|------|-------------|-------------|
| `google_search` | Google Search grounding — agents access live web data | All agents |
| `read_workspace_file` | Read files from the shared workspace | VP, leads, senior engineers |
| `write_workspace_file` | Write deliverables to workspace | VP, leads |
| `list_workspace_files` | List available workspace files | VP, leads |
| `calculator` | Safe math evaluation (arithmetic, sqrt, log, etc.) | Leads, ICs |

### How Tool Use Works

1. Agent receives a task from the pipeline
2. Gemini model decides whether to use tools based on the task context
3. If a tool call is needed, the SDK **automatically executes** the function and feeds the result back
4. The final response incorporates tool outputs
5. Tool usage is logged to the agent's memory stream

### Adding Custom Tools

1. Create a new file in `simulation/tools/` with your function:
   ```python
   def my_tool(param: str) -> str:
       """Description of what this tool does.

       Args:
           param: Description of the parameter.

       Returns:
           Result as a string.
       """
       return "result"
   ```

2. Register it in `simulation/tools/__init__.py`:
   ```python
   elif name == "my_tool":
       custom_functions.append(my_tool)
   ```

3. Assign it to agents in `config/agent_profiles.yaml`:
   ```yaml
   agent_name:
     tools_enabled:
       - my_tool
   ```

---

## Trait System

Traits are modular capabilities that plug into an agent's cognitive loop. Enable/disable per agent in YAML.

| Trait | Description |
|-------|-------------|
| `confidence` | Tracks confidence levels in outputs, adds certainty qualifiers |
| `voting` | Enables agents to vote on proposals during the voting session |
| `skill_growth` | Agents develop skills over time based on tasks completed |
| `knowledge_graph` | Builds a per-agent knowledge graph of concepts and relationships |
| `fact_check` | Cross-validates claims against other agents' outputs |

---

## Configuration Files

| File | Purpose |
|------|---------|
| `config/agent_profiles.yaml` | Agent personalities, traits, tools, hierarchy levels |
| `config/org_structure.yaml` | Reporting lines, department structures, cross-dept channels |
| `config/pipeline.yaml` | Simulation round sequence, auto-skip rules, quality gates |

### Customizing Agent Profiles

Each agent profile in `config/agent_profiles.yaml` contains:

```yaml
agent_id:
  name: "Agent Name"
  title: "Job Title"
  level: 2                    # 1=VP, 2=Lead, 3=Senior IC, 4=Junior IC
  department: "research"      # Department name
  personality:
    traits: [...]             # Personality traits
    communication_style: "..."
    decision_approach: "..."
    expertise: [...]
    quirks: [...]
  traits_enabled:             # Modular trait plugins
    - confidence
    - voting
  tools_enabled:              # Tools this agent can use
    - google_search
    - calculator
```

---

## Output Files

| File | Description |
|------|-------------|
| `workspace/reports/final_synthesis.md` | VP's executive summary |
| `workspace/reports/simulation_report.md` | Full simulation report with all rounds |
| `workspace/logs/activity_log.jsonl` | Every agent action with metadata |
| `workspace/logs/communication_log.jsonl` | All inter-agent messages |
| `workspace/memory/*.jsonl` | Per-agent memory streams |
| `workspace/reflections/*.md` | Per-agent reflection outputs |
| `workspace/departments/<dept>/` | Department-specific workspace files |

---

## Project Structure

```
Agentic_testing/
├── run_simulation.py           # CLI entry point
├── config/
│   ├── agent_profiles.yaml     # Agent personalities, traits, tools
│   ├── org_structure.yaml      # Org chart, reporting lines
│   └── pipeline.yaml           # Simulation round pipeline config
├── simulation/
│   ├── agents.py               # Agent class with cognitive loop + tool integration
│   ├── engine.py               # Simulation orchestrator (pipeline, quality gates)
│   ├── communication.py        # Message board system
│   ├── memory.py               # Memory stream (working, episodic, semantic)
│   ├── reflection.py           # Self-reflection engine
│   ├── logger.py               # Structured logging
│   ├── reporter.py             # Report generation
│   ├── chat_chains.py          # Multi-turn chat chains
│   ├── dashboard.py            # Live tmux-style terminal dashboard
│   └── tools/                  # Agent tool system
│       ├── __init__.py         # Tool registry and resolution
│       ├── file_tools.py       # Workspace file read/write/list
│       └── calculator.py       # Safe math evaluation
├── simulation/traits/          # Modular trait plugins
│   ├── __init__.py             # Trait base class and registry
│   ├── confidence.py           # Confidence tracking
│   ├── voting.py               # Voting system
│   ├── skill_growth.py         # Skill development
│   ├── knowledge_graph.py      # Knowledge graph building
│   └── fact_check.py           # Fact verification
├── workspace/                  # Simulation output (created at runtime)
└── requirements.txt
```

---

## Requirements

- Python 3.10+
- `GOOGLE_API_KEY` environment variable
- ~30-50+ API calls per simulation (~2-5 min runtime)
- Additional calls if quality gate triggers re-iteration

# Agentic Simulation — Improvement Guide

Based on web research (2025–2026) and deep codebase analysis.

---

## 1. Memory System — Highest Impact Area

**Embedding volume is your biggest hidden bottleneck.** Every `add_memory()` call in `simulation/memory.py` fires a separate Gemini embedding API call. With 9 agents × 7 rounds × ~10 memories/round, you're making ~630 embedding API calls per simulation.

**Fix: Batch embeddings at round boundaries**
```python
# Buffer memories without embedding during the round,
# then in engine._call_round_end_hooks() flush the batch:
client.models.embed_content(
    model="gemini-embedding-001",
    contents=["text1", "text2", ..., "textN"]  # up to 100 per batch
)
```

**Fix: LRU cache for repeated text** (system instructions, VP decomposition, task templates are embedded repeatedly):
```python
@functools.lru_cache(maxsize=512)
def _get_embedding_cached(text_hash, text):
    ...

def get_embedding(text: str) -> list[float]:
    h = hashlib.md5(text[:2000].encode()).hexdigest()
    return list(_get_embedding_cached(h, text))
```

**Fix: Skip embeddings for unimportant memories** — memories with `importance <= 3` are rarely retrieved semantically; skip their embedding calls entirely.

**Fix: LLM-assessed importance** — currently `agents.py` uses hard-coded constants (always `importance=5` or `importance=6`). The Stanford Generative Agents approach is to ask the model to score: *"On a scale of 1–10, how important is this event?"* — letting it calibrate based on actual content.

**Fix: Ebbinghaus forgetting curve** — replace the current linear recency score in `retrieve()` with:
```python
recency = 0.7 ** (current_round - mem.round_number)  # exponential decay per round
```
Research shows this better mirrors human memory consolidation.
- Source: [Synapse: Episodic-Semantic Memory](https://arxiv.org/html/2601.02744v1) (95% token reduction, +23% multi-hop reasoning)

**New: A-MEM dynamic memory linking** — when a new memory is stored, automatically find related past memories and create bidirectional links. This enables much richer contextual recall than the current flat list.
- Source: [A-MEM: Agentic Memory for LLM Agents](https://arxiv.org/abs/2502.12110)

---

## 2. Structured Output — Low Effort, Eliminates Fragile Parsing

Currently `_parse_cross_dept_requests()` in `agents.py` uses regex on free-text sections like `## Cross-Department Requests`. This breaks when the LLM formats things differently.

**Fix: Use Gemini's `response_schema`**
```python
import typing_extensions

class AgentOutput(typing_extensions.TypedDict):
    thinking: str
    action: str
    cross_dept_requests: list[dict]
    status: str

config = types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=AgentOutput,
    ...
)
```
- Source: [Gemini Structured Output](https://ai.google.dev/gemini-api/docs/structured-output)

---

## 3. Tool Loop — Currently Broken for Multi-Turn Tool Use

`think()` in `agents.py` makes a single `generate_content` call. When Gemini returns a `function_call` part (not text), the code detects it post-hoc but **doesn't continue the conversation**. The correct agentic pattern:

```python
while True:
    response = client.models.generate_content(...)
    if has_function_calls(response):
        results = [execute_tool(fc) for fc in get_function_calls(response)]
        contents.append({"role": "tool", "parts": results})
        # loop back — let the model see the tool result and continue
    else:
        return response.text
```

Also: enable **dynamic retrieval** on `google_search` so it only fires when the model's confidence is low — saving calls on topics agents already know:
```python
types.Tool(google_search=types.GoogleSearch(
    dynamic_retrieval_config=types.DynamicRetrievalConfig(
        mode="MODE_DYNAMIC",
        dynamic_threshold=0.3,
    )
))
```
- Source: [Gemini Function Calling Docs](https://ai.google.dev/gemini-api/docs/function-calling)

---

## 4. Gemini 2.5 Thinking Mode — Free Quality Upgrade

Gemini 2.5 has a `thinkingBudget` parameter that activates internal chain-of-thought reasoning before responding. Currently unused.

```python
# For high-stakes agents (VP, Leads - level 1 & 2): dynamic thinking
thinking_config = types.ThinkingConfig(thinking_budget=-1)

# For junior ICs (level 3 & 4): disable thinking to save cost/latency
thinking_config = types.ThinkingConfig(thinking_budget=0)
```

Also: when thinking is enabled with function calling, Gemini returns **thought signatures** that must be passed back in subsequent turns. `chat_chains.py` multi-turn conversations should capture and replay these to preserve context.
- Source: [Gemini Thinking Mode](https://ai.google.dev/gemini-api/docs/thinking)

---

## 5. Reflection — From Passive to Active

Currently reflection happens once, post-hoc, in Round 6. Two key upgrades:

**Inline self-critique (Generator-Critic pattern)** — before an agent submits a deliverable, make a second LLM call with a "critic" role:
> *"Review your draft above. What's weak or missing? Revise if needed."*

The `on_act_postprocess` hook in the trait system (`simulation/traits/__init__.py`) is the perfect injection point — it's already wired in.

**Multi-Agent Reflexion (MAR)** — for quality gate failures, instead of just the VP saying "ITERATE", have department leads act as persona-guided critics who analyze the failure from different angles, then a coordinator aggregates.
- Source: [MAR: Multi-Agent Reflexion](https://arxiv.org/html/2512.20845)

**Lead → IC corrective feedback loop** — currently there's no feedback from leads to ICs between Round 3 (execution) and Round 5 (refinement). Adding a mini-feedback step in Round 4 (when leads have seen deliverables) would dramatically improve Round 5 output quality.

---

## 6. Rate Limiting & Reliability

There's no retry or rate-limit protection — a single 429 error mid-simulation after 10+ minutes = lost run.

**Add `tenacity` with exponential backoff + jitter** around every `generate_content` call in `agents.py`:
```python
from tenacity import retry, wait_random_exponential, stop_after_attempt, retry_if_exception

@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception(lambda e: "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e))
)
def _call_api(...):
    ...
```

**Add a semaphore** in `engine.py` to cap concurrent API calls (important for free-tier users):
```python
self._api_semaphore = threading.Semaphore(4)  # max 4 simultaneous

# In agent.think():
with self._api_semaphore:
    response = client.models.generate_content(...)
```
- Source: [LLM API Retry Logic 2025](https://markaicode.com/llm-api-retry-logic-implementation/)
- Source: [Python Asyncio for LLM Concurrency](https://www.newline.co/@zaoyang/python-asyncio-for-llm-concurrency-best-practices--bc079176)

---

## 7. Evaluation — Beyond Binary Quality Gate

The current quality gate is a single VP judgment (PROCEED/ITERATE). 2025 research recommends richer metrics:

**Multi-dimensional scoring rubric** in the quality gate prompt:
```
Rate the team's output on 5 dimensions (1–10 each):
1. Factual depth
2. Strategic relevance
3. Actionability
4. Cross-department integration
5. Risk coverage
Total: [X]/50. PROCEED if ≥ 35, ITERATE otherwise.
```

**Perspective diversity metric** — compute pairwise cosine similarity between agent deliverables (embeddings already exist). Low avg similarity = healthy debate. High similarity = echo chamber. Detectable automatically.

**Missing metrics to add to `run_metadata.json`:**
- Quality gate iteration count (tracked but not reported)
- Tool utilization rate per agent
- Cross-dept request fulfillment rate
- Avg pairwise similarity between department outputs

- Source: [MultiAgentBench](https://arxiv.org/abs/2503.01935)
- Source: [Rethinking LLM Benchmarks 2025](https://www.fluid.ai/blog/rethinking-llm-benchmarks-for-2025)

---

## 8. Observability — Replace JSONL with Proper Tracing

**Add OpenLLMetry** (open-source, drop-in OTel instrumentation for Gemini):
```bash
pip install openllmetry-sdk openllmetry-instrumentation-google-generativeai
```
Every `generate_content` call becomes a traced span with prompt, response, token count, and latency — viewable in Jaeger, Grafana, or any OTel backend. No code changes needed beyond initialization.

**Add span causality** — tag every log entry with a `parent_span_id` to make the chain traceable: VP delegation → James planning → Priya execution → VP synthesis.

- Source: [OpenLLMetry on GitHub](https://github.com/traceloop/openllmetry)
- Source: [OTel AI Agent Observability 2025](https://opentelemetry.io/blog/2025/ai-agent-observability/)

---

## 9. NiceGUI Dashboard — Two Quick Wins

**Fix flickering (full clear → incremental append):** `_update_feed()` and `_update_conversations()` in `simulation/ui_dashboard.py` call `container.clear()` and rebuild everything every 500ms. Switch to append-only for log views — the existing change-tracking variables (`_last_msg_count` etc.) already detect new items; just render the delta.

**Reduce polling waste:** The `ui.timer(0.5, ...)` fires every 500ms even when nothing is happening. Increase to 2s when all agents are idle (all in `"waiting"` or `"done"` state), drop back to 0.5s when a round is active.

---

## Priority Matrix

| Improvement | Effort | Impact | Where |
|---|---|---|---|
| `tenacity` retry + semaphore | **Low** | **Critical** (prevents lost runs) | `simulation/agents.py` |
| Batch embeddings + LRU cache | **Low** | **High** (major latency reduction) | `simulation/memory.py` |
| `response_schema` structured output | **Low** | **High** (eliminates parse failures) | `simulation/agents.py` |
| Ebbinghaus recency decay | **Low** | Medium | `simulation/memory.py` |
| `thinkingBudget` per agent level | **Low** | Medium (quality + cost) | `simulation/agents.py` |
| NiceGUI incremental append | **Low** | Medium (no more flickering) | `simulation/ui_dashboard.py` |
| Proper agentic tool loop | **Medium** | **High** (tools work end-to-end) | `simulation/agents.py` |
| Inline self-critique trait | **Medium** | High (better deliverable quality) | new trait file |
| Lead → IC corrective feedback | **Medium** | High | `simulation/engine.py` Round 4 |
| Multi-dim quality gate scoring | **Medium** | Medium | `simulation/engine.py` |
| OTel observability | **Medium** | Medium (debugging) | `run_simulation.py` |
| A-MEM dynamic memory linking | **High** | High (long-term) | `simulation/memory.py` |

---

## Sources

- [A-MEM: Agentic Memory for LLM Agents](https://arxiv.org/abs/2502.12110)
- [Synapse: Episodic-Semantic Memory via Spreading Activation](https://arxiv.org/html/2601.02744v1)
- [Episodic Memory is the Missing Piece for Long-Term LLM Agents](https://arxiv.org/pdf/2502.06975)
- [MAR: Multi-Agent Reflexion Improves Reasoning](https://arxiv.org/html/2512.20845)
- [Self-correcting multi-agent LLM framework (Nature)](https://www.nature.com/articles/s44387-025-00057-z)
- [Gemini Thinking Mode](https://ai.google.dev/gemini-api/docs/thinking)
- [Gemini Function Calling Docs](https://ai.google.dev/gemini-api/docs/function-calling)
- [Gemini Structured Output](https://ai.google.dev/gemini-api/docs/structured-output)
- [Python Asyncio for LLM Concurrency](https://www.newline.co/@zaoyang/python-asyncio-for-llm-concurrency-best-practices--bc079176)
- [LLM API Retry Logic 2025](https://markaicode.com/llm-api-retry-logic-implementation/)
- [MultiAgentBench: Evaluating LLM Agent Collaboration](https://arxiv.org/abs/2503.01935)
- [Rethinking LLM Benchmarks for 2025](https://www.fluid.ai/blog/rethinking-llm-benchmarks-for-2025)
- [OpenLLMetry on GitHub](https://github.com/traceloop/openllmetry)
- [OTel AI Agent Observability 2025](https://opentelemetry.io/blog/2025/ai-agent-observability/)
- [AriGraph: Knowledge Graph World Models (IJCAI 2025)](https://www.ijcai.org/proceedings/2025/0002.pdf)
- [Enhancing Memory Retrieval via Cross-Attention Networks](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2025.1591618/full)
- [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442)
- [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366)
- [LangGraph Agentic Concepts](https://langchain-ai.github.io/langgraph/concepts/agentic_concepts/)

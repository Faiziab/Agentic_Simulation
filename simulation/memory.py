"""
Memory System for R&D Simulation Agents.
Implements Working Memory, Episodic Memory, and Semantic Memory
inspired by Stanford's Generative Agents architecture.

Upgraded with:
  - Embedding-based semantic retrieval (Gemini text-embedding-004)
  - Tri-factor scoring: relevance + recency + importance
  - End-of-round memory consolidation
"""

import json
import math
import os
import threading
from datetime import datetime
from typing import Optional

from google import genai

# ── Embedding helpers ──────────────────────────────────────────

_embed_client = None
_embed_lock = threading.Lock()
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768  # text-embedding-004 output size


def _get_client():
    """Lazy singleton for the Gemini client (thread-safe)."""
    global _embed_client
    if _embed_client is None:
        with _embed_lock:
            if _embed_client is None:
                _embed_client = genai.Client()
    return _embed_client


def get_embedding(text: str) -> list[float]:
    """Get embedding vector for a text string using Gemini's embedding model."""
    try:
        client = _get_client()
        # Truncate very long text to avoid token limits
        truncated = text[:2000] if len(text) > 2000 else text
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=truncated,
        )
        return result.embeddings[0].values
    except Exception:
        # Fallback: return zero vector if embedding fails (API error, etc.)
        return [0.0] * EMBEDDING_DIM


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── Memory Entry ──────────────────────────────────────────────

class MemoryEntry:
    """A single memory entry in an agent's memory stream."""

    def __init__(
        self,
        content: str,
        memory_type: str,
        importance: int = 5,
        source: str = "",
        related_agent: str = "",
        round_number: int = 0,
        embedding: list[float] | None = None,
    ):
        self.id = f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self.timestamp = datetime.now().isoformat()
        self.content = content
        self.memory_type = memory_type  # observation, action, communication, reflection, insight, consolidated
        self.importance = min(max(importance, 1), 10)  # 1-10 scale
        self.source = source  # who/what caused this memory
        self.related_agent = related_agent
        self.round_number = round_number
        self.embedding = embedding  # Semantic embedding vector

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "timestamp": self.timestamp,
            "content": self.content,
            "memory_type": self.memory_type,
            "importance": self.importance,
            "source": self.source,
            "related_agent": self.related_agent,
            "round_number": self.round_number,
        }
        # Store embedding only if it's non-zero (saves disk space)
        if self.embedding and any(v != 0.0 for v in self.embedding):
            d["embedding"] = self.embedding
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        entry = cls(
            content=data["content"],
            memory_type=data["memory_type"],
            importance=data["importance"],
            source=data.get("source", ""),
            related_agent=data.get("related_agent", ""),
            round_number=data.get("round_number", 0),
            embedding=data.get("embedding"),
        )
        entry.id = data["id"]
        entry.timestamp = data["timestamp"]
        return entry

    def __repr__(self):
        return f"Memory({self.memory_type}, imp={self.importance}): {self.content[:60]}..."


# ── Working Memory ────────────────────────────────────────────

class WorkingMemory:
    """
    Short-term memory for the current task context.
    Holds the immediate context passed to the LLM in each call.
    """

    def __init__(self, max_items: int = 20):
        self.items: list[str] = []
        self.max_items = max_items
        self.current_task: Optional[str] = None
        self.current_round: int = 0
        self.assigned_by: Optional[str] = None

    def add(self, item: str):
        self.items.append(item)
        if len(self.items) > self.max_items:
            self.items = self.items[-self.max_items :]

    def set_task(self, task: str, assigned_by: str = "", round_number: int = 0):
        self.current_task = task
        self.assigned_by = assigned_by
        self.current_round = round_number

    def get_context(self) -> str:
        """Build context string for LLM calls."""
        parts = []
        if self.current_task:
            parts.append(f"CURRENT TASK: {self.current_task}")
        if self.assigned_by:
            parts.append(f"ASSIGNED BY: {self.assigned_by}")
        parts.append(f"CURRENT ROUND: {self.current_round}")
        if self.items:
            parts.append("RECENT CONTEXT:")
            for item in self.items[-10:]:  # Last 10 items for immediate context
                parts.append(f"  - {item}")
        return "\n".join(parts)

    def clear(self):
        self.items.clear()
        self.current_task = None
        self.assigned_by = None


# ── Memory Stream ─────────────────────────────────────────────

class MemoryStream:
    """
    Long-term episodic + semantic memory for an agent.
    Persists as JSONL file. Supports retrieval by recency, importance,
    and semantic relevance (embedding-based).
    """

    def __init__(self, agent_id: str, workspace_dir: str):
        self.agent_id = agent_id
        self.memories: list[MemoryEntry] = []
        self.workspace_dir = workspace_dir
        self.memory_dir = os.path.join(workspace_dir, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        self.filepath = os.path.join(self.memory_dir, f"{agent_id}.jsonl")

    def add(self, entry: MemoryEntry):
        """Add a memory and persist it."""
        self.memories.append(entry)
        self._persist_entry(entry)

    def add_memory(
        self,
        content: str,
        memory_type: str = "observation",
        importance: int = 5,
        source: str = "",
        related_agent: str = "",
        round_number: int = 0,
    ) -> MemoryEntry:
        """Create, embed, and add a memory."""
        # Generate semantic embedding for this memory
        embedding = get_embedding(content)

        entry = MemoryEntry(
            content=content,
            memory_type=memory_type,
            importance=importance,
            source=source,
            related_agent=related_agent,
            round_number=round_number,
            embedding=embedding,
        )
        self.add(entry)
        return entry

    def get_recent(self, n: int = 10) -> list[MemoryEntry]:
        """Get the n most recent memories."""
        return self.memories[-n:]

    def get_by_type(self, memory_type: str, n: int = 10) -> list[MemoryEntry]:
        """Get memories of a specific type."""
        filtered = [m for m in self.memories if m.memory_type == memory_type]
        return filtered[-n:]

    def get_important(self, threshold: int = 7, n: int = 10) -> list[MemoryEntry]:
        """Get memories above an importance threshold."""
        filtered = [m for m in self.memories if m.importance >= threshold]
        return sorted(filtered, key=lambda m: m.importance, reverse=True)[:n]

    def get_by_round(self, round_number: int) -> list[MemoryEntry]:
        """Get all memories from a specific round."""
        return [m for m in self.memories if m.round_number == round_number]

    def retrieve(self, query: str = "", n: int = 10) -> list[MemoryEntry]:
        """
        Retrieve top-n memories using tri-factor scoring:
          - 35% semantic relevance (cosine similarity to query)
          - 25% recency (more recent = higher)
          - 40% importance (agent-assigned 1-10 scale)

        Falls back to recency+importance if no query or no embeddings.
        """
        if not self.memories:
            return []

        # Get query embedding if a query is provided
        query_embedding = None
        if query:
            query_embedding = get_embedding(query)

        scored = []
        total = len(self.memories)
        for i, mem in enumerate(self.memories):
            recency_score = (i + 1) / total  # 0→1, more recent = higher
            importance_score = mem.importance / 10  # 0→1

            # Semantic relevance (0→1)
            if query_embedding and mem.embedding:
                relevance_score = max(0.0, cosine_similarity(query_embedding, mem.embedding))
            else:
                relevance_score = 0.5  # Neutral if no embeddings

            # Tri-factor weighted score
            if query_embedding:
                combined = (
                    0.35 * relevance_score
                    + 0.25 * recency_score
                    + 0.40 * importance_score
                )
            else:
                # No query → fall back to original recency+importance
                combined = 0.4 * recency_score + 0.6 * importance_score

            scored.append((combined, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in scored[:n]]

    def consolidate(self, current_round: int, llm_client=None, model_name: str = "gemini-2.5-flash"):
        """
        End-of-round memory consolidation.
        Summarizes older memories into 2-3 high-level insights,
        reducing context bloat while preserving key knowledge.
        """
        # Only consolidate if we have enough memories
        if len(self.memories) < 25:
            return

        # Identify old memories (more than 2 rounds old, not already consolidated)
        old_memories = [
            m for m in self.memories
            if m.round_number < current_round - 1
            and m.memory_type not in ("consolidated", "reflection", "insight")
        ]

        if len(old_memories) < 10:
            return  # Not enough to justify consolidation

        # Build summary prompt from old memories
        mem_texts = [f"[R{m.round_number}] ({m.memory_type}) {m.content}" for m in old_memories[:30]]
        summary_prompt = (
            "You are consolidating an agent's memory. Summarize the following "
            f"{len(mem_texts)} memories into exactly 3 concise key insights "
            "(one line each). Preserve important facts, decisions, and relationships. "
            "Format as a numbered list.\n\n"
            + "\n".join(mem_texts)
        )

        try:
            client = llm_client or _get_client()
            response = client.models.generate_content(
                model=model_name,
                contents=summary_prompt,
                config={"temperature": 0.3, "max_output_tokens": 512},
            )
            summary = response.text
            if not summary:
                return

            # Remove old memories from active list (they're still in JSONL on disk)
            old_ids = {m.id for m in old_memories}
            self.memories = [m for m in self.memories if m.id not in old_ids]

            # Add consolidated insight
            self.add_memory(
                content=f"CONSOLIDATED MEMORIES (rounds 1-{current_round - 2}):\n{summary}",
                memory_type="consolidated",
                importance=8,
                source="memory_consolidation",
                round_number=current_round,
            )
        except Exception:
            pass  # Non-critical — keep original memories if consolidation fails

    def get_cumulative_importance(self, since_round: int = 0) -> int:
        """Get sum of importance scores since a given round."""
        return sum(
            m.importance for m in self.memories if m.round_number >= since_round
        )

    def format_for_context(self, memories: list[MemoryEntry]) -> str:
        """Format memories as a string for LLM context."""
        if not memories:
            return "No relevant memories."
        lines = ["RELEVANT MEMORIES:"]
        for mem in memories:
            prefix = {
                "observation": "📝",
                "action": "⚡",
                "communication": "💬",
                "reflection": "🔄",
                "insight": "💡",
                "consolidated": "📦",
            }.get(mem.memory_type, "•")
            lines.append(
                f"  {prefix} [{mem.memory_type.upper()}] (importance: {mem.importance}/10) {mem.content}"
            )
        return "\n".join(lines)

    def _persist_entry(self, entry: MemoryEntry):
        """Append a memory entry to the JSONL file."""
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def load(self):
        """Load memories from JSONL file."""
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = MemoryEntry.from_dict(json.loads(line))
                        self.memories.append(entry)

    def get_reflections(self) -> list[MemoryEntry]:
        """Get all reflection-type memories."""
        return [m for m in self.memories if m.memory_type in ("reflection", "insight")]

    def __len__(self):
        return len(self.memories)

    def __repr__(self):
        return f"MemoryStream({self.agent_id}, {len(self.memories)} memories)"

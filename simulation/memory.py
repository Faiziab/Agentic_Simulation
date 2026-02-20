"""
Memory System for R&D Simulation Agents.
Implements Working Memory, Episodic Memory, and Semantic Memory
inspired by Stanford's Generative Agents architecture.
"""

import json
import os
from datetime import datetime
from typing import Optional


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
    ):
        self.id = f"mem_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self.timestamp = datetime.now().isoformat()
        self.content = content
        self.memory_type = memory_type  # "observation", "action", "communication", "reflection", "insight"
        self.importance = min(max(importance, 1), 10)  # 1-10 scale
        self.source = source  # who/what caused this memory
        self.related_agent = related_agent
        self.round_number = round_number

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "content": self.content,
            "memory_type": self.memory_type,
            "importance": self.importance,
            "source": self.source,
            "related_agent": self.related_agent,
            "round_number": self.round_number,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        entry = cls(
            content=data["content"],
            memory_type=data["memory_type"],
            importance=data["importance"],
            source=data.get("source", ""),
            related_agent=data.get("related_agent", ""),
            round_number=data.get("round_number", 0),
        )
        entry.id = data["id"]
        entry.timestamp = data["timestamp"]
        return entry

    def __repr__(self):
        return f"Memory({self.memory_type}, imp={self.importance}): {self.content[:60]}..."


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


class MemoryStream:
    """
    Long-term episodic + semantic memory for an agent.
    Persists as JSONL file. Supports retrieval by recency, importance, and type.
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
        """Convenience method to create and add a memory."""
        entry = MemoryEntry(
            content=content,
            memory_type=memory_type,
            importance=importance,
            source=source,
            related_agent=related_agent,
            round_number=round_number,
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

    def retrieve(self, n: int = 10) -> list[MemoryEntry]:
        """
        Retrieve top-n memories weighted by recency + importance.
        This is the primary retrieval method for building LLM context.
        """
        if not self.memories:
            return []

        scored = []
        total = len(self.memories)
        for i, mem in enumerate(self.memories):
            recency_score = (i + 1) / total  # 0 to 1, more recent = higher
            importance_score = mem.importance / 10  # 0 to 1
            # Weight: 40% recency, 60% importance
            combined = 0.4 * recency_score + 0.6 * importance_score
            scored.append((combined, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in scored[:n]]

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

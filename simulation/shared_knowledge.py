"""
Shared Team Knowledge Pool for R&D Simulation.
Provides department-level shared memory accessible by all team members.

Agents can publish findings, decisions, and insights to their
department's knowledge pool. Other agents (including cross-department)
can query the pool for relevant information using semantic search.
"""

import json
import os
from datetime import datetime
from typing import Optional

from simulation.memory import cosine_similarity, get_embedding


class KnowledgeEntry:
    """A single entry in the shared knowledge pool."""

    _counter = 0

    def __init__(
        self,
        from_agent: str,
        content: str,
        tags: list[str] | None = None,
        importance: int = 5,
        round_number: int = 0,
        embedding: list[float] | None = None,
    ):
        KnowledgeEntry._counter += 1
        self.id = f"know_{KnowledgeEntry._counter:04d}"
        self.timestamp = datetime.now().isoformat()
        self.from_agent = from_agent
        self.content = content
        self.tags = tags or []
        self.importance = min(max(importance, 1), 10)
        self.round_number = round_number
        self.embedding = embedding

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "timestamp": self.timestamp,
            "from_agent": self.from_agent,
            "content": self.content,
            "tags": self.tags,
            "importance": self.importance,
            "round_number": self.round_number,
        }
        if self.embedding and any(v != 0.0 for v in self.embedding):
            d["embedding"] = self.embedding
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeEntry":
        entry = cls(
            from_agent=data["from_agent"],
            content=data["content"],
            tags=data.get("tags", []),
            importance=data.get("importance", 5),
            round_number=data.get("round_number", 0),
            embedding=data.get("embedding"),
        )
        entry.id = data["id"]
        entry.timestamp = data["timestamp"]
        return entry


class SharedKnowledge:
    """
    Department-level shared knowledge pool.
    Agents publish findings, and any team member can query them.
    Supports semantic search via embeddings.
    """

    def __init__(self, department: str, workspace_dir: str):
        self.department = department
        self.entries: list[KnowledgeEntry] = []
        self.workspace_dir = workspace_dir
        self.knowledge_dir = os.path.join(workspace_dir, "knowledge")
        os.makedirs(self.knowledge_dir, exist_ok=True)
        self.filepath = os.path.join(self.knowledge_dir, f"{department}.jsonl")

    def publish(
        self,
        agent_id: str,
        content: str,
        tags: list[str] | None = None,
        importance: int = 5,
        round_number: int = 0,
    ) -> KnowledgeEntry:
        """Agent shares a finding with their department's knowledge pool."""
        embedding = get_embedding(content)
        entry = KnowledgeEntry(
            from_agent=agent_id,
            content=content,
            tags=tags,
            importance=importance,
            round_number=round_number,
            embedding=embedding,
        )
        self.entries.append(entry)
        self._persist_entry(entry)
        return entry

    def query(self, query_text: str, n: int = 5) -> list[dict]:
        """
        Semantic search across shared knowledge.
        Returns list of dicts with content and metadata.
        """
        if not self.entries:
            return []

        query_embedding = get_embedding(query_text)

        scored = []
        for entry in self.entries:
            if entry.embedding:
                relevance = max(0.0, cosine_similarity(query_embedding, entry.embedding))
            else:
                relevance = 0.0
            importance = entry.importance / 10
            combined = 0.6 * relevance + 0.4 * importance
            scored.append((combined, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "id": entry.id,
                "from_agent": entry.from_agent,
                "content": entry.content,
                "tags": entry.tags,
                "importance": entry.importance,
                "round_number": entry.round_number,
                "relevance_score": round(score, 3),
            }
            for score, entry in scored[:n]
        ]

    def get_by_tags(self, tags: list[str]) -> list[KnowledgeEntry]:
        """Get knowledge entries matching any of the given tags."""
        tag_set = set(t.lower() for t in tags)
        return [
            e for e in self.entries
            if set(t.lower() for t in e.tags) & tag_set
        ]

    def get_recent(self, n: int = 5) -> list[KnowledgeEntry]:
        """Get the most recent knowledge entries."""
        return self.entries[-n:]

    def _persist_entry(self, entry: KnowledgeEntry):
        """Append entry to JSONL file."""
        with open(self.filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def load(self):
        """Load entries from JSONL file."""
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = KnowledgeEntry.from_dict(json.loads(line))
                        self.entries.append(entry)

    def __len__(self):
        return len(self.entries)

    def __repr__(self):
        return f"SharedKnowledge({self.department}, {len(self.entries)} entries)"


class KnowledgeManager:
    """
    Manages all department knowledge pools and cross-department queries.
    Used by the engine to coordinate shared knowledge.
    """

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.pools: dict[str, SharedKnowledge] = {}

    def get_pool(self, department: str) -> SharedKnowledge:
        """Get or create a knowledge pool for a department."""
        if department not in self.pools:
            self.pools[department] = SharedKnowledge(department, self.workspace_dir)
        return self.pools[department]

    def cross_dept_query(
        self, query: str, source_dept: str, n: int = 3
    ) -> list[dict]:
        """
        Query all OTHER departments' knowledge pools.
        Returns combined results from all departments except source.
        """
        all_results = []
        for dept, pool in self.pools.items():
            if dept == source_dept:
                continue
            results = pool.query(query, n=n)
            for r in results:
                r["department"] = dept
            all_results.extend(results)

        # Sort by relevance and take top-n
        all_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        return all_results[:n]

    def publish_to_dept(
        self,
        department: str,
        agent_id: str,
        content: str,
        tags: list[str] | None = None,
        importance: int = 5,
        round_number: int = 0,
    ) -> KnowledgeEntry:
        """Convenience: publish to a specific department's pool."""
        pool = self.get_pool(department)
        return pool.publish(agent_id, content, tags, importance, round_number)

    def get_summary_stats(self) -> dict:
        """Get summary statistics across all knowledge pools."""
        return {
            dept: {
                "entries": len(pool),
                "agents": list(set(e.from_agent for e in pool.entries)),
            }
            for dept, pool in self.pools.items()
        }

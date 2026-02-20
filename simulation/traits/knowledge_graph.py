"""
Knowledge Graph Trait.
Tracks what each agent knows about (topics, facts, expertise areas).
Enables smart question routing: "who knows most about X?"
"""

import re
from collections import defaultdict
from simulation.traits import BaseTrait


class KnowledgeNode:
    """A single knowledge entry: agent knows about a topic."""

    def __init__(self, topic: str, confidence: float = 0.5, source_round: int = 0):
        self.topic = topic.lower().strip()
        self.confidence = confidence  # 0.0 to 1.0
        self.source_round = source_round
        self.mentions = 1  # How many times referenced

    def reinforce(self, confidence_boost: float = 0.1):
        """Strengthen knowledge through repeated exposure."""
        self.confidence = min(1.0, self.confidence + confidence_boost)
        self.mentions += 1

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "confidence": round(self.confidence, 2),
            "mentions": self.mentions,
            "source_round": self.source_round,
        }


class KnowledgeGraph:
    """
    In-memory graph: Agent → knows → Topic (with confidence).
    Used for smart routing of cross-department questions.
    """

    def __init__(self):
        self.graph: dict[str, dict[str, KnowledgeNode]] = defaultdict(dict)
        # agent_id -> {topic -> KnowledgeNode}

    def add_knowledge(self, agent_id: str, topic: str,
                      confidence: float = 0.5, round_number: int = 0):
        """Record that an agent knows about a topic."""
        topic_key = topic.lower().strip()
        if topic_key in self.graph[agent_id]:
            self.graph[agent_id][topic_key].reinforce()
        else:
            self.graph[agent_id][topic_key] = KnowledgeNode(
                topic=topic_key, confidence=confidence, source_round=round_number
            )

    def who_knows_about(self, topic: str, top_n: int = 3) -> list[tuple[str, float]]:
        """Find which agents know most about a topic. Returns [(agent_id, score)]."""
        topic_lower = topic.lower().strip()
        scores = []

        for agent_id, knowledge in self.graph.items():
            score = 0.0
            for known_topic, node in knowledge.items():
                # Exact match
                if topic_lower == known_topic:
                    score += node.confidence * 2.0
                # Partial match (topic is substring)
                elif topic_lower in known_topic or known_topic in topic_lower:
                    score += node.confidence * 1.0
                # Word overlap
                else:
                    topic_words = set(topic_lower.split())
                    known_words = set(known_topic.split())
                    overlap = topic_words & known_words
                    if overlap:
                        score += node.confidence * 0.5 * len(overlap)

            if score > 0:
                scores.append((agent_id, score))

        return sorted(scores, key=lambda x: -x[1])[:top_n]

    def get_agent_knowledge(self, agent_id: str) -> list[dict]:
        """Get all knowledge for an agent, sorted by confidence."""
        knowledge = self.graph.get(agent_id, {})
        return sorted(
            [node.to_dict() for node in knowledge.values()],
            key=lambda x: -x["confidence"]
        )

    def get_all_topics(self) -> set[str]:
        """Get all unique topics across all agents."""
        topics = set()
        for knowledge in self.graph.values():
            topics.update(knowledge.keys())
        return topics

    def format_graph(self) -> str:
        """Format the full knowledge graph as markdown."""
        lines = ["## Knowledge Graph\n"]

        for agent_id in sorted(self.graph.keys()):
            knowledge = self.get_agent_knowledge(agent_id)
            if not knowledge:
                continue
            lines.append(f"### {agent_id}")
            lines.append("| Topic | Confidence | Mentions |")
            lines.append("|-------|-----------|----------|")
            for k in knowledge[:15]:  # Top 15 per agent
                bar = "●" * int(k["confidence"] * 5) + "○" * (5 - int(k["confidence"] * 5))
                lines.append(f"| {k['topic']} | {bar} {k['confidence']:.0%} | {k['mentions']} |")
            lines.append("")

        return "\n".join(lines)


# Keywords to extract topics from text
TOPIC_PATTERNS = [
    r'\b(?:AI|ML|NLP|API|UX|UI)\b',
    r'\b(?:machine learning|deep learning|neural network|recommendation engine)\b',
    r'\b(?:vector search|semantic search|information retrieval)\b',
    r'\b(?:microservice|distributed system|cloud native)\b',
    r'\b(?:user research|user experience|accessibility)\b',
    r'\b(?:data pipeline|data lake|ETL)\b',
    r'\b(?:security|encryption|authentication|authorization)\b',
    r'\b(?:performance|latency|throughput|scalability)\b',
    r'\b(?:market analysis|competitive analysis|product strategy)\b',
    r'\b(?:natural language processing|text analysis|document processing)\b',
    r'\b(?:prototype|architecture|system design|technical spec)\b',
    r'\b(?:embedding|fine.?tuning|RAG|retrieval)\b',
]


def extract_topics(text: str) -> list[str]:
    """Extract knowledge topics from text using pattern matching."""
    topics = set()
    text_lower = text.lower()

    for pattern in TOPIC_PATTERNS:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        topics.update(m.lower() for m in matches)

    return list(topics)


class KnowledgeTrait(BaseTrait):
    name = "knowledge_graph"
    description = "Tracks what each agent knows for smart question routing"

    def __init__(self, **kwargs):
        self.graph = KnowledgeGraph()

    def on_act_postprocess(self, agent, result: dict, round_number: int) -> dict:
        """Extract topics from agent output and add to knowledge graph."""
        response = result.get("response", "")
        task = result.get("task", "")
        combined = f"{task} {response}"

        topics = extract_topics(combined)
        for topic in topics:
            self.graph.add_knowledge(
                agent_id=agent.agent_id,
                topic=topic,
                confidence=0.6,
                round_number=round_number,
            )

        result["knowledge_topics"] = topics
        return result

    def on_think_prompt(self, agent, task: str, round_number: int) -> str:
        """Show agent what topics they're knowledgeable about."""
        knowledge = self.graph.get_agent_knowledge(agent.agent_id)
        strong = [k for k in knowledge if k["confidence"] >= 0.5]

        if not strong:
            return ""

        topics = ", ".join(k["topic"] for k in strong[:8])
        return f"\nYour KNOWN AREAS OF EXPERTISE (from this simulation): {topics}\n"

    def route_question(self, topic: str, exclude_agent: str = "") -> list[tuple[str, float]]:
        """Route a question to the most knowledgeable agent(s)."""
        results = self.graph.who_knows_about(topic)
        return [(a, s) for a, s in results if a != exclude_agent]

    def get_report(self) -> str:
        """Get formatted knowledge graph report."""
        return self.graph.format_graph()

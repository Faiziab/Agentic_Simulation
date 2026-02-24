"""
Communication System for R&D Simulation.
Implements a centralized message board with structured payloads,
conversation threading, and topic-based retrieval.

Upgraded with:
  - Structured message payloads (tags, references, thread_id)
  - Conversation threading via post_reply()
  - Topic-based retrieval via get_by_tags()
  - Unanswered question tracking via get_unanswered()
"""

import json
import os
import uuid
from datetime import datetime
from typing import Optional


class Message:
    """A structured message between agents."""

    _counter = 0

    def __init__(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
        msg_type: str = "direct_message",
        channel: str = "direct",
        priority: str = "medium",
        context: str = "",
        round_number: int = 0,
        tags: list[str] | None = None,
        references: list[str] | None = None,
        thread_id: str | None = None,
        requires_response: bool = False,
    ):
        Message._counter += 1
        self.id = f"msg_{Message._counter:04d}"
        self.timestamp = datetime.now().isoformat()
        self.from_agent = from_agent
        self.to_agent = to_agent  # Can be an agent_id, department name, or "all"
        self.content = content
        self.msg_type = msg_type  # task_assignment, question, response, status_update, deliverable, escalation, feedback, decision
        self.channel = channel  # direct, department_broadcast, cross_department, escalation
        self.priority = priority  # low, medium, high, urgent
        self.context = context
        self.round_number = round_number
        self.read = False

        # Structured metadata
        self.tags = tags or []  # Topic tags: ["security", "architecture", "RAG"]
        self.references = references or []  # Parent message IDs (threading)
        self.thread_id = thread_id or self.id  # Conversation thread ID
        self.requires_response = requires_response  # Sender expects a reply
        self.responded = False  # Has this been replied to

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "content": self.content,
            "msg_type": self.msg_type,
            "channel": self.channel,
            "priority": self.priority,
            "context": self.context,
            "round_number": self.round_number,
            "read": self.read,
            "tags": self.tags,
            "references": self.references,
            "thread_id": self.thread_id,
            "requires_response": self.requires_response,
            "responded": self.responded,
        }

    def format_display(self) -> str:
        """Format for display in agent context."""
        priority_icon = {
            "low": "◻️",
            "medium": "◼️",
            "high": "🔶",
            "urgent": "🔴",
        }.get(self.priority, "◼️")
        tags_str = f" [{', '.join(self.tags)}]" if self.tags else ""
        thread_str = " (threaded)" if self.references else ""
        response_str = " ⏳" if self.requires_response and not self.responded else ""
        return f"{priority_icon} [{self.msg_type}]{tags_str} From {self.from_agent}: {self.content}{thread_str}{response_str}"


class MessageBoard:
    """
    Centralized communication hub for all agent messages.
    Supports structured payloads, conversation threading,
    topic-based retrieval, and unanswered question tracking.
    """

    def __init__(self, workspace_dir: str):
        self.messages: list[Message] = []
        self.workspace_dir = workspace_dir
        self.log_dir = os.path.join(workspace_dir, "logs")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, "communication_log.jsonl")

    def post(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
        msg_type: str = "direct_message",
        channel: str = "direct",
        priority: str = "medium",
        context: str = "",
        round_number: int = 0,
        tags: list[str] | None = None,
        requires_response: bool = False,
    ) -> Message:
        """Post a message to the board."""
        msg = Message(
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            msg_type=msg_type,
            channel=channel,
            priority=priority,
            context=context,
            round_number=round_number,
            tags=tags,
            requires_response=requires_response,
        )
        self.messages.append(msg)
        self._log_message(msg)
        return msg

    def post_reply(
        self,
        parent_msg_id: str,
        from_agent: str,
        content: str,
        msg_type: str = "response",
        tags: list[str] | None = None,
        round_number: int = 0,
    ) -> Message:
        """Post a reply to an existing message, auto-threading."""
        # Find parent message
        parent = None
        for m in self.messages:
            if m.id == parent_msg_id:
                parent = m
                break

        thread_id = parent.thread_id if parent else str(uuid.uuid4())[:8]
        to_agent = parent.from_agent if parent else "unknown"

        # Mark parent as responded
        if parent and parent.requires_response:
            parent.responded = True

        # Inherit tags from parent if not specified
        inherited_tags = tags or (parent.tags if parent else [])

        msg = Message(
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            msg_type=msg_type,
            channel=parent.channel if parent else "direct",
            priority=parent.priority if parent else "medium",
            round_number=round_number,
            tags=inherited_tags,
            references=[parent_msg_id],
            thread_id=thread_id,
        )
        self.messages.append(msg)
        self._log_message(msg)
        return msg

    def post_task_assignment(
        self,
        from_agent: str,
        to_agent: str,
        task_description: str,
        context: str = "",
        round_number: int = 0,
        tags: list[str] | None = None,
    ) -> Message:
        """Convenience: post a task assignment."""
        return self.post(
            from_agent=from_agent,
            to_agent=to_agent,
            content=task_description,
            msg_type="task_assignment",
            channel="direct",
            priority="high",
            context=context,
            round_number=round_number,
            tags=tags,
            requires_response=True,
        )

    def post_question(
        self,
        from_agent: str,
        to_agent: str,
        question: str,
        context: str = "",
        round_number: int = 0,
        tags: list[str] | None = None,
    ) -> Message:
        """Convenience: post a question to another agent."""
        return self.post(
            from_agent=from_agent,
            to_agent=to_agent,
            content=question,
            msg_type="question",
            channel="cross_department",
            priority="medium",
            context=context,
            round_number=round_number,
            tags=tags,
            requires_response=True,
        )

    def post_deliverable(
        self,
        from_agent: str,
        to_agent: str,
        deliverable: str,
        context: str = "",
        round_number: int = 0,
        tags: list[str] | None = None,
    ) -> Message:
        """Convenience: submit a deliverable."""
        return self.post(
            from_agent=from_agent,
            to_agent=to_agent,
            content=deliverable,
            msg_type="deliverable",
            channel="direct",
            priority="high",
            context=context,
            round_number=round_number,
            tags=tags,
        )

    def get_for_agent(
        self,
        agent_id: str,
        unread_only: bool = False,
        msg_type: Optional[str] = None,
    ) -> list[Message]:
        """Get all messages addressed to an agent."""
        messages = [
            m
            for m in self.messages
            if m.to_agent == agent_id or m.to_agent == "all"
        ]
        if unread_only:
            messages = [m for m in messages if not m.read]
        if msg_type:
            messages = [m for m in messages if m.msg_type == msg_type]
        return messages

    def get_from_agent(self, agent_id: str) -> list[Message]:
        """Get all messages sent by an agent."""
        return [m for m in self.messages if m.from_agent == agent_id]

    def get_department_messages(
        self, department: str, round_number: Optional[int] = None
    ) -> list[Message]:
        """Get messages in a department broadcast channel."""
        messages = [
            m for m in self.messages if m.to_agent == department
        ]
        if round_number is not None:
            messages = [m for m in messages if m.round_number == round_number]
        return messages

    def get_cross_department(
        self, round_number: Optional[int] = None
    ) -> list[Message]:
        """Get all cross-department messages."""
        messages = [m for m in self.messages if m.channel == "cross_department"]
        if round_number is not None:
            messages = [m for m in messages if m.round_number == round_number]
        return messages

    def get_by_round(self, round_number: int) -> list[Message]:
        """Get all messages from a specific round."""
        return [m for m in self.messages if m.round_number == round_number]

    def mark_read(self, agent_id: str):
        """Mark all messages for an agent as read."""
        for m in self.messages:
            if m.to_agent == agent_id or m.to_agent == "all":
                m.read = True

    def get_conversation_between(
        self, agent1: str, agent2: str
    ) -> list[Message]:
        """Get the full conversation thread between two agents."""
        return [
            m
            for m in self.messages
            if (m.from_agent == agent1 and m.to_agent == agent2)
            or (m.from_agent == agent2 and m.to_agent == agent1)
        ]

    # ── New: Threading & Topic-Based Retrieval ──────────────

    def get_thread(self, thread_id: str) -> list[Message]:
        """Get all messages in a conversation thread, ordered chronologically."""
        return [m for m in self.messages if m.thread_id == thread_id]

    def get_unanswered(self, agent_id: str) -> list[Message]:
        """Get all messages addressed to agent that require a response but haven't been answered."""
        return [
            m for m in self.messages
            if (m.to_agent == agent_id or m.to_agent == "all")
            and m.requires_response
            and not m.responded
        ]

    def get_by_tags(self, tags: list[str], match_any: bool = True) -> list[Message]:
        """
        Get messages matching topic tags.
        match_any=True: message must have at least one of the tags
        match_any=False: message must have all of the tags
        """
        tag_set = set(t.lower() for t in tags)
        results = []
        for m in self.messages:
            msg_tags = set(t.lower() for t in m.tags)
            if match_any:
                if msg_tags & tag_set:  # Intersection
                    results.append(m)
            else:
                if tag_set <= msg_tags:  # Subset check
                    results.append(m)
        return results

    def get_threads_summary(self) -> list[dict]:
        """Get a summary of all conversation threads."""
        threads: dict[str, list[Message]] = {}
        for m in self.messages:
            threads.setdefault(m.thread_id, []).append(m)

        summaries = []
        for tid, msgs in threads.items():
            if len(msgs) <= 1 and not msgs[0].references:
                continue  # Skip single messages that aren't part of a thread
            participants = list(set(m.from_agent for m in msgs))
            summaries.append({
                "thread_id": tid,
                "participants": participants,
                "message_count": len(msgs),
                "first_message": msgs[0].content[:100],
                "tags": list(set(t for m in msgs for t in m.tags)),
                "rounds": sorted(set(m.round_number for m in msgs)),
            })
        return summaries

    def format_inbox(self, agent_id: str, unread_only: bool = True) -> str:
        """Format an agent's inbox for LLM context, grouped by thread."""
        messages = self.get_for_agent(agent_id, unread_only=unread_only)
        if not messages:
            return "No new messages."

        # Group by thread
        threads: dict[str, list[Message]] = {}
        standalone: list[Message] = []
        for msg in messages:
            if msg.references or any(m.thread_id == msg.thread_id and m.id != msg.id for m in messages):
                threads.setdefault(msg.thread_id, []).append(msg)
            else:
                standalone.append(msg)

        lines = [f"INBOX ({len(messages)} message{'s' if len(messages) != 1 else ''}):\n"]

        # Standalone messages first
        for msg in standalone:
            lines.append(msg.format_display())
            lines.append("")

        # Threaded conversations
        for tid, thread_msgs in threads.items():
            tags_str = ", ".join(set(t for m in thread_msgs for t in m.tags))
            lines.append(f"── Thread [{tags_str or 'conversation'}] ──")
            for msg in thread_msgs:
                lines.append(f"  {msg.format_display()}")
            lines.append("")

        # Unanswered questions alert
        unanswered = self.get_unanswered(agent_id)
        if unanswered:
            lines.append(f"⚠️ {len(unanswered)} unanswered question(s) pending your response.")

        return "\n".join(lines)

    def get_all(self) -> list[Message]:
        """Get all messages."""
        return self.messages

    def _log_message(self, msg: Message):
        """Persist message to JSONL log."""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(msg.to_dict()) + "\n")

    def __len__(self):
        return len(self.messages)

"""
Communication System for R&D Simulation.
Implements a centralized message board with multiple channels
for inter-agent communication.
"""

import json
import os
from datetime import datetime
from typing import Optional


class Message:
    """A single message between agents."""

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
    ):
        Message._counter += 1
        self.id = f"msg_{Message._counter:04d}"
        self.timestamp = datetime.now().isoformat()
        self.from_agent = from_agent
        self.to_agent = to_agent  # Can be an agent_id, department name, or "all"
        self.content = content
        self.msg_type = msg_type  # task_assignment, question, response, status_update, deliverable, escalation
        self.channel = channel  # direct, department_broadcast, cross_department, escalation
        self.priority = priority  # low, medium, high, urgent
        self.context = context
        self.round_number = round_number
        self.read = False

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
        }

    def format_display(self) -> str:
        """Format for display in agent context."""
        priority_icon = {
            "low": "◻️",
            "medium": "◼️",
            "high": "🔶",
            "urgent": "🔴",
        }.get(self.priority, "◼️")
        return f"{priority_icon} [{self.msg_type}] From {self.from_agent}: {self.content}"


class MessageBoard:
    """
    Centralized communication hub for all agent messages.
    Supports multiple channels and message types.
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
        )

    def post_question(
        self,
        from_agent: str,
        to_agent: str,
        question: str,
        context: str = "",
        round_number: int = 0,
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
        )

    def post_deliverable(
        self,
        from_agent: str,
        to_agent: str,
        deliverable: str,
        context: str = "",
        round_number: int = 0,
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

    def format_inbox(self, agent_id: str, unread_only: bool = True) -> str:
        """Format an agent's inbox for LLM context."""
        messages = self.get_for_agent(agent_id, unread_only=unread_only)
        if not messages:
            return "No new messages."
        lines = [f"INBOX ({len(messages)} message{'s' if len(messages) != 1 else ''}):\n"]
        for msg in messages:
            lines.append(msg.format_display())
            lines.append("")
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

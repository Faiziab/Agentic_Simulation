"""
Chat Chains for R&D Simulation.
Implements ChatDev-style structured multi-turn dialogues between agent pairs.
Instead of single-shot messages, agents have back-and-forth conversations
until they reach agreement or exhaust the turn limit.
"""

from typing import Optional
from simulation.communication import MessageBoard


class ChatChain:
    """
    A structured multi-turn dialogue between two agents.
    Agents alternate responses until convergence or max turns.
    """

    def __init__(
        self,
        initiator_id: str,
        responder_id: str,
        topic: str,
        context: str = "",
        max_turns: int = 4,
        round_number: int = 0,
    ):
        self.initiator_id = initiator_id
        self.responder_id = responder_id
        self.topic = topic
        self.context = context
        self.max_turns = max_turns
        self.round_number = round_number
        self.turns: list[dict] = []
        self.concluded = False
        self.conclusion: str = ""

    def add_turn(self, speaker_id: str, content: str):
        """Record a turn in the conversation."""
        self.turns.append({
            "turn": len(self.turns) + 1,
            "speaker": speaker_id,
            "content": content,
        })

    def get_conversation_history(self) -> str:
        """Format conversation so far for the next speaker's context."""
        if not self.turns:
            return ""
        lines = [f"ONGOING CONVERSATION about: {self.topic}\n"]
        for turn in self.turns:
            lines.append(f"[Turn {turn['turn']}] {turn['speaker']}: {turn['content']}\n")
        return "\n".join(lines)

    def is_complete(self) -> bool:
        """Check if the chain has concluded."""
        return self.concluded or len(self.turns) >= self.max_turns

    def to_dict(self) -> dict:
        return {
            "initiator": self.initiator_id,
            "responder": self.responder_id,
            "topic": self.topic,
            "turns": self.turns,
            "total_turns": len(self.turns),
            "concluded": self.concluded,
            "conclusion": self.conclusion,
            "round": self.round_number,
        }


class ChatChainRunner:
    """
    Runs chat chains between agent pairs.
    Manages the multi-turn dialogue flow.
    """

    def __init__(self, max_turns: int = 4):
        self.max_turns = max_turns
        self.completed_chains: list[ChatChain] = []

    def run_chain(
        self,
        initiator,  # Agent object
        responder,  # Agent object
        topic: str,
        initial_message: str,
        context: str = "",
        round_number: int = 0,
        message_board: Optional[MessageBoard] = None,
        logger=None,
    ) -> ChatChain:
        """
        Run a full chat chain between two agents.

        Turn 1: Initiator sends the opening message (already provided)
        Turn 2: Responder replies
        Turn 3: Initiator follows up
        Turn 4: Responder provides final response
        ... continues until max_turns or convergence
        """
        chain = ChatChain(
            initiator_id=initiator.agent_id,
            responder_id=responder.agent_id,
            topic=topic,
            context=context,
            max_turns=self.max_turns,
            round_number=round_number,
        )

        # Turn 1: Initiator's opening message
        chain.add_turn(initiator.agent_id, initial_message)

        if logger:
            logger.log_communication(
                from_agent=initiator.agent_id,
                to_agent=responder.agent_id,
                msg_type="chat_chain_start",
                content_preview=f"[Chain: {topic}] {initial_message[:100]}",
                round_number=round_number,
            )

        # Alternate turns
        current_speaker = responder
        other_speaker = initiator

        for turn_num in range(2, self.max_turns + 1):
            conversation_so_far = chain.get_conversation_history()
            is_final_turn = (turn_num == self.max_turns)

            prompt = self._build_turn_prompt(
                speaker=current_speaker,
                other=other_speaker,
                topic=topic,
                conversation_history=conversation_so_far,
                context=context,
                turn_number=turn_num,
                max_turns=self.max_turns,
                is_final_turn=is_final_turn,
            )

            response = current_speaker.think(prompt, round_number=round_number)
            chain.add_turn(current_speaker.agent_id, response)

            # Store in memory
            current_speaker.memory_stream.add_memory(
                content=f"Chat chain with {other_speaker.name} about '{topic}' (turn {turn_num}): {response[:200]}",
                memory_type="communication",
                importance=6,
                related_agent=other_speaker.agent_id,
                round_number=round_number,
            )

            if logger:
                logger.log_communication(
                    from_agent=current_speaker.agent_id,
                    to_agent=other_speaker.agent_id,
                    msg_type=f"chat_chain_turn_{turn_num}",
                    content_preview=f"[Chain: {topic}] {response[:100]}",
                    round_number=round_number,
                )

            # Post to message board
            if message_board:
                message_board.post(
                    from_agent=current_speaker.agent_id,
                    to_agent=other_speaker.agent_id,
                    content=response,
                    msg_type="chat_chain",
                    channel="cross_department",
                    context=f"Chat chain: {topic} (turn {turn_num}/{self.max_turns})",
                    round_number=round_number,
                )

            # Check for convergence keywords
            if self._check_convergence(response):
                chain.concluded = True
                chain.conclusion = response
                break

            # Swap speakers
            current_speaker, other_speaker = other_speaker, current_speaker

        # If not explicitly concluded, use last turn as conclusion
        if not chain.concluded:
            chain.concluded = True
            chain.conclusion = chain.turns[-1]["content"]

        self.completed_chains.append(chain)

        if logger:
            logger.log_communication(
                from_agent=chain.initiator_id,
                to_agent=chain.responder_id,
                msg_type="chat_chain_complete",
                content_preview=f"[Chain concluded after {len(chain.turns)} turns: {topic}]",
                round_number=round_number,
            )

        return chain

    def _build_turn_prompt(
        self,
        speaker,
        other,
        topic: str,
        conversation_history: str,
        context: str,
        turn_number: int,
        max_turns: int,
        is_final_turn: bool,
    ) -> str:
        """Build the prompt for a conversation turn."""
        final_instruction = ""
        if is_final_turn:
            final_instruction = """
THIS IS THE FINAL TURN. You must:
1. Summarize the key agreements and conclusions reached
2. List any remaining open questions
3. State your final position clearly
End with "CONCLUSION:" followed by the agreed-upon outcome."""

        prompt = f"""You are in a multi-turn conversation with {other.name} ({other.title}).

TOPIC: {topic}

{conversation_history}

{f"BACKGROUND CONTEXT: {context}" if context else ""}

INSTRUCTIONS FOR THIS TURN (Turn {turn_number}/{max_turns}):
- Respond naturally as yourself, staying in character
- Build on what's been said — don't repeat points already made
- If you agree with something, say so explicitly and build on it
- If you disagree, explain why with evidence from your expertise
- Ask clarifying questions if needed
- Be concise but substantive — this is a focused work discussion
{final_instruction}

Your response:"""

        return prompt

    def _check_convergence(self, response: str) -> bool:
        """Check if the conversation has naturally concluded."""
        convergence_signals = [
            "CONCLUSION:",
            "we're aligned",
            "I think we've covered",
            "sounds like we agree",
            "that settles it",
            "we have a clear path",
            "I'm satisfied with",
            "let's go with that",
        ]
        response_lower = response.lower()
        return any(signal.lower() in response_lower for signal in convergence_signals)

    def get_chain_summary(self, chain: ChatChain) -> str:
        """Generate a summary of a completed chat chain."""
        lines = [
            f"### Chat Chain: {chain.topic}",
            f"**Between:** {chain.initiator_id} ↔ {chain.responder_id}",
            f"**Turns:** {len(chain.turns)}",
            "",
        ]
        for turn in chain.turns:
            lines.append(f"**[Turn {turn['turn']}] {turn['speaker']}:**")
            lines.append(turn["content"])
            lines.append("")

        if chain.conclusion:
            lines.append(f"**Conclusion:** {chain.conclusion}")

        return "\n".join(lines)

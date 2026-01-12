"""Rolling Semantic Summary memory strategy.

滚动语义摘要メモリ戦略.

This strategy (type=1) compresses conversation history into a rolling
natural-language summary, keeping only the most recent K messages in full.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from utils.memory.base import BaseMemory

if TYPE_CHECKING:
    from aiwolf_nlp_common.packet import Talk
    from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)


SUMMARIZE_SYSTEM_PROMPT = """You are a memory compression assistant for a Werewolf game AI.

Your task is to update a running summary of the game based on new events.

RULES:
- Keep: facts, role claims, votes, accusations, deaths, divine results
- Remove: small talk, filler, redundant information
- Be concise but comprehensive
- Maximum 500 characters for the summary
- Write in third person, past tense
- Focus on information useful for deduction

Output ONLY the updated summary, nothing else."""

SUMMARIZE_USER_TEMPLATE = """Current Summary:
{old_summary}

New Events:
{new_events}

Write the updated summary (max 500 chars):"""


class RollingSummaryMemory(BaseMemory):
    """Rolling semantic summary memory.

    滚动语义摘要メモリ.

    Maintains:
    - A compressed natural-language summary of past events
    - A buffer of the last K raw messages for immediate context
    """

    def __init__(
        self,
        config: dict[str, Any],
        llm_model: BaseChatModel,
        agent_name: str,
        buffer_size: int = 5,
    ) -> None:
        """Initialize RollingSummaryMemory.

        Args:
            config: Configuration dictionary
            llm_model: LangChain chat model for summarization
            agent_name: Name of the agent
            buffer_size: Number of recent messages to keep in full
        """
        super().__init__(config, agent_name)
        self._llm = llm_model
        self._buffer_size = buffer_size

        # State
        self._summary: str = ""
        self._recent_buffer: list[dict[str, str]] = []
        self._pending_events: list[str] = []  # Events to summarize at turn end

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the recent buffer.

        Args:
            role: Message role
            content: Message content
        """
        self._recent_buffer.append({"role": role, "content": content})
        self._pending_events.append(f"[{role.upper()}]: {content}")

        # Keep only the last buffer_size messages
        if len(self._recent_buffer) > self._buffer_size:
            self._recent_buffer.pop(0)

    def add_talk(self, talk: Talk) -> None:
        """Add a game talk to pending events.

        Args:
            talk: Talk object from the game
        """
        event_str = f"{talk.agent}: {talk.text}"
        self._pending_events.append(event_str)
        
        # Also add to recent buffer so it appears in memory context
        self._recent_buffer.append({"role": "game", "content": event_str})
        
        # Keep only the last buffer_size messages
        if len(self._recent_buffer) > self._buffer_size:
            self._recent_buffer.pop(0)


    def get_memory_context(self) -> str:
        """Get the memory context for prompt injection.

        Returns:
            str: Formatted memory with summary and recent messages
        """
        parts = []

        if self._summary:
            parts.append("[MEMORY_SUMMARY]")
            parts.append(self._summary)
            parts.append("")

        if self._recent_buffer:
            parts.append("[RECENT_MESSAGES]")
            for msg in self._recent_buffer:
                parts.append(f"[{msg['role'].upper()}]: {msg['content']}")

        return "\n".join(parts)

    def on_turn_end(self, events: dict[str, Any]) -> None:
        """Update the summary at turn end.

        Args:
            events: Game events from the turn
        """
        # Add any game events to pending
        if events:
            for key, value in events.items():
                if value:
                    self._pending_events.append(f"[{key}]: {value}")

        if not self._pending_events:
            return

        # Build the new events string
        new_events = "\n".join(self._pending_events[-20:])  # Limit to last 20 events

        try:
            # Call LLM to update summary
            messages = [
                SystemMessage(content=SUMMARIZE_SYSTEM_PROMPT),
                HumanMessage(content=SUMMARIZE_USER_TEMPLATE.format(
                    old_summary=self._summary or "(No previous summary)",
                    new_events=new_events,
                )),
            ]

            chain = self._llm | StrOutputParser()
            new_summary = chain.invoke(messages)

            # Truncate if too long
            if len(new_summary) > 500:
                new_summary = new_summary[:497] + "..."

            old_summary = self._summary
            self._summary = new_summary.strip()
            logger.debug("Updated rolling summary: %s", self._summary)

            # Log the summary update
            self._log(f"[SUMMARY_UPDATE]")
            self._log(f"Old: {old_summary[:200]}..." if len(old_summary) > 200 else f"Old: {old_summary}")
            self._log(f"New: {self._summary}")
            self._log(f"Events processed: {len(self._pending_events)}")

        except Exception:
            logger.exception("Failed to update rolling summary")

        # Clear pending events after processing
        self._pending_events.clear()

    def clear(self) -> None:
        """Clear all memory for a new game."""
        self._summary = ""
        self._recent_buffer.clear()
        self._pending_events.clear()
        self._log("[MEMORY_CLEARED]")


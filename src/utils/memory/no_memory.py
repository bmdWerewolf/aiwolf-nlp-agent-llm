"""No Memory strategy - baseline behavior.

メモリなし戦略 - ベースライン動作.

This is the default strategy (type=0) that maintains full message history
without any compression or summarization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from utils.memory.base import BaseMemory

if TYPE_CHECKING:
    from aiwolf_nlp_common.packet import Talk


class NoMemory(BaseMemory):
    """No memory management - keeps full history.

    メモリ管理なし - 完全な履歴を保持.

    This strategy simply stores all messages and returns them as-is.
    It provides the same behavior as the original agent without memory management.
    """

    def __init__(self, config: dict[str, Any], agent_name: str) -> None:
        """Initialize NoMemory.

        Args:
            config: Configuration dictionary
            agent_name: Name of the agent
        """
        super().__init__(config, agent_name)
        self._messages: list[dict[str, str]] = []
        self._talks: list[Talk] = []

    def add_message(self, role: str, content: str) -> None:
        """Add a message to history.

        Args:
            role: Message role
            content: Message content
        """
        self._messages.append({"role": role, "content": content})

    def add_talk(self, talk: Talk) -> None:
        """Add a game talk to history.

        Args:
            talk: Talk object from the game
        """
        self._talks.append(talk)

    def get_memory_context(self) -> str:
        """Get empty context (no memory injection).

        NoMemory doesn't inject any additional context.
        The agent will use the standard prompt templates.

        Returns:
            str: Empty string (no memory context)
        """
        # NoMemory returns empty - the agent uses its native history handling
        return ""

    def on_turn_end(self, events: dict[str, Any]) -> None:
        """No-op for NoMemory.

        Args:
            events: Game events (ignored)
        """
        # NoMemory doesn't process turn-end events
        pass

    def clear(self) -> None:
        """Clear all stored history."""
        self._messages.clear()
        self._talks.clear()

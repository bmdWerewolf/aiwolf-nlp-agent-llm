"""Base class for memory management strategies.

メモリ管理戦略の基底クラス.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aiwolf_nlp_common.packet import Talk


class BaseMemory(ABC):
    """Abstract base class for all memory strategies.

    全てのメモリ戦略の抽象基底クラス.
    """

    def __init__(self, config: dict[str, Any], agent_name: str) -> None:
        """Initialize base memory.

        Args:
            config: Configuration dictionary
            agent_name: Name of the agent using this memory
        """
        self.config = config
        self.agent_name = agent_name
        self._logger: logging.Logger | None = None

    def set_logger(self, logger: logging.Logger) -> None:
        """Set the logger for memory decision tracking.

        メモリ決策追跡用のロガーを設定する.

        Args:
            logger: Logger instance for memory logging
        """
        self._logger = logger

    def _log(self, message: str) -> None:
        """Log a message if logger is available.

        Args:
            message: Message to log
        """
        if self._logger:
            self._logger.info(message)

    @abstractmethod
    def add_message(self, role: str, content: str) -> None:
        """Add a message to memory.

        メモリにメッセージを追加する.

        Args:
            role: Message role ("user", "assistant", "system")
            content: Message content
        """
        ...

    @abstractmethod
    def add_talk(self, talk: Talk) -> None:
        """Add a game talk/whisper to memory.

        ゲームの発言をメモリに追加する.

        Args:
            talk: Talk object from the game
        """
        ...

    @abstractmethod
    def get_memory_context(self) -> str:
        """Get the memory context to inject into prompts.

        プロンプトに注入するメモリコンテキストを取得する.

        Returns:
            str: Formatted memory context string
        """
        ...

    @abstractmethod
    def on_turn_end(self, events: dict[str, Any]) -> None:
        """Process end-of-turn updates.

        ターン終了時の更新処理を行う.

        Args:
            events: Dictionary of game events from the turn
                    (e.g., votes, attacks, divine results)
        """
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear all memory for a new game.

        新しいゲームのためにメモリをクリアする.
        """
        ...

    def get_memory_type(self) -> int:
        """Get the memory type from config.

        Returns:
            int: Memory type (0-3)
        """
        return int(self.config.get("memory", {}).get("type", 0))


"""Module for managing agent memory and conversation history.

エージェントのメモリーと会話履歴を管理するモジュール.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeAlias

from langchain_core.messages import AIMessage, HumanMessage

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage

from aiwolf_nlp_common.packet import Talk

# Type aliases for memory summaries
MemorySummary: TypeAlias = dict[str, str]
FullStateSummary: TypeAlias = dict[str, Any]


@dataclass
class CompressedMemory:
    """Represents a compressed summary of conversation history.

    会話履歴の圧縮されたサマリーを表す.
    """

    timestamp: str
    summary: str
    message_count: int
    start_turn: int
    end_turn: int


class ConversationMemory:
    """Manages conversation history and automatic compression.

    会話履歴を管理し、自動的に圧縮する.
    """

    def __init__(
        self,
        agent_name: str,
        threshold: int = 10,
        compress_count: int = 5,
    ) -> None:
        """Initialize conversation memory.

        会話メモリーを初期化する.

        Args:
            agent_name (str): Name of the agent / エージェント名
            threshold (int): Number of messages before compression is triggered / 圧縮をトリガーするメッセージ数 (デフォルト: 10)
            compress_count (int): Number of oldest messages to compress / 圧縮する最古のメッセージ数 (デフォルト: 5)
        """
        self.agent_name = agent_name
        self.threshold = threshold
        self.compress_count = compress_count

        self.messages: list[BaseMessage] = []
        self.compressed_memories: list[CompressedMemory] = []
        self.conversation_turn: int = 0

    def add_message(self, message: BaseMessage) -> None:
        """Add a message to conversation memory.

        メッセージを会話メモリーに追加する.

        Args:
            message (BaseMessage): Message to add (HumanMessage or AIMessage) / 追加するメッセージ
        """
        self.messages.append(message)
        self.conversation_turn += 1

        # Check if compression is needed
        if len(self.messages) >= self.threshold:
            self._compress_old_messages()

    def add_human_message(self, content: str) -> None:
        """Add a human message to conversation memory.

        ユーザーメッセージを会話メモリーに追加する.

        Args:
            content (str): Message content / メッセージ内容
        """
        self.add_message(HumanMessage(content=content))

    def add_ai_message(self, content: str) -> None:
        """Add an AI message to conversation memory.

        AIメッセージを会話メモリーに追加する.

        Args:
            content (str): Message content / メッセージ内容
        """
        self.add_message(AIMessage(content=content))

    def get_recent_messages(self, count: int | None = None) -> list[BaseMessage]:
        """Get recent messages from memory.

        メモリーから最近のメッセージを取得する.

        Args:
            count (int | None): Number of recent messages to retrieve / 取得する最近のメッセージ数

        Returns:
            list[BaseMessage]: List of recent messages / 最近のメッセージのリスト
        """
        if count is None:
            count = max(1, self.threshold - self.compress_count)
        return self.messages[-count:] if len(self.messages) > count else self.messages

    def get_full_context(self) -> list[BaseMessage]:
        """Get full conversation context including compressed memories.

        圧縮されたメモリーを含む完全な会話コンテキストを取得する.

        Returns:
            list[BaseMessage]: Full conversation context / 完全な会話コンテキスト
        """
        context: list[BaseMessage] = []

        # Add compressed memories as system context
        if self.compressed_memories:
            for compressed in self.compressed_memories:
                summary_msg = HumanMessage(
                    content=f"[Previous context summary]\n"
                    f"Turn {compressed.start_turn}-{compressed.end_turn}: {compressed.summary}"
                )
                context.append(summary_msg)

        # Add recent messages
        context.extend(self.get_recent_messages())
        return context

    def get_memory_summary(self) -> MemorySummary:
        """Get memory usage summary.

        メモリー使用状況のサマリーを取得する.

        Returns:
            MemorySummary: Summary including message count, compressed memories count, etc. / メッセージ数や圧縮メモリー数などを含むサマリー
        """
        return {
            "agent_name": self.agent_name,
            "current_messages": str(len(self.messages)),
            "compressed_memories": str(len(self.compressed_memories)),
            "conversation_turn": str(self.conversation_turn),
            "total_context_length": str(len(self.get_full_context())),
        }

    def _compress_old_messages(self) -> None:
        """Compress old messages into a summary.

        古いメッセージをサマリーに圧縮する.
        """
        if len(self.messages) < self.compress_count:
            return

        messages_to_compress = self.messages[: self.compress_count]
        remaining_messages = self.messages[self.compress_count :]

        # Build summary from compressed messages
        summary = self._build_summary(messages_to_compress)

        # Create compressed memory record
        compressed = CompressedMemory(
            timestamp=datetime.now().isoformat(),
            summary=summary,
            message_count=len(messages_to_compress),
            start_turn=self.conversation_turn - len(self.messages),
            end_turn=self.conversation_turn - len(remaining_messages),
        )
        self.compressed_memories.append(compressed)

        # Keep only recent messages
        self.messages = remaining_messages

    def _build_summary(self, messages: list[BaseMessage]) -> str:
        """Build a summary from a list of messages.

        メッセージのリストからサマリーを構築する.

        Args:
            messages (list[BaseMessage]): Messages to summarize / サマリーするメッセージ

        Returns:
            str: Summary of the messages / メッセージのサマリー
        """
        summary_parts: list[str] = []

        for msg in messages:
            if isinstance(msg.content, str): # type: ignore
                content_str = msg.content
            elif isinstance(msg.content, list): # type: ignore
                content_str = str(msg.content) # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
            else:
                content_str = str(msg.content)
            if isinstance(msg, HumanMessage):
                summary_parts.append(f"User: {content_str[:100]}...")
            elif isinstance(msg, AIMessage):
                summary_parts.append(f"Assistant: {content_str[:100]}...")

        return " | ".join(summary_parts) if summary_parts else "No messages to summarize"

    def clear(self) -> None:
        """Clear all memories.

        すべてのメモリーをクリアする.
        """
        self.messages = []
        self.compressed_memories = []
        self.conversation_turn = 0


class TalkHistoryMemory:
    """Manages talk history with automatic summarization.

    発言履歴を管理し、自動的に要約する.
    """

    def __init__(
        self,
        agent_name: str,
        threshold: int = 10,
        compress_count: int = 5,
    ) -> None:
        """Initialize talk history memory.

        発言履歴メモリーを初期化する.

        Args:
            agent_name (str): Name of the agent / エージェント名
            threshold (int): Number of talks before compression is triggered / 圧縮をトリガーする発言数 (デフォルト: 10)
            compress_count (int): Number of oldest talks to compress / 圧縮する最古の発言数 (デフォルト: 5)
        """
        self.agent_name = agent_name
        self.threshold = threshold
        self.compress_count = compress_count

        self.talks: list[Talk] = []
        self.compressed_summaries: list[CompressedMemory] = []
        self.day_counter: int = 0

    def add_talk(self, talk: Talk) -> None:
        """Add a talk to history.

        発言を履歴に追加する.

        Args:
            talk (Talk): Talk to add / 追加する発言
        """
        self.talks.append(talk)

        # Check if compression is needed
        if len(self.talks) >= self.threshold:
            self._compress_old_talks()

    def add_talks(self, talks: list[Talk]) -> None:
        """Add multiple talks to history.

        複数の発言を履歴に追加する.

        Args:
            talks (list[Talk]): List of talks to add / 追加する発言のリスト
        """
        for talk in talks:
            self.add_talk(talk)

    def get_recent_talks(self, count: int | None = None) -> list[Talk]:
        """Get recent talks from history.

        履歴から最近の発言を取得する.

        Args:
            count (int | None): Number of recent talks to retrieve / 取得する最近の発言数

        Returns:
            list[Talk]: List of recent talks / 最近の発言のリスト
        """
        if count is None:
            count = max(1, self.threshold - self.compress_count)
        return self.talks[-count:] if len(self.talks) > count else self.talks

    def get_talks_by_agent(self, agent_name: str) -> list[Talk]:
        """Get talks from a specific agent.

        特定のエージェントからの発言を取得する.

        Args:
            agent_name (str): Name of the agent / エージェント名

        Returns:
            list[Talk]: List of talks from the specified agent / 指定されたエージェントからの発言のリスト
        """
        return [talk for talk in self.talks if talk.agent == agent_name]

    def get_full_talk_history(self) -> list[Talk]:
        """Get full talk history including compressed summaries.

        圧縮されたサマリーを含む完全な発言履歴を取得する.

        Returns:
            list[Talk]: Full talk history / 完全な発言履歴
        """
        # For now, return recent talks
        # In practice, summaries would be reconstructed as Talk objects
        return self.get_recent_talks()

    def get_memory_summary(self) -> MemorySummary:
        """Get memory usage summary.

        メモリー使用状況のサマリーを取得する.

        Returns:
            MemorySummary: Summary including talk count, compressed summaries, etc. / 発言数や圧縮サマリー数などを含むサマリー
        """
        return {
            "agent_name": self.agent_name,
            "current_talks": str(len(self.talks)),
            "compressed_summaries": str(len(self.compressed_summaries)),
            "day_counter": str(self.day_counter),
        }

    def _compress_old_talks(self) -> None:
        """Compress old talks into a summary.

        古い発言をサマリーに圧縮する.
        """
        if len(self.talks) < self.compress_count:
            return

        talks_to_compress = self.talks[: self.compress_count]
        remaining_talks = self.talks[self.compress_count :]

        # Build summary from compressed talks
        summary = self._build_talk_summary(talks_to_compress)

        # Create compressed memory record
        compressed = CompressedMemory(
            timestamp=datetime.now().isoformat(),
            summary=summary,
            message_count=len(talks_to_compress),
            start_turn=self.day_counter,
            end_turn=self.day_counter + len(talks_to_compress),
        )
        self.compressed_summaries.append(compressed)

        # Keep only recent talks
        self.talks = remaining_talks

    def _build_talk_summary(self, talks: list[Talk]) -> str:
        """Build a summary from a list of talks.

        発言のリストからサマリーを構築する.

        Args:
            talks (list[Talk]): Talks to summarize / サマリーする発言

        Returns:
            str: Summary of the talks / 発言のサマリー
        """
        summary_parts: list[str] = []
        agent_talk_count: dict[str, int] = {}

        for talk in talks:
            agent = talk.agent if hasattr(talk, "agent") else "Unknown"
            agent_talk_count[agent] = agent_talk_count.get(agent, 0) + 1

            # Include key content snippets
            content = getattr(talk, "content", None)
            if content is not None:
                content_preview = str(content)[:50]
                summary_parts.append(f"{agent}: {content_preview}...")

        if not summary_parts:
            return "No talks to summarize"

        # Add agent activity summary
        agent_summary = ", ".join([f"{agent}({count})" for agent, count in agent_talk_count.items()])
        return f"[Agents: {agent_summary}] " + " | ".join(summary_parts[:3])

    def advance_day(self) -> None:
        """Advance to the next day.

        次の日に進める.
        """
        self.day_counter += 1

    def clear(self) -> None:
        """Clear all talk history.

        すべての発言履歴をクリアする.
        """
        self.talks = []
        self.compressed_summaries = []


class WhisperHistoryMemory:
    """Manages whisper history with automatic summarization.

    囁き履歴を管理し、自動的に要約する.
    """

    def __init__(
        self,
        agent_name: str,
        threshold: int = 10,
        compress_count: int = 5,
    ) -> None:
        """Initialize whisper history memory.

        囁き履歴メモリーを初期化する.

        Args:
            agent_name (str): Name of the agent / エージェント名
            threshold (int): Number of whispers before compression is triggered / 圧縮をトリガーする囁き数 (デフォルト: 10)
            compress_count (int): Number of oldest whispers to compress / 圧縮する最古の囁き数 (デフォルト: 5)
        """
        self.agent_name = agent_name
        self.threshold = threshold
        self.compress_count = compress_count

        self.whispers: list[Talk] = []
        self.compressed_summaries: list[CompressedMemory] = []
        self.night_counter: int = 0

    def add_whisper(self, whisper: Talk) -> None:
        """Add a whisper to history.

        囁きを履歴に追加する.

        Args:
            whisper (Talk): Whisper to add / 追加する囁き
        """
        self.whispers.append(whisper)

        # Check if compression is needed
        if len(self.whispers) >= self.threshold:
            self._compress_old_whispers()

    def add_whispers(self, whispers: list[Talk]) -> None:
        """Add multiple whispers to history.

        複数の囁きを履歴に追加する.

        Args:
            whispers (list[Talk]): List of whispers to add / 追加する囁きのリスト
        """
        for whisper in whispers:
            self.add_whisper(whisper)

    def get_recent_whispers(self, count: int | None = None) -> list[Talk]:
        """Get recent whispers from history.

        履歴から最近の囁きを取得する.

        Args:
            count (int | None): Number of recent whispers to retrieve / 取得する最近の囁き数

        Returns:
            list[Talk]: List of recent whispers / 最近の囁きのリスト
        """
        if count is None:
            count = max(1, self.threshold - self.compress_count)
        return self.whispers[-count:] if len(self.whispers) > count else self.whispers

    def get_whispers_to_target(self, target_agent: str) -> list[Talk]:
        """Get whispers to a specific target agent.

        特定の対象エージェントへの囁きを取得する.

        Args:
            target_agent (str): Name of the target agent / 対象エージェント名

        Returns:
            list[Talk]: List of whispers to the target agent / 対象エージェントへの囁きのリスト
        """
        return [whisper for whisper in self.whispers if getattr(whisper, "target", None) == target_agent]

    def get_memory_summary(self) -> MemorySummary:
        """Get memory usage summary.

        メモリー使用状況のサマリーを取得する.

        Returns:
            MemorySummary: Summary including whisper count, compressed summaries, etc. / 囁き数や圧縮サマリー数などを含むサマリー
        """
        return {
            "agent_name": self.agent_name,
            "current_whispers": str(len(self.whispers)),
            "compressed_summaries": str(len(self.compressed_summaries)),
            "night_counter": str(self.night_counter),
        }

    def _compress_old_whispers(self) -> None:
        """Compress old whispers into a summary.

        古い囁きをサマリーに圧縮する.
        """
        if len(self.whispers) < self.compress_count:
            return

        whispers_to_compress = self.whispers[: self.compress_count]
        remaining_whispers = self.whispers[self.compress_count :]

        # Build summary from compressed whispers
        summary = self._build_whisper_summary(whispers_to_compress)

        # Create compressed memory record
        compressed = CompressedMemory(
            timestamp=datetime.now().isoformat(),
            summary=summary,
            message_count=len(whispers_to_compress),
            start_turn=self.night_counter,
            end_turn=self.night_counter + len(whispers_to_compress),
        )
        self.compressed_summaries.append(compressed)

        # Keep only recent whispers
        self.whispers = remaining_whispers

    def _build_whisper_summary(self, whispers: list[Talk]) -> str:
        """Build a summary from a list of whispers.

        囁きのリストからサマリーを構築する.

        Args:
            whispers (list[Talk]): Whispers to summarize / サマリーする囁き

        Returns:
            str: Summary of the whispers / 囁きのサマリー
        """
        summary_parts = [] # type: ignore
        target_summary: dict[str, int] = {}

        for whisper in whispers:
            target = getattr(whisper, "target", "Unknown")
            target_summary[target] = target_summary.get(target, 0) + 1

        if not target_summary:
            return "No whispers to summarize"

        target_list = ", ".join([f"{target}({count})" for target, count in target_summary.items()])
        return f"[Whispered to: {target_list}]"

    def advance_night(self) -> None:
        """Advance to the next night.

        次の夜に進める.
        """
        self.night_counter += 1

    def clear(self) -> None:
        """Clear all whisper history.

        すべての囁き履歴をクリアする.
        """
        self.whispers = []
        self.compressed_summaries = []


class AgentMemoryManager:
    """Unified memory manager for agent conversation, talks, and whispers.

    エージェントの会話、発言、囁きを統一的に管理するメモリーマネージャー.
    """

    def __init__(
        self,
        agent_name: str,
        config: dict | None = None, # type: ignore
    ) -> None:
        """Initialize agent memory manager.

        エージェントメモリーマネージャーを初期化する.

        Args:
            agent_name (str): Name of the agent / エージェント名
            config (dict | None): Configuration dictionary with optional memory settings / メモリー設定を含む設定辞書
        """
        self.agent_name = agent_name

        # Load configuration
        threshold = 10
        compress_count = 5
        if config and "memory" in config:
            threshold = config["memory"].get("threshold", 10) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
            compress_count = config["memory"].get("compress_count", 5) # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

        # Initialize memory managers
        self.conversation = ConversationMemory(agent_name, threshold, compress_count) # type: ignore
        self.talk_history = TalkHistoryMemory(agent_name, threshold, compress_count) # type: ignore
        self.whisper_history = WhisperHistoryMemory(agent_name, threshold, compress_count) # type: ignore

    def update_from_agent(self, agent: object) -> None:
        """Update memory from agent object.

        エージェントオブジェクトからメモリーを更新する.

        Args:
            agent (object): Agent instance with llm_message_history, talk_history, whisper_history attributes / 属性を持つエージェントインスタンス
        """
        # Update conversation memory from llm_message_history
        if hasattr(agent, "llm_message_history"):
            for msg in getattr(agent, "llm_message_history"):
                if msg not in self.conversation.messages:
                    self.conversation.add_message(msg)

        # Update talk history
        if hasattr(agent, "talk_history"):
            self.talk_history.add_talks(getattr(agent, "talk_history"))

        # Update whisper history
        if hasattr(agent, "whisper_history"):
            self.whisper_history.add_whispers(getattr(agent, "whisper_history"))

    def get_conversation_context(self) -> list[BaseMessage]:
        """Get conversation context for LLM.

        LLM用の会話コンテキストを取得する.

        Returns:
            list[BaseMessage]: Conversation context / 会話コンテキスト
        """
        return self.conversation.get_full_context()

    def get_full_state_summary(self) -> FullStateSummary:
        """Get full summary of all memories.

        すべてのメモリーの完全なサマリーを取得する.

        Returns:
            FullStateSummary: Full state summary / 完全な状態サマリー
        """
        return {
            "agent_name": self.agent_name,
            "conversation": self.conversation.get_memory_summary(),
            "talk_history": self.talk_history.get_memory_summary(),
            "whisper_history": self.whisper_history.get_memory_summary(),
        }

    def clear_all(self) -> None:
        """Clear all memories.

        すべてのメモリーをクリアする.
        """
        self.conversation.clear()
        self.talk_history.clear()
        self.whisper_history.clear()

    def reset_day_cycle(self) -> None:
        """Reset day cycle counters.

        日のサイクルカウンターをリセットする.
        """
        self.talk_history.advance_day()

    def reset_night_cycle(self) -> None:
        """Reset night cycle counters.

        夜のサイクルカウンターをリセットする.
        """
        self.whisper_history.advance_night()

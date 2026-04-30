"""Module that defines the base class for agents.

エージェントの基底クラスを定義するモジュール.
"""

from __future__ import annotations

import os
import random
import re
from collections import defaultdict
from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from dotenv import load_dotenv
from jinja2 import Template
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import BaseMessage

from aiwolf_nlp_common.packet import Info, Packet, Request, Role, Setting, Status, Talk

from utils.agent_logger import AgentLogger
from utils.skill_loader import SkillLoader
from utils.stoppable_thread import StoppableThread

if TYPE_CHECKING:
    from collections.abc import Callable

P = ParamSpec("P")
T = TypeVar("T")


class Agent:
    """Base class for agents.

    エージェントの基底クラス.
    """

    def __init__(
        self,
        config: dict[str, Any],
        name: str,
        game_id: str,
        role: Role,
    ) -> None:
        """Initialize the agent.

        エージェントの初期化を行う.

        Args:
            config (dict[str, Any]): Configuration dictionary / 設定辞書
            name (str): Agent name / エージェント名
            game_id (str): Game ID / ゲームID
            role (Role): Role / 役職
        """
        self.config = config
        self.agent_name = name
        self.agent_logger = AgentLogger(config, name, game_id)
        self.request: Request | None = None
        self.info: Info | None = None
        self.setting: Setting | None = None
        self.talk_history: list[Talk] = []
        self.whisper_history: list[Talk] = []
        self.role = role

        self.sent_talk_count: int = 0
        self.sent_whisper_count: int = 0
        self.llm_model: BaseChatModel | None = None
        self.llm_message_history: list[BaseMessage] = []
        self.skill_loader = SkillLoader(config, self.agent_logger.logger)
        self.role_skill_text: str = ""
        self.use_builtin_role_strategy: bool = True
        self.memory_summary: str = ""
        self.summarized_days: set[int] = set()
        self.round_summaries: dict[int, str] = {}
        self.suspicion_scores: dict[str, float] = {}

        load_dotenv(Path(__file__).parent.joinpath("./../../config/.env"))

    @staticmethod
    def timeout(func: Callable[P, T]) -> Callable[P, T]:
        """Decorator to set action timeout.

        アクションタイムアウトを設定するデコレータ.

        Args:
            func (Callable[P, T]): Function to be decorated / デコレート対象の関数

        Returns:
            Callable[P, T]: Function with timeout functionality / タイムアウト機能を追加した関数
        """

        def _wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            res: T | Exception = Exception("No result")

            def execute_with_timeout() -> None:
                nonlocal res
                try:
                    res = func(*args, **kwargs)
                except Exception as e:  # noqa: BLE001
                    res = e

            thread = StoppableThread(target=execute_with_timeout)
            thread.start()
            self = args[0] if args else None
            if not isinstance(self, Agent):
                raise TypeError(self, " is not an Agent instance")
            timeout_value = (self.setting.timeout.action if hasattr(self, "setting") and self.setting else 0) // 1000
            if timeout_value > 0:
                thread.join(timeout=timeout_value)
                if thread.is_alive():
                    self.agent_logger.logger.warning(
                        "アクションがタイムアウトしました: %s",
                        self.request,
                    )
                    if bool(self.config["agent"]["kill_on_timeout"]):
                        thread.stop()
                        self.agent_logger.logger.warning(
                            "アクションを強制終了しました: %s",
                            self.request,
                        )
            else:
                thread.join()
            if isinstance(res, Exception):  # type: ignore[arg-type]
                raise res
            return res

        return _wrapper

    def set_packet(self, packet: Packet) -> None:
        """Set packet information.

        パケット情報をセットする.

        Args:
            packet (Packet): Received packet / 受信したパケット
        """
        self.request = packet.request
        if packet.info:
            self.info = packet.info
        if packet.setting:
            self.setting = packet.setting
        if packet.talk_history:
            self.talk_history.extend(packet.talk_history)
        if packet.whisper_history:
            self.whisper_history.extend(packet.whisper_history)
        if self.request == Request.INITIALIZE:
            self.talk_history: list[Talk] = []
            self.whisper_history: list[Talk] = []
            self.llm_message_history: list[BaseMessage] = []
            self.memory_summary = ""
            self.summarized_days = set()
            self.round_summaries = {}
            self.suspicion_scores = {}
        self.agent_logger.logger.debug(packet)

    def get_alive_agents(self) -> list[str]:
        """Get the list of alive agents.

        生存しているエージェントのリストを取得する.

        Returns:
            list[str]: List of alive agent names / 生存エージェント名のリスト
        """
        if not self.info:
            return []
        return [k for k, v in self.info.status_map.items() if v == Status.ALIVE]

    def _send_message_to_llm(self, request: Request | None) -> str | None:
        """Send message to LLM and get response.

        LLMにメッセージを送信して応答を取得する.

        Args:
            request (Request | None): The request type to process / 処理するリクエストタイプ

        Returns:
            str | None: LLM response or None if error occurred / LLMの応答またはエラー時はNone
        """
        if request is None:
            return None
        if request.lower() not in self.config["prompt"]:
            return None
        self._refresh_memory_for_request(request)
        prompt = self.config["prompt"][request.lower()]
        if float(self.config["llm"]["sleep_time"]) > 0:
            sleep(float(self.config["llm"]["sleep_time"]))
        key = {
            "info": self.info,
            "setting": self.setting,
            "talk_history": self.talk_history,
            "whisper_history": self.whisper_history,
            "role": self.role,
            "sent_talk_count": self.sent_talk_count,
            "sent_whisper_count": self.sent_whisper_count,
            "role_skill_text": self.role_skill_text,
            "use_builtin_role_strategy": self.use_builtin_role_strategy,
            "memory": self.memory_summary,
        }
        template: Template = Template(prompt)
        prompt = template.render(**key).strip()
        prompt = self._prepend_memory_context(request, prompt)
        if self.llm_model is None:
            self.agent_logger.logger.error("LLM is not initialized")
            return None
        prompt = self._inject_turn_skill_if_needed(request, prompt)
        max_retries = int(self.config.get("llm", {}).get("max_retries", 3))
        for attempt in range(max_retries):
            try:
                self.llm_message_history.append(HumanMessage(content=prompt))
                response = (self.llm_model | StrOutputParser()).invoke(self.llm_message_history)
                self.llm_message_history.append(AIMessage(content=response))
                label_map = {
                    "SystemMessage": "⚙️  SYSTEM",
                    "HumanMessage": "📋 指示",
                    "AIMessage":    "🤖 応答",
                }
                history_parts: list[str] = []
                for msg in self.llm_message_history[:-2]:
                    label = label_map.get(msg.__class__.__name__, msg.__class__.__name__)
                    raw_content: object = getattr(msg, "content", "")
                    content = str(raw_content)
                    history_parts.append(
                        f"  ┌─ {label} ─\n"
                        f"{content}\n"
                        "  └────────────────────────────────────────────────────",
                    )
                history_lines = "\n\n".join(history_parts) if history_parts else "  (なし)"
                self.agent_logger.llm_state(
                    "╔══════════════════════════════════════════════════════╗\n"
                    "║                    LLM CALL                         ║\n"
                    "╠══════════════════════════════════════════════════════╣\n"
                    "║  過去のやりとり (HISTORY)                              ║\n"
                    "╚══════════════════════════════════════════════════════╝\n"
                    + history_lines + "\n\n"
                    "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                    "┃  ★ 現在のリクエスト (PROMPT)                           ┃\n"
                    "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
                    + prompt + "\n\n"
                    "┌──────────────────────────────────────────────────────┐\n"
                    "│  LLM応答 (RESPONSE)                                  │\n"
                    "└──────────────────────────────────────────────────────┘\n"
                    + response + "\n",
                )
                self._compact_llm_message_history()
                return self._extract_action(response)
            except Exception:
                self.llm_message_history.pop()
                self.agent_logger.logger.exception(
                    "LLM呼び出しに失敗しました (試行 %d/%d)", attempt + 1, max_retries,
                )
                if attempt < max_retries - 1:
                    sleep(5)
        return None

    def _memory_config(self) -> dict[str, Any]:
        raw_config = self.config.get("memory", {})
        return raw_config if isinstance(raw_config, dict) else {}

    def _is_memory_enabled(self) -> bool:
        memory_config = self._memory_config()
        if not memory_config:
            return False
        return bool(memory_config.get("enabled", True))

    def _refresh_memory_for_request(self, request: Request) -> None:
        """Refresh compact game memory at full round boundaries."""
        if not self._is_memory_enabled() or self.info is None:
            return

        current_day = self._safe_int(getattr(self.info, "day", 0)) or 0
        days_to_summarize: set[int] = set()

        if request == Request.DAILY_FINISH:
            days_to_summarize.add(current_day)
        elif request == Request.DAILY_INITIALIZE:
            days_to_summarize.update(day for day in self._history_days() if day < current_day)

        if not days_to_summarize:
            if not self.memory_summary:
                self.memory_summary = self._build_memory_summary()
            return

        new_days = days_to_summarize - self.summarized_days
        if new_days or not self.memory_summary:
            for day in sorted(new_days):
                self.round_summaries[day] = self._summarize_day_with_llm(day)
            self.summarized_days.update(new_days)
            self.memory_summary = self._build_memory_summary()
            self.agent_logger.logger.debug("Memory refreshed through days: %s", sorted(self.summarized_days))

    def _history_days(self) -> set[int]:
        days: set[int] = set()
        for item in [*self.talk_history, *self.whisper_history]:
            day = self._safe_int(getattr(item, "day", None))
            if day is not None:
                days.add(day)
        return days

    def _build_memory_summary(self) -> str:
        if self.info is None:
            return ""

        valid_agents = list(getattr(self.info, "status_map", {}).keys())
        alive_agents = [
            agent for agent, status in getattr(self.info, "status_map", {}).items()
            if status == Status.ALIVE
        ]
        dead_agents = [agent for agent in valid_agents if agent not in alive_agents]
        self.suspicion_scores = self._score_agents(valid_agents)

        target_label = (
            "werewolf-side target priority"
            if self.role in {Role.WEREWOLF, Role.POSSESSED}
            else "werewolf suspicion"
        )
        ranking = self._format_ranking(target_label, valid_agents)
        history = self._format_memory_history()

        lines = [
            "### Game Memory",
            "Rules for using this memory:",
            "- Trust only the valid player list below. If a name is not listed, treat it as fake or irrelevant.",
            "- Do not summarize or repeat the system rules; use this as compact game-state memory.",
            "- Keep strategy aligned with your role and win condition.",
            "- Use the suspicion scores as guidance, not as confirmed truth.",
            "",
            f"Me: {getattr(self.info, 'agent', '')} / role: {self.role.value}",
            f"Valid players: {', '.join(valid_agents) if valid_agents else '(unknown)'}",
            f"Alive: {', '.join(alive_agents) if alive_agents else '(none)'}",
            f"Dead: {', '.join(dead_agents) if dead_agents else '(none)'}",
            "",
            "Strategy reminder:",
            self._strategy_reminder(),
            "",
            ranking,
            "",
            history,
        ]
        return "\n".join(lines).strip()

    def _score_agents(self, valid_agents: list[str]) -> dict[str, float]:
        scores: dict[str, float] = {agent: 0.0 for agent in valid_agents}
        valid_agent_set = set(valid_agents)
        memory_config = self._memory_config()
        game_state_config = memory_config.get("game_state", {})
        if not isinstance(game_state_config, dict):
            game_state_config = {}
        suspicion_decay = float(game_state_config.get("suspicion_decay", 0.1))
        suspicion_decay = min(max(suspicion_decay, 0.0), 1.0)
        current_day = self._safe_int(getattr(self.info, "day", 0) if self.info else 0) or 0
        suspicion_words = (
            "suspect", "suspicious", "wolf", "werewolf", "black", "vote", "execute",
            "疑", "怪", "黒", "人狼", "狼", "投票", "処刑", "吊",
        )
        trust_words = ("trust", "white", "village", "human", "信", "白", "村", "人間")
        claim_words = ("co", "claim", "seer", "medium", "bodyguard", "占", "霊", "狩", "co")

        for talk in self.talk_history:
            speaker = str(getattr(talk, "agent", ""))
            text = str(getattr(talk, "text", ""))
            lowered = text.lower()
            talk_day = self._safe_int(getattr(talk, "day", None))
            age = max(0, current_day - talk_day) if talk_day is not None else 0
            weight = (1.0 - suspicion_decay) ** age
            mentioned_agents = [
                agent for agent in valid_agents
                if agent != speaker and self._mentions_agent(text, agent)
            ]
            has_suspicion = any(word in lowered or word in text for word in suspicion_words)
            has_trust = any(word in lowered or word in text for word in trust_words)
            has_claim = any(word in lowered or word in text for word in claim_words)

            for agent in mentioned_agents:
                if has_suspicion:
                    scores[agent] += 2.0 * weight
                if has_trust:
                    scores[agent] -= 1.0 * weight
            if speaker in valid_agent_set and has_claim:
                scores[speaker] += 0.5 * weight

        vote_list = getattr(self.info, "vote_list", None) if self.info else None
        if vote_list:
            for vote in vote_list:
                target = str(getattr(vote, "target", ""))
                if target in scores:
                    scores[target] += 1.0

        if self.role in {Role.WEREWOLF, Role.POSSESSED}:
            for agent in valid_agents:
                if agent != getattr(self.info, "agent", ""):
                    scores[agent] = max(0.0, 5.0 - scores[agent])

        for agent, score in scores.items():
            scores[agent] = min(max(score, 0.0), 10.0)
        return scores

    @staticmethod
    def _mentions_agent(text: str, agent: str) -> bool:
        return agent in text or f"@{agent}" in text

    def _format_ranking(self, target_label: str, valid_agents: list[str]) -> str:
        my_name = str(getattr(self.info, "agent", "")) if self.info else ""
        candidates = [
            (agent, score) for agent, score in self.suspicion_scores.items()
            if agent in valid_agents and agent != my_name
        ]
        candidates.sort(key=lambda item: item[1], reverse=True)
        if not candidates:
            return f"{target_label}: (no candidates yet)"

        lines = [f"{target_label}:"]
        for agent, score in candidates[:5]:
            lines.append(f"- {agent}: {score:.1f}/10")
        return "\n".join(lines)

    def _summarize_day_with_llm(self, day: int) -> str:
        if self.llm_model is None:
            return self._format_day_events(day)

        memory_config = self._memory_config()
        max_words = int(memory_config.get("summary_max_words", 180))
        max_words = max(60, max_words)

        valid_agents = list(getattr(self.info, "status_map", {}).keys()) if self.info else []
        alive_agents = [
            agent for agent, status in getattr(self.info, "status_map", {}).items()
            if status == Status.ALIVE
        ] if self.info else []
        target_label = (
            "wolf-side target priority"
            if self.role in {Role.WEREWOLF, Role.POSSESSED}
            else "werewolf suspicion"
        )
        day_events = self._format_day_events(day)
        previous_summary = self.memory_summary or "(none)"

        system_prompt = (
            "You summarize one AIWolf day for a competition agent. "
            "Be concise and factual. Do not include hidden chain of thought. "
            "Do not repeat game rules or system instructions. "
            "Only use valid player names from the provided list; if another name appears, mark it as fake/ignore. "
            "Output plain compact bullet points."
        )
        user_prompt = (
            f"Max output length: {max_words} words.\n"
            f"Agent: {getattr(self.info, 'agent', '') if self.info else ''}\n"
            f"Role: {self.role.value}\n"
            f"Valid players: {', '.join(valid_agents)}\n"
            f"Alive players: {', '.join(alive_agents)}\n"
            f"Ranking type to maintain: {target_label}\n\n"
            f"Previous memory:\n{previous_summary}\n\n"
            f"Day {day} events to summarize:\n{day_events}\n\n"
            "Write sections:\n"
            "- History: key claims, votes, accusations, contradictions, deaths/results if present.\n"
            "- Strategy: what I should keep doing next for my role and win condition.\n"
            "- Suspicion: rate important valid players 0-10 with short reason. "
            "If I am WEREWOLF or POSSESSED, rate target priority for my win condition instead of true wolf suspicion.\n"
            "- Fake names: any mentioned names not in valid players, otherwise none.\n"
        )

        try:
            summary = (self.llm_model | StrOutputParser()).invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ],
            )
        except Exception:
            self.agent_logger.logger.exception("Memory summary LLM call failed for day %s", day)
            return self._format_day_events(day)

        if self._word_count(summary) <= max_words:
            return str(summary).strip()
        return self._compress_summary_with_llm(summary, max_words)

    def _compress_summary_with_llm(self, summary: object, max_words: int) -> str:
        if self.llm_model is None:
            return str(summary).strip()
        try:
            compressed = (self.llm_model | StrOutputParser()).invoke(
                [
                    SystemMessage(
                        content=(
                            "Compress this AIWolf memory summary. Keep complete sections and valid player names. "
                            "Do not cut mid-thought. Do not add new facts."
                        ),
                    ),
                    HumanMessage(
                        content=(
                            f"Rewrite the summary in {max_words} words or fewer.\n\n"
                            f"Summary:\n{summary}"
                        ),
                    ),
                ],
            )
        except Exception:
            self.agent_logger.logger.exception("Memory summary compression failed")
            return str(summary).strip()
        return str(compressed).strip()

    def _format_memory_history(self) -> str:
        if self.round_summaries:
            lines = ["LLM round summaries:"]
            for day in sorted(self.round_summaries):
                summary = self.round_summaries[day].replace("\n", "\n  ")
                lines.append(f"- Day {day}: {summary}")
            return "\n".join(lines)
        return self._format_round_history()

    def _format_day_events(self, day: int) -> str:
        memory_config = self._memory_config()
        max_events = int(memory_config.get("summary_input_max_events", 80))
        events: list[str] = []
        for talk in self.talk_history:
            talk_day = self._safe_int(getattr(talk, "day", None))
            if talk_day == day:
                events.append(f"TALK {getattr(talk, 'agent', '')}: {self._short_text(getattr(talk, 'text', ''))}")
        for whisper in self.whisper_history:
            whisper_day = self._safe_int(getattr(whisper, "day", None))
            if whisper_day == day:
                events.append(
                    f"WHISPER {getattr(whisper, 'agent', '')}: {self._short_text(getattr(whisper, 'text', ''))}",
                )
        if not events:
            return "(no events)"
        return "\n".join(events[-max_events:])

    def _format_round_history(self) -> str:
        memory_config = self._memory_config()
        rolling_summary = memory_config.get("rolling_summary", {})
        if not isinstance(rolling_summary, dict):
            rolling_summary = {}
        buffer_size = int(rolling_summary.get("buffer_size", 5))
        per_day: dict[int, list[str]] = defaultdict(list)

        for talk in self.talk_history:
            day = self._safe_int(getattr(talk, "day", None))
            if day is None:
                continue
            per_day[day].append(f"TALK {getattr(talk, 'agent', '')}: {self._short_text(getattr(talk, 'text', ''))}")
        for whisper in self.whisper_history:
            day = self._safe_int(getattr(whisper, "day", None))
            if day is None:
                continue
            per_day[day].append(
                f"WHISPER {getattr(whisper, 'agent', '')}: {self._short_text(getattr(whisper, 'text', ''))}",
            )

        if not per_day:
            return "Round history: (no talks yet)"

        lines = ["Round history:"]
        for day in sorted(per_day):
            lines.append(f"- Day {day}:")
            for event in per_day[day][-buffer_size:]:
                lines.append(f"  - {event}")
        return "\n".join(lines)

    @staticmethod
    def _safe_int(value: object) -> int | None:
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _short_text(value: object, max_chars: int = 120) -> str:
        text = " ".join(str(value).split())
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3] + "..."

    @staticmethod
    def _word_count(value: object) -> int:
        return len(str(value).split())

    def _strategy_reminder(self) -> str:
        match self.role:
            case Role.WEREWOLF:
                return "- Hide as a villager, coordinate with wolves in whisper, push executions toward village-side threats."
            case Role.POSSESSED:
                return "- Confuse village reasoning and protect werewolves without revealing them."
            case Role.SEER:
                return "- Use divination results to find werewolves and explain them clearly when useful."
            case Role.MEDIUM:
                return "- Use execution results to connect vote history with likely werewolf teams."
            case Role.BODYGUARD:
                return "- Stay hidden unless needed and protect high-value village roles."
            case _:
                return "- Find contradictions, compare claims, and vote for the most likely werewolf."

    def _prepend_memory_context(self, request: Request, prompt: str) -> str:
        if not self.memory_summary or request == Request.INITIALIZE:
            return prompt
        return f"{self.memory_summary}\n\n### Current Request\n{prompt}"

    def _compact_llm_message_history(self) -> None:
        if not self._is_memory_enabled():
            return
        memory_config = self._memory_config()
        keep_turns = int(memory_config.get("keep_llm_turns", 2))
        if keep_turns <= 0:
            keep_turns = 1
        if len(self.llm_message_history) <= (keep_turns * 2) + 1:
            return

        system_messages = [
            message for message in self.llm_message_history[:1]
            if isinstance(message, SystemMessage)
        ]
        recent_messages = self.llm_message_history[-keep_turns * 2 :]
        self.llm_message_history = [*system_messages, *recent_messages]

    def _inject_turn_skill_if_needed(self, request: Request, prompt: str) -> str:
        """Inject turn skill text into current prompt when selected by LLM."""
        if self.llm_model is None:
            return prompt
        if not self.skill_loader.should_apply_turn_skill(request.name):
            return prompt

        skill_summaries = self.skill_loader.get_turn_skill_summaries()
        if not skill_summaries:
            return prompt

        selected_skill_id, decision_reason = self._select_turn_skill_id(
            request_name=request.name,
            prompt=prompt,
            skill_summaries=skill_summaries,
        )
        if not selected_skill_id:
            return prompt

        selected_skill_text = self.skill_loader.load_turn_skill(selected_skill_id)
        if not selected_skill_text:
            return prompt

        self.agent_logger.logger.info(
            "Turn skill injected for %s: %s (%s)",
            request.name,
            selected_skill_id,
            decision_reason,
        )
        return (
            "### 追加スキル (心理戦術)\n"
            f"選択スキル: {selected_skill_id}\n"
            f"選択理由: {decision_reason}\n"
            f"{selected_skill_text}\n\n"
            "### 現在のリクエスト\n"
            f"{prompt}"
        )

    def _select_turn_skill_id(
        self,
        request_name: str,
        prompt: str,
        skill_summaries: dict[str, str],
    ) -> tuple[str, str]:
        """Ask LLM whether to inject a turn skill and which skill to use."""
        if self.llm_model is None:
            return "", ""

        candidate_text = "\n".join(
            [f"- {skill_id}: {summary}" for skill_id, summary in skill_summaries.items()],
        )
        prompt_excerpt = prompt[:1400]
        routing_system_prompt = (
            "あなたはAIWolf向けの心理スキルルーターです。"
            "現在のリクエスト文を読み、必要なら心理スキルを1つだけ選んでください。"
            "不要なら使わない判断をしてください。"
            "必ず以下のタグ形式のみで出力してください。"
            "<use_skill>true|false</use_skill>"
            "<skill_id>skill_id_or_empty</skill_id>"
            "<reason>short reason</reason>"
        )
        routing_user_prompt = (
            f"Request: {request_name}\n\n"
            f"Current prompt excerpt:\n{prompt_excerpt}\n\n"
            f"Available turn skills:\n{candidate_text}\n\n"
            "選択基準:\n"
            "- 強く疑われている、信用回復が必要、議論が荒れている、投票圧が強い場合はtrueを検討\n"
            "- 該当しない場合はfalse\n"
        )

        try:
            routing_response = (self.llm_model | StrOutputParser()).invoke(
                [
                    SystemMessage(content=routing_system_prompt),
                    HumanMessage(content=routing_user_prompt),
                ],
            )
        except Exception:
            self.agent_logger.logger.exception("Turn skill routing call failed")
            return "", ""

        use_skill_match = re.search(r"<use_skill>\s*(true|false)\s*</use_skill>", routing_response, re.IGNORECASE)
        if not use_skill_match or use_skill_match.group(1).lower() != "true":
            return "", ""

        skill_id_match = re.search(r"<skill_id>\s*([a-zA-Z0-9_\\-]*)\s*</skill_id>", routing_response)
        if not skill_id_match:
            return "", ""
        selected_skill_id = skill_id_match.group(1).strip()
        if selected_skill_id not in skill_summaries:
            self.agent_logger.logger.warning("Invalid turn skill selected by router: %s", selected_skill_id)
            return "", ""

        reason_match = re.search(r"<reason>\s*(.*?)\s*</reason>", routing_response, re.DOTALL)
        decision_reason = reason_match.group(1).strip() if reason_match else "router selected"
        if not decision_reason:
            decision_reason = "router selected"
        return selected_skill_id, decision_reason

    @staticmethod
    def _extract_action(response: str | None) -> str | None:
        """Extract content from <action>...</action> tag.

        Args:
            response (str | None): LLM response / LLMの応答

        Returns:
            str | None: Extracted action content / 抽出されたアクション内容
        """
        if response is None:
            return None
        match = re.search(r"<action>(.*?)</action>", response, re.DOTALL)
        if match:
            return match.group(1).strip()
        # 閉じタグなしのケース: <action>content (LLMが</action>を省略した場合)
        match = re.search(r"<action>(.+)", response, re.DOTALL)
        if match:
            return match.group(1).strip()
        return response

    @timeout
    def name(self) -> str:
        """Return response to name request.

        名前リクエストに対する応答を返す.

        Returns:
            str: Agent name / エージェント名
        """
        return self.agent_name

    def initialize(self) -> None:
        """Perform initialization for game start request.

        ゲーム開始リクエストに対する初期化処理を行う.
        """
        if self.info is None:
            return

        model_type = str(self.config["llm"]["type"])
        match model_type:
            case "openai":
                self.llm_model = ChatOpenAI(
                    model=str(self.config["openai"]["model"]),
                    temperature=float(self.config["openai"]["temperature"]),
                    api_key=SecretStr(os.environ["OPENAI_API_KEY"]),
                )
            case "google":
                self.llm_model = ChatGoogleGenerativeAI(
                    model=str(self.config["google"]["model"]),
                    temperature=float(self.config["google"]["temperature"]),
                    api_key=SecretStr(os.environ["GOOGLE_API_KEY"]),
                )
            case "ollama":
                self.llm_model = ChatOllama(
                    model=str(self.config["ollama"]["model"]),
                    temperature=float(self.config["ollama"]["temperature"]),
                    base_url=str(self.config["ollama"]["base_url"]),
                )
            case _:
                raise ValueError(model_type, "Unknown LLM type")
        self.llm_model = self.llm_model
        self.role_skill_text = self.skill_loader.load(self.role.value)
        self.use_builtin_role_strategy = self.skill_loader.should_use_builtin_role_strategy()
        if "system" in self.config["prompt"]:
            key = {
                "info": self.info,
                "setting": self.setting,
                "role": self.role,
                "role_skill_text": self.role_skill_text,
                "use_builtin_role_strategy": self.use_builtin_role_strategy,
            }
            system_prompt = Template(self.config["prompt"]["system"]).render(**key).strip()
            self.llm_message_history = [SystemMessage(content=system_prompt)]
        self._send_message_to_llm(self.request)

    def daily_initialize(self) -> None:
        """Perform processing for daily initialization request.

        昼開始リクエストに対する処理を行う.
        """
        self._send_message_to_llm(self.request)

    def whisper(self) -> str:
        """Return response to whisper request.

        囁きリクエストに対する応答を返す.

        Returns:
            str: Whisper message / 囁きメッセージ
        """
        response = self._send_message_to_llm(self.request)
        self.sent_whisper_count = len(self.whisper_history)
        return response or ""

    def talk(self) -> str:
        """Return response to talk request.

        トークリクエストに対する応答を返す.

        Returns:
            str: Talk message / 発言メッセージ
        """
        response = self._send_message_to_llm(self.request)
        self.sent_talk_count = len(self.talk_history)
        return response or ""

    def daily_finish(self) -> None:
        """Perform processing for daily finish request.

        昼終了リクエストに対する処理を行う.
        """
        if self.request is not None:
            self._refresh_memory_for_request(self.request)

    def divine(self) -> str:
        """Return response to divine request.

        占いリクエストに対する応答を返す.

        Returns:
            str: Agent name to divine / 占い対象のエージェント名
        """
        return self._send_message_to_llm(self.request) or random.choice(  # noqa: S311
            self.get_alive_agents(),
        )

    def guard(self) -> str:
        """Return response to guard request.

        護衛リクエストに対する応答を返す.

        Returns:
            str: Agent name to guard / 護衛対象のエージェント名
        """
        return self._send_message_to_llm(self.request) or random.choice(  # noqa: S311
            self.get_alive_agents(),
        )

    def vote(self) -> str:
        """Return response to vote request.

        投票リクエストに対する応答を返す.

        Returns:
            str: Agent name to vote / 投票対象のエージェント名
        """
        return self._send_message_to_llm(self.request) or random.choice(  # noqa: S311
            self.get_alive_agents(),
        )

    def attack(self) -> str:
        """Return response to attack request.

        襲撃リクエストに対する応答を返す.

        Returns:
            str: Agent name to attack / 襲撃対象のエージェント名
        """
        return self._send_message_to_llm(self.request) or random.choice(  # noqa: S311
            self.get_alive_agents(),
        )

    def finish(self) -> None:
        """Perform processing for game finish request.

        ゲーム終了リクエストに対する処理を行う.
        """

    @timeout
    def action(self) -> str | None:  # noqa: C901, PLR0911
        """Execute action according to request type.

        リクエストの種類に応じたアクションを実行する.

        Returns:
            str | None: Action result string or None / アクションの結果文字列またはNone
        """
        match self.request:
            case Request.NAME:
                return self.name()
            case Request.TALK:
                return self.talk()
            case Request.WHISPER:
                return self.whisper()
            case Request.VOTE:
                return self.vote()
            case Request.DIVINE:
                return self.divine()
            case Request.GUARD:
                return self.guard()
            case Request.ATTACK:
                return self.attack()
            case Request.INITIALIZE:
                self.initialize()
            case Request.DAILY_INITIALIZE:
                self.daily_initialize()
            case Request.DAILY_FINISH:
                self.daily_finish()
            case Request.FINISH:
                self.finish()
            case _:
                pass
        return None

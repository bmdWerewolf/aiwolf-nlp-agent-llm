"""Module that defines the base class for agents.

エージェントの基底クラスを定義するモジュール.
"""

from __future__ import annotations

import os
import random
import re
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
        }
        template: Template = Template(prompt)
        prompt = template.render(**key).strip()
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
                return self._extract_action(response)
            except Exception:
                self.llm_message_history.pop()
                self.agent_logger.logger.exception(
                    "LLM呼び出しに失敗しました (試行 %d/%d)", attempt + 1, max_retries,
                )
                if attempt < max_retries - 1:
                    sleep(5)
        return None

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
        self._send_message_to_llm(self.request)

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

"""Module that defines the base class for agents.

エージェントの基底クラスを定義するモジュール.
"""

from __future__ import annotations

import logging
import os
import random
import re
from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from dotenv import load_dotenv
from jinja2 import Template
from langchain_core.messages import AIMessage, HumanMessage
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
from utils.memory import create_memory
from utils.memory.base import BaseMemory
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

        # Memory management system
        self.memory: BaseMemory | None = None
        self.memory_logger: logging.Logger | None = None
        
        # Track first successful LLM API call
        self._first_llm_call_success: bool = False

        load_dotenv(Path(__file__).parent.joinpath("./../../config/.env"))

        # Initialize COT (Chain of Thought) logger - separate from main agent logger
        self.cot_logger: logging.Logger | None = None
        if self._is_cot_enabled():
            self._init_cot_logger(game_id)

        # Initialize Memory logger if memory is enabled
        if self._get_memory_type() != 0:
            self._init_memory_logger(game_id)

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
            # Add new talks to memory
            if self.memory:
                for talk in packet.talk_history:
                    self.memory.add_talk(talk)
            self.talk_history.extend(packet.talk_history)
        if packet.whisper_history:
            # Add new whispers to memory
            if self.memory:
                for whisper in packet.whisper_history:
                    self.memory.add_talk(whisper)  # Whispers are also Talk objects
            self.whisper_history.extend(packet.whisper_history)
        if self.request == Request.INITIALIZE:
            self.talk_history = []
            self.whisper_history = []
            self.llm_message_history = []
            # Clear memory for new game
            if self.memory:
                self.memory.clear()
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

    def _is_cot_enabled(self) -> bool:
        """Check if COT (Chain of Thought) is enabled in config.

        COT（思維鏈）が設定で有効になっているかを確認する.

        Returns:
            bool: True if COT is enabled / COTが有効な場合True
        """
        return bool(self.config.get("cot", {}).get("enabled", False))

    def _init_cot_logger(self, game_id: str) -> None:
        """Initialize separate COT logger for Chain of Thought logging.

        COT専用のロガーを初期化する（メインログとは別ファイルに出力）.

        Args:
            game_id (str): Game ID for log file organization / ログファイル整理用のゲームID
        """
        from datetime import UTC, datetime

        from ulid import ULID

        self.cot_logger = logging.getLogger(f"{self.agent_name}_cot")
        self.cot_logger.setLevel(logging.INFO)
        # Prevent propagation to root logger to avoid duplicate logs
        self.cot_logger.propagate = False

        if bool(self.config["log"]["file_output"]):
            ulid: ULID = ULID.from_str(game_id)
            tz = datetime.now(UTC).astimezone().tzinfo
            # Create cot_log directory inside the main log directory
            cot_output_dir = (
                Path(str(self.config["log"]["output_dir"]))
                / "cot_log"
                / datetime.fromtimestamp(ulid.timestamp, tz=tz).strftime("%Y%m%d%H%M%S%f")[:-3]
            )
            cot_output_dir.mkdir(parents=True, exist_ok=True)

            handler = logging.FileHandler(
                cot_output_dir / f"{self.agent_name}_cot.log",
                mode="w",
                encoding="utf-8",
            )
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
            handler.setFormatter(formatter)
            self.cot_logger.addHandler(handler)

    def _get_memory_type(self) -> int:
        """Get the memory type from config.

        Returns:
            int: Memory type (0-3)
        """
        return int(self.config.get("memory", {}).get("type", 0))

    def _init_memory_logger(self, game_id: str) -> None:
        """Initialize separate Memory logger for memory state tracking.

        Memory専用のロガーを初期化する（メインログとは別ファイルに出力）.

        Args:
            game_id (str): Game ID for log file organization
        """
        from datetime import UTC, datetime
        from ulid import ULID

        memory_type = self._get_memory_type()
        memory_type_names = {1: "rolling_summary", 2: "game_state", 3: "belief_reflexion"}
        type_name = memory_type_names.get(memory_type, f"type_{memory_type}")

        self.memory_logger = logging.getLogger(f"{self.agent_name}_memory")
        self.memory_logger.setLevel(logging.INFO)
        self.memory_logger.propagate = False

        if bool(self.config["log"]["file_output"]):
            ulid: ULID = ULID.from_str(game_id)
            tz = datetime.now(UTC).astimezone().tzinfo
            memory_output_dir = (
                Path(str(self.config["log"]["output_dir"]))
                / "memory_log"
                / datetime.fromtimestamp(ulid.timestamp, tz=tz).strftime("%Y%m%d%H%M%S%f")[:-3]
            )
            memory_output_dir.mkdir(parents=True, exist_ok=True)

            handler = logging.FileHandler(
                memory_output_dir / f"{self.agent_name}_{type_name}.log",
                mode="w",
                encoding="utf-8",
            )
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
            handler.setFormatter(formatter)
            self.memory_logger.addHandler(handler)

            # Log initial info
            self.memory_logger.info(f"[INIT] Memory Type: {memory_type} ({type_name})")
            self.memory_logger.info("=" * 60)

    def _parse_cot_response(self, response: str) -> tuple[str, str]:
        """Parse COT formatted response into thinking and action parts.

        COT形式のレスポンスを思考部分とアクション部分に分割する.

        Args:
            response (str): Raw LLM response / LLMの生の応答

        Returns:
            tuple[str, str]: (thinking, action) tuple / (思考, アクション)のタプル
        """
        # Try to extract <thinking> tag (with or without closing tag)
        thinking_match = re.search(r"<thinking>(.*?)</thinking>", response, re.DOTALL | re.IGNORECASE)
        # Try to extract <action> tag (closing tag is optional since LLM may omit it)
        action_match = re.search(r"<action>(.*?)(?:</action>|$)", response, re.DOTALL | re.IGNORECASE)

        if thinking_match and action_match:
            thinking = thinking_match.group(1).strip()
            action = action_match.group(1).strip()
        elif action_match:
            # Only action tag found
            thinking = ""
            action = action_match.group(1).strip()
        else:
            # Fallback: if no tags found, treat entire response as action
            thinking = ""
            action = response.strip()

        return thinking, action

    def _send_message_to_llm(self, request: Request | None) -> str | None:
        """Send message to LLM and get response.

        LLMにメッセージを送信して応答を取得する.
        COTが有効な場合、思考過程をログに記録し、アクション部分のみを返す.

        Args:
            request (Request | None): The request type to process / 処理するリクエストタイプ

        Returns:
            str | None: LLM response (action only if COT enabled) or None if error occurred
                        LLMの応答（COT有効時はアクション部分のみ）またはエラー時はNone
        """
        if request is None:
            return None
        if request.lower() not in self.config["prompt"]:
            return None
        prompt = self.config["prompt"][request.lower()]
        if float(self.config["llm"]["sleep_time"]) > 0:
            sleep(float(self.config["llm"]["sleep_time"]))

        # Get memory context if memory is enabled
        memory_context = ""
        if self.memory:
            memory_context = self.memory.get_memory_context()

        key = {
            "info": self.info,
            "setting": self.setting,
            "talk_history": self.talk_history,
            "whisper_history": self.whisper_history,
            "role": self.role,
            "sent_talk_count": self.sent_talk_count,
            "sent_whisper_count": self.sent_whisper_count,
            "memory_context": memory_context,  # Add memory context to template vars
        }
        template: Template = Template(prompt)
        prompt = template.render(**key).strip()

        # Prepend memory context to prompt if available and not empty
        if memory_context:
            prompt = f"{memory_context}\n\n{prompt}"
        if self.llm_model is None:
            self.agent_logger.logger.error("LLM is not initialized")
            return None
        try:
            self.llm_message_history.append(HumanMessage(content=prompt))
            response = (self.llm_model | StrOutputParser()).invoke(self.llm_message_history)
            self.llm_message_history.append(AIMessage(content=response))

            # Log first successful API call
            if not self._first_llm_call_success:
                self._first_llm_call_success = True
                model_type = str(self.config["llm"]["type"])
                model_name = str(self.config[model_type]["model"])
                base_url = self.config[model_type].get("base_url", "default")
                self.agent_logger.logger.info("=" * 80)
                self.agent_logger.logger.info("🎉 首次 LLM API 调用成功!")
                self.agent_logger.logger.info(f"   模型类型: {model_type}")
                self.agent_logger.logger.info(f"   模型名称: {model_name}")
                self.agent_logger.logger.info(f"   API 地址: {base_url}")
                self.agent_logger.logger.info(f"   请求类型: {request}")
                self.agent_logger.logger.info(f"   响应长度: {len(response)} 字符")
                self.agent_logger.logger.info("=" * 80)

            # COT parsing: separate thinking from action
            if self._is_cot_enabled():
                thinking, action = self._parse_cot_response(response)
                # Log COT to separate cot_logger (not in main agent log)
                if self.cot_logger:
                    if thinking:
                        self.cot_logger.info(f"[THINKING] {request}\n{thinking}")
                    self.cot_logger.info(f"[ACTION] {request}\n{action}")
                    self.cot_logger.info(f"[FULL_RESPONSE]\n{response}\n{'='*50}")
                return action
            else:
                self.agent_logger.logger.info(["LLM", prompt, response])
                return response
        except Exception:
            self.agent_logger.logger.exception("Failed to send message to LLM")
            return None

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
                openai_kwargs: dict[str, Any] = {
                    "model": str(self.config["openai"]["model"]),
                    "temperature": float(self.config["openai"]["temperature"]),
                    "api_key": SecretStr(os.environ["OPENAI_API_KEY"]),
                }
                if self.config["openai"].get("base_url"):
                    openai_kwargs["base_url"] = str(self.config["openai"]["base_url"])
                self.llm_model = ChatOpenAI(**openai_kwargs)
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

        # Log the model being used
        model_name = str(self.config[model_type]["model"])
        self.agent_logger.logger.info(["MODEL_INIT", f"type={model_type}", f"model={model_name}"])

        # Initialize memory management system
        self._init_memory()

        self._send_message_to_llm(self.request)

    def _init_memory(self) -> None:
        """Initialize the memory management system.

        メモリ管理システムを初期化する.
        """
        memory_type = int(self.config.get("memory", {}).get("type", 0))
        # Create memory instance (factory handles all types)
        self.memory = create_memory(self.config, self.llm_model, self.agent_name)

        self.agent_logger.logger.info(["MEMORY_INIT", f"type={memory_type}"])

        # Pass memory_logger to memory instance if available
        if self.memory and self.memory_logger:
            self.memory.set_logger(self.memory_logger)

        # Initialize memory with game info if available
        self._update_memory_with_game_info()

    def _update_memory_with_game_info(self) -> None:
        """Update memory with current game state information.

        現在のゲーム状態情報でメモリを更新する.
        """
        if not self.memory or not self.info:
            return

        # For GameStateMemory, update with game info
        from utils.memory.game_state import GameStateMemory
        if isinstance(self.memory, GameStateMemory):
            alive = [k for k, v in self.info.status_map.items() if v == Status.ALIVE]
            dead = [k for k, v in self.info.status_map.items() if v != Status.ALIVE]
            divine_result = str(self.info.divine_result) if self.info.divine_result else None
            executed = str(self.info.executed_agent) if self.info.executed_agent else None
            attacked = str(self.info.attacked_agent) if self.info.attacked_agent else None
            self.memory.update_from_game_info(
                alive_players=alive,
                dead_players=dead,
                current_day=self.info.day,
                divine_result=divine_result,
                executed_agent=executed,
                attacked_agent=attacked,
            )

        # For BeliefReflexionMemory, initialize players and role
        from utils.memory.belief_reflexion import BeliefReflexionMemory
        if isinstance(self.memory, BeliefReflexionMemory):
            all_players = list(self.info.status_map.keys())
            self.memory.initialize_players(all_players)
            self.memory.set_my_role(self.role.value if self.role else "UNKNOWN")

    def daily_initialize(self) -> None:
        """Perform processing for daily initialization request.

        昼開始リクエストに対する処理を行う.
        """
        # Update memory with new day's game state
        self._update_memory_with_game_info()

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

        # Process turn-end memory updates
        if self.memory and self.info:
            events = {
                "day": self.info.day,
                "executed": str(self.info.executed_agent) if self.info.executed_agent else None,
                "attacked": str(self.info.attacked_agent) if self.info.attacked_agent else None,
                "divine_result": str(self.info.divine_result) if self.info.divine_result else None,
                "medium_result": str(self.info.medium_result) if self.info.medium_result else None,
            }
            self.memory.on_turn_end(events)

            # Log memory state after turn-end processing
            if self.memory_logger:
                self.memory_logger.info(f"[DAY_END] Day {self.info.day}")
                self.memory_logger.info(f"[EVENTS] {events}")
                memory_context = self.memory.get_memory_context()
                self.memory_logger.info(f"[MEMORY_STATE]\n{memory_context}")
                self.memory_logger.info("=" * 60)

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

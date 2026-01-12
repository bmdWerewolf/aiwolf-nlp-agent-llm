"""Memory management package for AIWolf agent.

AIWolf エージェントのメモリ管理パッケージ.

This package provides pluggable memory strategies:
- 0: NoMemory (baseline, full history)
- 1: RollingSummary (semantic compression)
- 2: GameStateMemory (structured JSON state)
- 3: BeliefReflexionMemory (probabilistic beliefs + strategy)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from utils.memory.base import BaseMemory
from utils.memory.no_memory import NoMemory
from utils.memory.rolling_summary import RollingSummaryMemory
from utils.memory.game_state import GameStateMemory
from utils.memory.belief_reflexion import BeliefReflexionMemory

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

__all__ = [
    "BaseMemory",
    "NoMemory",
    "RollingSummaryMemory",
    "GameStateMemory",
    "BeliefReflexionMemory",
    "create_memory",
]


def create_memory(
    config: dict[str, Any],
    llm_model: BaseChatModel | None,
    agent_name: str,
) -> BaseMemory:
    """Factory function to create a memory instance based on config.

    設定に基づいてメモリインスタンスを生成するファクトリ関数.

    Args:
        config: Configuration dictionary containing memory settings
        llm_model: LangChain chat model for memory strategies that need LLM
        agent_name: Name of the agent (for context)

    Returns:
        BaseMemory: Appropriate memory instance based on config["memory"]["type"]
    """
    memory_config = config.get("memory", {})
    memory_type = int(memory_config.get("type", 0))

    match memory_type:
        case 0:
            return NoMemory(config=config, agent_name=agent_name)
        case 1:
            if llm_model is None:
                raise ValueError("RollingSummaryMemory requires an LLM model")
            buffer_size = int(memory_config.get("rolling_summary", {}).get("buffer_size", 5))
            return RollingSummaryMemory(
                config=config,
                llm_model=llm_model,
                agent_name=agent_name,
                buffer_size=buffer_size,
            )
        case 2:
            if llm_model is None:
                raise ValueError("GameStateMemory requires an LLM model")
            suspicion_decay = float(memory_config.get("game_state", {}).get("suspicion_decay", 0.1))
            return GameStateMemory(
                config=config,
                llm_model=llm_model,
                agent_name=agent_name,
                suspicion_decay=suspicion_decay,
            )
        case 3:
            if llm_model is None:
                raise ValueError("BeliefReflexionMemory requires an LLM model")
            reflexion_interval = int(memory_config.get("belief_reflexion", {}).get("reflexion_interval", 1))
            return BeliefReflexionMemory(
                config=config,
                llm_model=llm_model,
                agent_name=agent_name,
                reflexion_interval=reflexion_interval,
            )
        case _:
            raise ValueError(f"Unknown memory type: {memory_type}. Must be 0-3.")

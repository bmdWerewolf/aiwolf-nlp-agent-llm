"""Structured Game State memory strategy.

構造化ゲーム状態メモリ戦略.

This strategy (type=2) maintains a machine-readable JSON state object
that models the current game state, replacing raw conversation history.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from utils.memory.base import BaseMemory

if TYPE_CHECKING:
    from aiwolf_nlp_common.packet import Talk
    from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)


EXTRACT_STATE_SYSTEM_PROMPT = """You are a game state extraction assistant for a Werewolf game AI.

Your task is to extract structured information from game events and conversations.

Extract ONLY the following fields (output valid JSON):
{
  "role_claims": {"AgentName": "ROLE", ...},  // New role claims made
  "votes_mentioned": [{"voter": "...", "target": "..."}],  // Votes discussed
  "accusations": [{"accuser": "...", "target": "...", "reason": "..."}],
  "suspicion_updates": {"AgentName": delta, ...},  // Suspicion changes (-0.3 to +0.3)
  "deaths": ["AgentName", ...],  // Players who died
  "divine_results": [{"seer": "...", "target": "...", "result": "HUMAN/WEREWOLF"}]
}

RULES:
- Only include fields with actual new information
- suspicion_updates: positive = more suspicious, negative = less suspicious
- Keep values between -0.3 and +0.3 for suspicion changes
- Output ONLY valid JSON, no explanation"""

EXTRACT_STATE_USER_TEMPLATE = """Current game state:
{current_state}

New events to process:
{events}

Extract state updates (JSON only):"""


class GameStateMemory(BaseMemory):
    """Structured game state memory.

    構造化ゲーム状態メモリ.

    Maintains a JSON state object with:
    - alive/dead players
    - role claims
    - votes
    - investigations (divine results)
    - suspicion levels (0-1 per player)
    - current day
    """

    def __init__(
        self,
        config: dict[str, Any],
        llm_model: BaseChatModel,
        agent_name: str,
        suspicion_decay: float = 0.1,
    ) -> None:
        """Initialize GameStateMemory.

        Args:
            config: Configuration dictionary
            llm_model: LangChain chat model for state extraction
            agent_name: Name of the agent
            suspicion_decay: Rate at which old suspicions decay each turn
        """
        super().__init__(config, agent_name)
        self._llm = llm_model
        self._suspicion_decay = suspicion_decay

        # Initialize state
        self._state: dict[str, Any] = self._create_initial_state()
        self._pending_events: list[str] = []

    def _create_initial_state(self) -> dict[str, Any]:
        """Create the initial empty game state."""
        return {
            "my_name": self.agent_name,
            "current_day": 0,
            "alive": [],
            "dead": [],
            "role_claims": {},
            "votes": [],
            "investigations": [],
            "suspicion": {},  # player_name -> float (0.0 to 1.0)
            "trust_notes": [],
        }

    def add_message(self, role: str, content: str) -> None:
        """Add a message to pending events.

        Args:
            role: Message role
            content: Message content
        """
        self._pending_events.append(f"[{role.upper()}]: {content}")

    def add_talk(self, talk: Talk) -> None:
        """Add a game talk to pending events.

        Args:
            talk: Talk object from the game
        """
        self._pending_events.append(f"{talk.agent}: {talk.text}")

    def get_memory_context(self) -> str:
        """Get the game state as formatted context.

        Returns:
            str: JSON-formatted game state
        """
        parts = ["[GAME_STATE]"]
        parts.append(json.dumps(self._state, indent=2, ensure_ascii=False))
        return "\n".join(parts)

    def update_from_game_info(
        self,
        alive_players: list[str],
        dead_players: list[str],
        current_day: int,
        divine_result: str | None = None,
        executed_agent: str | None = None,
        attacked_agent: str | None = None,
    ) -> None:
        """Update state directly from game info.

        ゲーム情報から直接状態を更新する.

        Args:
            alive_players: List of alive player names
            dead_players: List of dead player names
            current_day: Current game day
            divine_result: Divine result if available
            executed_agent: Agent executed this round
            attacked_agent: Agent attacked this round
        """
        self._state["alive"] = alive_players
        self._state["dead"] = dead_players
        self._state["current_day"] = current_day

        # Initialize suspicion for new players
        for player in alive_players:
            if player not in self._state["suspicion"]:
                self._state["suspicion"][player] = 0.5  # Neutral starting point

        # Remove dead players from suspicion (optional: keep for reference)
        # for player in dead_players:
        #     self._state["suspicion"].pop(player, None)

        if executed_agent:
            self._pending_events.append(f"[EXECUTED]: {executed_agent}")
        if attacked_agent:
            self._pending_events.append(f"[ATTACKED]: {attacked_agent}")
        if divine_result:
            self._pending_events.append(f"[DIVINE_RESULT]: {divine_result}")

    def on_turn_end(self, events: dict[str, Any]) -> None:
        """Process pending events and update state.

        Args:
            events: Game events from the turn
        """
        # Add any additional events
        for key, value in events.items():
            if value:
                self._pending_events.append(f"[{key.upper()}]: {value}")

        if not self._pending_events:
            return

        # Apply suspicion decay
        for player in self._state["suspicion"]:
            current = self._state["suspicion"][player]
            # Decay towards 0.5 (neutral)
            self._state["suspicion"][player] = current + (0.5 - current) * self._suspicion_decay

        # Prepare events string
        events_str = "\n".join(self._pending_events[-30:])  # Limit to last 30

        try:
            messages = [
                SystemMessage(content=EXTRACT_STATE_SYSTEM_PROMPT),
                HumanMessage(content=EXTRACT_STATE_USER_TEMPLATE.format(
                    current_state=json.dumps(self._state, indent=2, ensure_ascii=False),
                    events=events_str,
                )),
            ]

            chain = self._llm | StrOutputParser()
            response = chain.invoke(messages)

            # Parse JSON response
            # Handle potential markdown code blocks
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1]
            if response.endswith("```"):
                response = response.rsplit("```", 1)[0]

            updates = json.loads(response)
            self._merge_state_updates(updates)

            logger.debug("Updated game state: %s", json.dumps(self._state, indent=2))

            # Log the state update
            self._log("[STATE_UPDATE]")
            self._log(f"LLM extracted: {json.dumps(updates, ensure_ascii=False)}")
            self._log(f"Suspicion levels: {self._state['suspicion']}")
            if self._state['role_claims']:
                self._log(f"Role claims: {self._state['role_claims']}")

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse state update JSON: %s", e)
            self._log(f"[ERROR] JSON parse failed: {e}")
        except Exception:
            logger.exception("Failed to update game state")

        self._pending_events.clear()

    def _merge_state_updates(self, updates: dict[str, Any]) -> None:
        """Merge extracted updates into the current state.

        Args:
            updates: Dictionary of state updates from LLM
        """
        # Role claims
        if "role_claims" in updates and isinstance(updates["role_claims"], dict):
            self._state["role_claims"].update(updates["role_claims"])

        # Votes
        if "votes_mentioned" in updates and isinstance(updates["votes_mentioned"], list):
            for vote in updates["votes_mentioned"]:
                if isinstance(vote, dict) and "voter" in vote and "target" in vote:
                    vote["day"] = self._state["current_day"]
                    self._state["votes"].append(vote)

        # Divine results
        if "divine_results" in updates and isinstance(updates["divine_results"], list):
            for result in updates["divine_results"]:
                if isinstance(result, dict):
                    self._state["investigations"].append(result)

        # Suspicion updates
        if "suspicion_updates" in updates and isinstance(updates["suspicion_updates"], dict):
            for player, delta in updates["suspicion_updates"].items():
                if player in self._state["suspicion"]:
                    new_value = self._state["suspicion"][player] + float(delta)
                    self._state["suspicion"][player] = max(0.0, min(1.0, new_value))

        # Deaths
        if "deaths" in updates and isinstance(updates["deaths"], list):
            for player in updates["deaths"]:
                if player in self._state["alive"]:
                    self._state["alive"].remove(player)
                if player not in self._state["dead"]:
                    self._state["dead"].append(player)

        # Accusations (store as trust notes)
        if "accusations" in updates and isinstance(updates["accusations"], list):
            for acc in updates["accusations"]:
                if isinstance(acc, dict):
                    note = f"Day {self._state['current_day']}: {acc.get('accuser', '?')} accused {acc.get('target', '?')}"
                    if acc.get("reason"):
                        note += f" ({acc['reason']})"
                    self._state["trust_notes"].append(note)
                    # Keep only last 10 trust notes
                    self._state["trust_notes"] = self._state["trust_notes"][-10:]

    def clear(self) -> None:
        """Clear all memory for a new game."""
        self._state = self._create_initial_state()
        self._pending_events.clear()
        self._log("[MEMORY_CLEARED]")

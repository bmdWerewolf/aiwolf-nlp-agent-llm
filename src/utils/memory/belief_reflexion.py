"""Belief + Reflexion memory strategy.

信念+反思メモリ戦略.

This strategy (type=3) maintains probabilistic beliefs about player roles
and accumulates strategic lessons through periodic reflexion.
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


BELIEF_UPDATE_SYSTEM_PROMPT = """You are a probability analyst for a Werewolf game AI.

Your task is to update belief probabilities based on new game events.

Current beliefs represent probability of each player being a WEREWOLF (0.0 to 1.0):
- 0.0 = definitely not werewolf (confirmed villager/seer)
- 0.5 = unknown/neutral
- 1.0 = definitely werewolf (confirmed)

RULES for updating beliefs:
- Divine result showing WEREWOLF -> set to 1.0
- Divine result showing HUMAN -> set to 0.0
- Aggressive early accusers -> slightly increase (+0.1)
- Defending obvious suspects -> increase (+0.15)
- Quiet players in late game -> slightly increase (+0.05)
- Consistent logical arguments -> decrease (-0.1)

Output ONLY valid JSON with updated beliefs:
{"AgentName": probability, ...}

Include ALL players, not just changed ones."""

BELIEF_UPDATE_USER_TEMPLATE = """Current beliefs:
{beliefs}

New events:
{events}

Output updated beliefs (JSON only):"""


REFLEXION_SYSTEM_PROMPT = """You are a strategic advisor for a Werewolf game AI.

Your task is to generate strategic lessons from recent game events.
These lessons will help the AI play better in future turns.

RULES:
- Focus on actionable heuristics
- Be concise (max 50 chars per lesson)
- Only add truly useful insights
- Output 1-3 bullet points

Examples of good lessons:
- "Seer should delay reveal until Day 2"
- "Agent[02] tends to vote with Agent[04]"
- "Early accusers are often wolves"
- "Watch for bandwagon voting patterns"

Output ONLY the bullet points, one per line, starting with "-"."""

REFLEXION_USER_TEMPLATE = """Current strategy notes:
{strategy_notes}

Recent events:
{events}

My role: {my_role}

Generate new strategic lessons (1-3 bullet points):"""


class BeliefReflexionMemory(BaseMemory):
    """Belief + Reflexion memory.

    信念+反思メモリ.

    Maintains:
    - beliefs: dict[player -> probability of being werewolf]
    - strategy_notes: list of learned heuristics
    - trust_graph: who supports whom
    """

    def __init__(
        self,
        config: dict[str, Any],
        llm_model: BaseChatModel,
        agent_name: str,
        reflexion_interval: int = 1,
    ) -> None:
        """Initialize BeliefReflexionMemory.

        Args:
            config: Configuration dictionary
            llm_model: LangChain chat model for belief updates and reflexion
            agent_name: Name of the agent
            reflexion_interval: Run reflexion every N turns
        """
        super().__init__(config, agent_name)
        self._llm = llm_model
        self._reflexion_interval = reflexion_interval

        # State
        self._beliefs: dict[str, float] = {}  # player -> P(werewolf)
        self._strategy_notes: list[str] = []
        self._trust_graph: dict[str, list[str]] = {}  # player -> supporters
        self._pending_events: list[str] = []
        self._turn_count: int = 0
        self._my_role: str = "UNKNOWN"

    def set_my_role(self, role: str) -> None:
        """Set the agent's role for context.

        Args:
            role: The agent's role (WEREWOLF, SEER, VILLAGER, etc.)
        """
        self._my_role = role

    def initialize_players(self, players: list[str]) -> None:
        """Initialize beliefs for all players.

        Args:
            players: List of player names in the game
        """
        for player in players:
            if player not in self._beliefs:
                if player == self.agent_name:
                    # We know our own role
                    self._beliefs[player] = 0.0  # We're not a wolf (from our perspective)
                else:
                    self._beliefs[player] = 0.5  # Neutral starting point
            if player not in self._trust_graph:
                self._trust_graph[player] = []

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

        # Simple trust graph update: if A supports B's claim
        text_lower = talk.text.lower() if talk.text else ""
        for player in self._beliefs:
            if player != talk.agent and player.lower() in text_lower:
                if "agree" in text_lower or "trust" in text_lower or "believe" in text_lower:
                    if talk.agent not in self._trust_graph.get(player, []):
                        self._trust_graph.setdefault(player, []).append(talk.agent)

    def get_memory_context(self) -> str:
        """Get the memory context for prompt injection.

        Returns:
            str: Formatted beliefs and strategy notes
        """
        parts = []

        # Beliefs section
        parts.append("[BELIEFS]")
        sorted_beliefs = sorted(self._beliefs.items(), key=lambda x: -x[1])
        for player, prob in sorted_beliefs:
            if player == self.agent_name:
                continue  # Skip self
            label = self._get_belief_label(prob)
            parts.append(f"{player}: {prob:.2f} ({label})")

        parts.append("")

        # Strategy notes section
        if self._strategy_notes:
            parts.append("[STRATEGY_NOTES]")
            for note in self._strategy_notes[-5:]:  # Last 5 notes
                parts.append(note)
            parts.append("")

        # Trust graph summary (condensed)
        if any(self._trust_graph.values()):
            parts.append("[TRUST_GRAPH]")
            for player, supporters in self._trust_graph.items():
                if supporters and player != self.agent_name:
                    parts.append(f"{player} <- supported by: {', '.join(supporters[:3])}")

        return "\n".join(parts)

    def _get_belief_label(self, prob: float) -> str:
        """Get a human-readable label for a belief probability."""
        if prob >= 0.8:
            return "highly suspicious"
        elif prob >= 0.6:
            return "suspicious"
        elif prob >= 0.4:
            return "uncertain"
        elif prob >= 0.2:
            return "likely innocent"
        else:
            return "trusted"

    def on_turn_end(self, events: dict[str, Any]) -> None:
        """Update beliefs and potentially run reflexion.

        Args:
            events: Game events from the turn
        """
        # Add game events
        for key, value in events.items():
            if value:
                self._pending_events.append(f"[{key.upper()}]: {value}")

        if not self._pending_events:
            return

        self._turn_count += 1
        events_str = "\n".join(self._pending_events[-30:])

        # 1. Update beliefs
        self._update_beliefs(events_str)

        # 2. Run reflexion periodically
        if self._turn_count % self._reflexion_interval == 0:
            self._run_reflexion(events_str)

        self._pending_events.clear()

    def _update_beliefs(self, events_str: str) -> None:
        """Call LLM to update belief probabilities.

        Args:
            events_str: Formatted string of recent events
        """
        try:
            messages = [
                SystemMessage(content=BELIEF_UPDATE_SYSTEM_PROMPT),
                HumanMessage(content=BELIEF_UPDATE_USER_TEMPLATE.format(
                    beliefs=json.dumps(self._beliefs, indent=2),
                    events=events_str,
                )),
            ]

            chain = self._llm | StrOutputParser()
            response = chain.invoke(messages)

            # Parse JSON
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1]
            if response.endswith("```"):
                response = response.rsplit("```", 1)[0]

            new_beliefs = json.loads(response)

            # Validate and update
            old_beliefs = self._beliefs.copy()
            for player, prob in new_beliefs.items():
                if isinstance(prob, (int, float)):
                    self._beliefs[player] = max(0.0, min(1.0, float(prob)))

            logger.debug("Updated beliefs: %s", self._beliefs)

            # Log belief changes
            self._log("[BELIEF_UPDATE]")
            for player, new_prob in self._beliefs.items():
                old_prob = old_beliefs.get(player, 0.5)
                if abs(new_prob - old_prob) > 0.05:  # Only log significant changes
                    change = "+" if new_prob > old_prob else ""
                    self._log(f"  {player}: {old_prob:.2f} -> {new_prob:.2f} ({change}{new_prob - old_prob:.2f})")

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse belief update JSON: %s", e)
            self._log(f"[ERROR] Belief JSON parse failed: {e}")
        except Exception:
            logger.exception("Failed to update beliefs")

    def _run_reflexion(self, events_str: str) -> None:
        """Call LLM to generate strategic lessons.

        Args:
            events_str: Formatted string of recent events
        """
        try:
            messages = [
                SystemMessage(content=REFLEXION_SYSTEM_PROMPT),
                HumanMessage(content=REFLEXION_USER_TEMPLATE.format(
                    strategy_notes="\n".join(self._strategy_notes[-5:]) or "(None yet)",
                    events=events_str,
                    my_role=self._my_role,
                )),
            ]

            chain = self._llm | StrOutputParser()
            response = chain.invoke(messages)

            # Parse bullet points
            for line in response.strip().split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    note = line[1:].strip()
                    if note and len(note) <= 100:  # Reasonable length
                        self._strategy_notes.append(f"- {note}")

            # Keep only last 10 strategy notes
            self._strategy_notes = self._strategy_notes[-10:]

            logger.debug("Updated strategy notes: %s", self._strategy_notes)

            # Log reflexion results
            self._log("[REFLEXION]")
            self._log(f"Turn {self._turn_count}, Role: {self._my_role}")
            for note in self._strategy_notes[-3:]:
                self._log(f"  {note}")

        except Exception:
            logger.exception("Failed to run reflexion")

    def clear(self) -> None:
        """Clear all memory for a new game."""
        self._beliefs.clear()
        self._strategy_notes.clear()
        self._trust_graph.clear()
        self._pending_events.clear()
        self._turn_count = 0
        self._my_role = "UNKNOWN"
        self._log("[MEMORY_CLEARED]")

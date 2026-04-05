"""Data models for the evaluation pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AgentRecord:
    """A single player in one game."""

    idx: int
    name: str
    role: str
    camp: str
    display_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "idx": self.idx,
            "name": self.name,
            "role": self.role,
            "camp": self.camp,
            "display_name": self.display_name,
        }


@dataclass(slots=True)
class EventRecord:
    """A parsed log event."""

    line_no: int
    day: int
    kind: str
    actor: int | None = None
    target: int | None = None
    text: str | None = None
    public: bool = True
    result: str | None = None
    status: str | None = None
    raw_fields: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def ref(self) -> str:
        """Stable event reference used by judge outputs."""
        return f"L{self.line_no}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "ref": self.ref,
            "line_no": self.line_no,
            "day": self.day,
            "kind": self.kind,
            "actor": self.actor,
            "target": self.target,
            "text": self.text,
            "public": self.public,
            "result": self.result,
            "status": self.status,
            "raw_fields": self.raw_fields,
            "meta": self.meta,
        }


@dataclass(slots=True)
class GameRecord:
    """Structured representation of one game log."""

    log_path: str
    json_path: str | None
    agents: list[AgentRecord]
    events: list[EventRecord]
    parser_notes: list[str] = field(default_factory=list)
    json_hints: dict[str, Any] = field(default_factory=dict)
    final_outcome: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "log_path": self.log_path,
            "json_path": self.json_path,
            "agents": [agent.to_dict() for agent in self.agents],
            "events": [event.to_dict() for event in self.events],
            "parser_notes": self.parser_notes,
            "json_hints": self.json_hints,
            "final_outcome": self.final_outcome,
        }

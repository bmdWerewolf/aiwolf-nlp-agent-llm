"""Parsers for AIWolf server logs and optional JSON sidecars."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from evaluate.models import AgentRecord, EventRecord, GameRecord

_JSON_AGENT_PATTERN = re.compile(
    r'\{"idx":(?P<idx>\d+),"name":"(?P<name>[^"]+)","role":"(?P<role>[^"]+)","team":"(?P<team>[^"]+)"}',
)
_NESTED_REQUEST_PATTERN = re.compile(r'\\"request\\":\\"(?P<request>[A-Z_]+)\\"')


def _camp_from_role(role: str) -> str:
    if role in {"WEREWOLF", "POSSESSED"}:
        return "WEREWOLF"
    return "VILLAGER"


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def read_text_with_fallback(path: Path) -> tuple[str, str]:
    """Read text by trying common encodings used in this repository."""
    encodings = ["utf-8", "utf-8-sig", "cp932", "shift_jis", "utf-16"]
    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding), encoding
        except UnicodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace"), "utf-8-replace"


def parse_json_hints(json_path: Path) -> tuple[dict[str, Any], list[str]]:
    """Recover minimal metadata from the sidecar JSON, even if it is malformed."""
    notes: list[str] = []
    raw_text, encoding = read_text_with_fallback(json_path)
    notes.append(f"Decoded JSON sidecar with {encoding}.")

    agents: list[dict[str, Any]] = []
    for match in _JSON_AGENT_PATTERN.finditer(raw_text):
        role = match.group("role")
        agents.append(
            {
                "idx": int(match.group("idx")),
                "name": match.group("name"),
                "role": role,
                "camp": _camp_from_role(role),
                "team": match.group("team"),
            },
        )

    request_counter = Counter(_NESTED_REQUEST_PATTERN.findall(raw_text))
    notes.append(f"Recovered {len(agents)} agent records from JSON via regex.")
    if request_counter:
        notes.append("Recovered nested request type counts from JSON via regex.")

    parse_status = "regex_recovered"
    try:
        parsed = json.loads(raw_text)
        parse_status = "json_loaded"
        notes.append("The sidecar JSON was parsed successfully as strict JSON.")
        if isinstance(parsed, dict) and isinstance(parsed.get("agents"), list):
            agents = []
            for record in parsed["agents"]:
                if not isinstance(record, dict):
                    continue
                role = str(record.get("role", "UNKNOWN"))
                agents.append(
                    {
                        "idx": int(record.get("idx", 0)),
                        "name": str(record.get("name", "")),
                        "role": role,
                        "camp": _camp_from_role(role),
                        "team": str(record.get("team", "")),
                    },
                )
    except json.JSONDecodeError:
        notes.append(
            "The sidecar JSON is not strict JSON in this environment; packet building falls back to log-first parsing.",
        )

    return {
        "path": str(json_path),
        "parse_status": parse_status,
        "agents": agents,
        "nested_request_counts": dict(request_counter),
    }, notes


def parse_game_log(log_path: Path, json_path: Path | None = None) -> GameRecord:
    """Parse one server game log into structured records."""
    log_text, encoding = read_text_with_fallback(log_path)
    parser_notes = [f"Decoded game log with {encoding}."]
    json_hints: dict[str, Any] = {}

    if json_path is not None and json_path.exists():
        json_hints, json_notes = parse_json_hints(json_path)
        parser_notes.extend(json_notes)

    agents_by_idx: dict[int, AgentRecord] = {}
    events: list[EventRecord] = []
    final_outcome: dict[str, Any] = {}

    for line_no, raw_line in enumerate(log_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        base_parts = line.split(",")
        if len(base_parts) < 2:
            parser_notes.append(f"Skipped malformed line {line_no}: {line}")
            continue

        day = _safe_int(base_parts[0])
        if day is None:
            parser_notes.append(f"Skipped non-numeric day on line {line_no}: {line}")
            continue

        kind = base_parts[1]
        if kind == "status":
            if len(base_parts) < 7:
                parser_notes.append(f"Skipped malformed status line {line_no}: {line}")
                continue
            agent_idx = _safe_int(base_parts[2])
            if agent_idx is None:
                parser_notes.append(f"Skipped malformed status actor on line {line_no}: {line}")
                continue
            role = base_parts[3]
            alive_status = base_parts[4]
            agent_name = base_parts[5]
            display_name = base_parts[6]
            if agent_idx not in agents_by_idx:
                agents_by_idx[agent_idx] = AgentRecord(
                    idx=agent_idx,
                    name=agent_name,
                    role=role,
                    camp=_camp_from_role(role),
                    display_name=display_name,
                )
            events.append(
                EventRecord(
                    line_no=line_no,
                    day=day,
                    kind=kind,
                    actor=agent_idx,
                    public=True,
                    status=alive_status,
                    result=role,
                    raw_fields=base_parts[2:],
                    meta={"name": agent_name, "display_name": display_name},
                ),
            )
            continue

        if kind in {"talk", "whisper"}:
            head = line.split(",", 5)
            if len(head) < 6:
                parser_notes.append(f"Skipped malformed {kind} line {line_no}: {line}")
                continue
            events.append(
                EventRecord(
                    line_no=line_no,
                    day=day,
                    kind=kind,
                    actor=_safe_int(head[4]),
                    text=head[5],
                    public=(kind == "talk"),
                    raw_fields=head[2:5],
                    meta={"sequence_fields": head[2:4]},
                ),
            )
            continue

        if kind in {"vote", "attackVote"}:
            head = line.split(",", 3)
            if len(head) < 4:
                parser_notes.append(f"Skipped malformed {kind} line {line_no}: {line}")
                continue
            events.append(
                EventRecord(
                    line_no=line_no,
                    day=day,
                    kind=kind,
                    actor=_safe_int(head[2]),
                    target=_safe_int(head[3]),
                    public=(kind == "vote"),
                    raw_fields=head[2:],
                ),
            )
            continue

        if kind in {"execute", "attack"}:
            head = line.split(",", 4)
            if len(head) < 4:
                parser_notes.append(f"Skipped malformed {kind} line {line_no}: {line}")
                continue
            target = _safe_int(head[2])
            result = head[3] if len(head) >= 4 else None
            events.append(
                EventRecord(
                    line_no=line_no,
                    day=day,
                    kind=kind,
                    target=target,
                    public=(kind == "execute"),
                    result=result,
                    raw_fields=head[2:],
                ),
            )
            if kind == "execute":
                final_outcome.setdefault("executions", []).append({"day": day, "target": target, "role": result})
            continue

        if kind in {"divine", "identify"}:
            head = line.split(",", 4)
            if len(head) < 5:
                parser_notes.append(f"Skipped malformed {kind} line {line_no}: {line}")
                continue
            events.append(
                EventRecord(
                    line_no=line_no,
                    day=day,
                    kind=kind,
                    actor=_safe_int(head[2]),
                    target=_safe_int(head[3]),
                    public=True,
                    result=head[4],
                    raw_fields=head[2:],
                ),
            )
            continue

        if kind == "result":
            head = line.split(",", 4)
            if len(head) >= 5:
                final_outcome = {
                    "day": day,
                    "winning_agent": _safe_int(head[2]),
                    "result_code": head[3],
                    "winning_camp": head[4],
                }
            events.append(
                EventRecord(
                    line_no=line_no,
                    day=day,
                    kind=kind,
                    actor=_safe_int(head[2]) if len(head) > 2 else None,
                    result=head[4] if len(head) > 4 else None,
                    public=True,
                    raw_fields=head[2:],
                ),
            )
            continue

        events.append(
            EventRecord(
                line_no=line_no,
                day=day,
                kind=kind,
                public=True,
                raw_fields=base_parts[2:],
            ),
        )

    for record in json_hints.get("agents", []):
        if not isinstance(record, dict):
            continue
        idx = int(record["idx"])
        if idx in agents_by_idx:
            continue
        agents_by_idx[idx] = AgentRecord(
            idx=idx,
            name=str(record["name"]),
            role=str(record["role"]),
            camp=str(record["camp"]),
        )

    agents = sorted(agents_by_idx.values(), key=lambda item: item.idx)
    if not agents:
        parser_notes.append("No agents were recovered from the log.")

    return GameRecord(
        log_path=str(log_path),
        json_path=str(json_path) if json_path is not None else None,
        agents=agents,
        events=events,
        parser_notes=parser_notes,
        json_hints=json_hints,
        final_outcome=final_outcome,
    )

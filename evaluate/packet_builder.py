"""Build prompt-ready judge packets from parsed logs."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from evaluate.models import AgentRecord, EventRecord, GameRecord
from evaluate.parser import parse_game_log


def _event_brief(event: EventRecord, names: dict[int, str]) -> dict[str, Any]:
    actor_name = names.get(event.actor, None) if event.actor is not None else None
    target_name = names.get(event.target, None) if event.target is not None else None
    return {
        "ref": event.ref,
        "day": event.day,
        "kind": event.kind,
        "actor": actor_name,
        "target": target_name,
        "text": event.text,
        "result": event.result,
        "status": event.status,
        "meta": event.meta,
    }


def _build_day_summaries(game: GameRecord) -> list[dict[str, Any]]:
    names = {agent.idx: agent.name for agent in game.agents}
    by_day: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "day": -1,
            "public_talks": [],
            "public_votes": [],
            "divinations": [],
            "identifications": [],
            "executions": [],
            "attacks": [],
            "whisper_count": 0,
            "attack_votes": [],
        },
    )

    for event in game.events:
        summary = by_day[event.day]
        summary["day"] = event.day
        if event.kind == "talk":
            summary["public_talks"].append(_event_brief(event, names))
        elif event.kind == "vote":
            summary["public_votes"].append(_event_brief(event, names))
        elif event.kind == "divine":
            summary["divinations"].append(_event_brief(event, names))
        elif event.kind == "identify":
            summary["identifications"].append(_event_brief(event, names))
        elif event.kind == "execute":
            summary["executions"].append(_event_brief(event, names))
        elif event.kind == "attack":
            summary["attacks"].append(_event_brief(event, names))
        elif event.kind == "whisper":
            summary["whisper_count"] += 1
        elif event.kind == "attackVote":
            summary["attack_votes"].append(_event_brief(event, names))

    return [by_day[day] for day in sorted(by_day)]


def _build_alive_timeline(game: GameRecord) -> dict[str, list[dict[str, Any]]]:
    names = {agent.idx: agent.name for agent in game.agents}
    timeline: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in game.events:
        if event.kind != "status" or event.actor is None:
            continue
        timeline[names[event.actor]].append(
            {
                "ref": event.ref,
                "day": event.day,
                "status": event.status,
                "role": event.result,
            },
        )
    return dict(timeline)


def _collect_role_actions(agent: AgentRecord, game: GameRecord, names: dict[int, str]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    relevant_types = {"divine", "identify", "attackVote", "attack", "execute"}
    for event in game.events:
        if event.kind not in relevant_types:
            continue
        if event.actor == agent.idx or event.target == agent.idx:
            actions.append(_event_brief(event, names))
    return actions


def _build_player_packet(agent: AgentRecord, game: GameRecord) -> dict[str, Any]:
    names = {record.idx: record.name for record in game.agents}
    talks = [
        _event_brief(event, names)
        for event in game.events
        if event.kind == "talk" and event.actor == agent.idx
    ]
    votes = [
        _event_brief(event, names)
        for event in game.events
        if event.kind == "vote" and event.actor == agent.idx
    ]
    whispers = [_event_brief(event, names) for event in game.events if event.kind == "whisper"]
    wolf_private_events = [
        _event_brief(event, names)
        for event in game.events
        if event.kind in {"attackVote", "attack"} or event.kind == "whisper"
    ]

    role_actions = _collect_role_actions(agent, game, names)
    alive_timeline = _build_alive_timeline(game).get(agent.name, [])
    talked_days = sorted({item["day"] for item in talks})
    voted_days = sorted({item["day"] for item in votes})
    whispered_days = sorted({item["day"] for item in whispers if item.get("actor") == agent.name})

    return {
        "agent": agent.to_dict(),
        "judge_scope": "postgame_full_info",
        "public_record": {
            "alive_timeline": alive_timeline,
            "talks": talks,
            "votes": votes,
            "role_actions": role_actions,
        },
        "private_record": {
            "available": agent.role in {"WEREWOLF", "POSSESSED"},
            "whispers": whispers if agent.role in {"WEREWOLF", "POSSESSED"} else [],
            "night_coordination": wolf_private_events if agent.role in {"WEREWOLF", "POSSESSED"} else [],
        },
        "derived_features": {
            "talk_count": len(talks),
            "vote_count": len(votes),
            "role_action_count": len(role_actions),
            "talked_days": talked_days,
            "voted_days": voted_days,
            "whispered_days": whispered_days,
            "used_private_info_available": agent.role in {"WEREWOLF", "POSSESSED"},
        },
        "scoring_dimensions": {
            "quality": [
                "strategy_quality_score",
                "role_consistency_score",
                "teamplay_score",
            ],
            "teamplay_breakdown": [
                "alignment_score",
                "coordination_signals_score",
                "vote_formation_score",
                "role_aware_teamplay_score",
            ],
            "penalties": [
                "anti_hallucination_penalty",
                "rules_compliance_penalty",
            ],
        },
    }


def build_judge_bundle(log_path: str | Path, json_path: str | Path | None = None) -> dict[str, Any]:
    """Build a prompt-ready bundle for one game."""
    resolved_log_path = Path(log_path)
    resolved_json_path = Path(json_path) if json_path is not None else None
    game = parse_game_log(resolved_log_path, resolved_json_path)

    day_summaries = _build_day_summaries(game)
    player_packets = [_build_player_packet(agent, game) for agent in game.agents]
    names = {agent.idx: agent.name for agent in game.agents}

    timeline_highlights = [
        _event_brief(event, names)
        for event in game.events
        if event.kind in {"divine", "identify", "vote", "execute", "attack", "attackVote"}
    ]

    return {
        "bundle_version": "judge-v1",
        "judge_scope": "postgame_full_info",
        "log_path": game.log_path,
        "json_path": game.json_path,
        "parser_notes": game.parser_notes,
        "json_hints": game.json_hints,
        "game_summary": {
            "agents": [agent.to_dict() for agent in game.agents],
            "final_outcome": game.final_outcome,
            "day_summaries": day_summaries,
            "timeline_highlights": timeline_highlights,
        },
        "player_packets": player_packets,
    }

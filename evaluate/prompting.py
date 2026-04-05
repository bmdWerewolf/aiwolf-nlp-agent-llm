"""Prompt rendering helpers for the judge pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Template


def render_judge_prompt(
    template_path: Path,
    rubric_path: Path,
    schema_path: Path,
    game_summary: dict[str, Any],
    player_packet: dict[str, Any],
) -> str:
    """Render the judge prompt for one player."""
    template = Template(template_path.read_text(encoding="utf-8"))
    rubric_text = rubric_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    return template.render(
        rubric_text=rubric_text,
        schema_text=schema_text,
        game_summary_json=json.dumps(game_summary, indent=2, ensure_ascii=False),
        player_packet_json=json.dumps(player_packet, indent=2, ensure_ascii=False),
    ).strip()

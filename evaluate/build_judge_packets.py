"""CLI for building judge bundles and optional prompt files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluate.packet_builder import build_judge_bundle
from evaluate.prompting import render_judge_prompt


def main() -> None:
    """Build a judge bundle from one log file."""
    parser = argparse.ArgumentParser(description="Build LLM-as-a-judge packets from an AIWolf game log.")
    parser.add_argument("--log", required=True, help="Path to server/logs/game/*.log")
    parser.add_argument("--json", help="Optional path to server/logs/json/*.json")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument(
        "--write-prompts",
        action="store_true",
        help="Render one prompt file per player with the default template.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle = build_judge_bundle(args.log, args.json)
    bundle_path = out_dir / "judge_bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.write_prompts:
        prompts_dir = out_dir / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        template_path = Path("evaluate/templates/postgame_judge_prompt.j2")
        rubric_path = Path("evaluate/rubric.md")
        schema_path = Path("evaluate/judge_schema.json")
        for player_packet in bundle["player_packets"]:
            player_name = player_packet["agent"]["name"]
            prompt_text = render_judge_prompt(
                template_path=template_path,
                rubric_path=rubric_path,
                schema_path=schema_path,
                game_summary=bundle["game_summary"],
                player_packet=player_packet,
            )
            (prompts_dir / f"{player_name}.prompt.md").write_text(prompt_text, encoding="utf-8")


if __name__ == "__main__":
    main()

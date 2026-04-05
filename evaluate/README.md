# evaluate/

This directory contains a `log-first` postgame `llm-as-a-judge` workflow for AIWolf games.

## What is included

- `parser.py`
  - Parses `server/logs/game/*.log`
  - Recovers optional metadata from `server/logs/json/*.json`
- `packet_builder.py`
  - Converts one game into a prompt-ready judge bundle
- `judge_schema.json`
  - Defines the expected judge output object
- `rubric.md`
  - Defines the scoring rubric and penalty logic
- `templates/postgame_judge_prompt.j2`
  - Prompt template used for one player
- `build_judge_packets.py`
  - CLI to export the bundle and prompt files
- `run_judge.py`
  - CLI to run the judge with the repository's configured LLM backend

## Scoring design

The pipeline separates:

- Validity layer
  - `anti_hallucination_penalty`
  - `rules_compliance_penalty`
- Quality layer
  - `strategy_quality_score`
  - `role_consistency_score`
  - `teamplay_score`

`teamplay_score` is computed from:

- `alignment_score`
- `coordination_signals_score`
- `vote_formation_score`
- `role_aware_teamplay_score`

## Bundle format

The exported `judge_bundle.json` contains:

- `game_summary`
  - agents
  - day summaries
  - timeline highlights
  - final outcome
- `player_packets`
  - one per player
  - public record
  - private record when applicable
  - derived features

## Usage

Build packets only:

```bash
python -m evaluate.build_judge_packets \
  --log server/logs/game/1773290733_bmd_1x_bmd_2x_bmd_3x_bmd_4x_bmd_5x_bmd_6x_bmd_7x_bmd_8x_bmd_9x.log \
  --json server/logs/json/1773290733_bmd_1x_bmd_2x_bmd_3x_bmd_4x_bmd_5x_bmd_6x_bmd_7x_bmd_8x_bmd_9x.json \
  --out evaluate/out/sample \
  --write-prompts
```

Run the judge end-to-end:

```bash
python -m evaluate.run_judge \
  --config config/config_gemini_jp.yml \
  --log server/logs/game/1773290733_bmd_1x_bmd_2x_bmd_3x_bmd_4x_bmd_5x_bmd_6x_bmd_7x_bmd_8x_bmd_9x.log \
  --json server/logs/json/1773290733_bmd_1x_bmd_2x_bmd_3x_bmd_4x_bmd_5x_bmd_6x_bmd_7x_bmd_8x_bmd_9x.json \
  --out evaluate/out/judge_run
```

Dry run without calling any model:

```bash
python -m evaluate.run_judge \
  --config config/config_gemini_jp.yml \
  --log server/logs/game/1773290733_bmd_1x_bmd_2x_bmd_3x_bmd_4x_bmd_5x_bmd_6x_bmd_7x_bmd_8x_bmd_9x.log \
  --json server/logs/json/1773290733_bmd_1x_bmd_2x_bmd_3x_bmd_4x_bmd_5x_bmd_6x_bmd_7x_bmd_8x_bmd_9x.json \
  --out evaluate/out/dry_run \
  --dry-run
```

## Notes

- The sidecar JSON in this repository is not always strict JSON in the current environment.
- Because of that, the pipeline is intentionally `log-first`.
- The JSON sidecar is treated as optional enrichment, not a hard dependency.

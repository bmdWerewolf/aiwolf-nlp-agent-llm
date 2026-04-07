# Benchmark Workflow

## Inputs

- Primary input: `server/logs/game/*.log`
- Optional enrichment: `server/logs/json/*.json` with the same stem as the log
- Config for full judge runs: `config/*.yml`
- Output root: `evaluate/out/`

If the user does not specify a log, inspect `server/logs/game/` and choose the most relevant file:

- newest file for "latest" or "most recent",
- a named file when the user gives a specific stem,
- the repository sample log when the user asks for a safe demonstration.

## Command Patterns

### 1. Build packets and prompts only

Use this when the user wants prompt inspection, packet debugging, or benchmark setup without model calls.

```bash
python -m evaluate.build_judge_packets \
  --log server/logs/game/<game>.log \
  --json server/logs/json/<game>.json \
  --out evaluate/out/<run-name> \
  --write-prompts
```

Omit `--json` if no same-stem sidecar exists.

### 2. Dry-run the full judge pipeline

Use this when the user wants to verify bundle creation and prompt rendering through the same CLI that the real benchmark uses.

```bash
python -m evaluate.run_judge \
  --config config/config_gemini_jp.yml \
  --log server/logs/game/<game>.log \
  --json server/logs/json/<game>.json \
  --out evaluate/out/<run-name> \
  --dry-run
```

This writes:

- `judge_bundle.json`
- `prompts/*.prompt.md`

It does not call the model and does not write `judge_results.json`.

### 3. Run the full judge

Use this only after verifying the config and credentials/backend.

```bash
python -m evaluate.run_judge \
  --config config/config_gemini_jp.yml \
  --log server/logs/game/<game>.log \
  --json server/logs/json/<game>.json \
  --out evaluate/out/<run-name>
```

## Config and Backend Checks

Read the chosen config file before a real run.

- If `llm.type` is `google`, require `GOOGLE_API_KEY`.
- If `llm.type` is `openai`, require `OPENAI_API_KEY` or a non-empty `openai.api_key`.
- If `llm.type` is `ollama`, confirm the configured `ollama.base_url` is reachable.

If these checks fail, do one of:

- switch to `--dry-run`,
- ask the user for the missing credential or backend,
- or stop and report the blocker.

## Suggested Run Naming

Use separate output folders under `evaluate/out/` such as:

- `evaluate/out/dry_run`
- `evaluate/out/judge_run`
- `evaluate/out/<config-name>-<log-stem>`
- `evaluate/out/<branch-or-model>-comparison-a`

Do not reuse a directory when the purpose is comparison.

## Review Order

After any run:

1. Open `judge_bundle.json` to confirm the log parsed correctly.
2. Open one or two `prompts/*.prompt.md` files to confirm rubric/template composition.
3. If it was a real run, inspect `judge_results.json`.
4. If results look malformed, inspect `judge_raw_outputs.json` for fence stripping or JSON extraction issues.

## Common Failure Modes

- Missing same-stem JSON: continue without `--json`.
- Missing API key or offline backend: stop at dry-run.
- Strange score output: inspect `judge_raw_outputs.json` and then the schema/rubric.
- Prompt looks wrong: check `evaluate/templates/postgame_judge_prompt.j2`, `evaluate/rubric.md`, and `evaluate/judge_schema.json`.

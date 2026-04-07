---
name: werewolf-agent-benchmark
description: Run, inspect, and compare the repository's AIWolf postgame benchmark workflow. Use when Codex needs to build judge bundles from server/logs/game/*.log, render judge prompts, run or dry-run evaluate.run_judge, review judge_results.json or judge_raw_outputs.json, or debug benchmark regressions for a werewolf agent.
---

# Werewolf Agent Benchmark

Use this skill to operate the repository's postgame benchmark pipeline in `evaluate/` against real AIWolf logs and judge artifacts.

## Quick Start

- Work from the repository root.
- Prefer a real game log from `server/logs/game/`.
- Pair the log with the same-stem JSON file from `server/logs/json/` when it exists, but do not block on missing JSON.
- Use one of these entry points:
  - Build bundle and prompts only: `python -m evaluate.build_judge_packets ... --write-prompts`
  - Dry-run the full judge pipeline: `python -m evaluate.run_judge ... --dry-run`
  - Run the full judge: `python -m evaluate.run_judge ...`

Read `references/workflow.md` before running commands. Read `references/output-review.md` before interpreting scores or debugging judge output.

## Workflow

1. Identify the input log, optional sidecar JSON, and a fresh output directory under `evaluate/out/`.
2. Decide whether the task is packet generation, dry-run validation, or a real judge run.
3. Check the selected config file before a real judge run:
   - `llm.type: google` requires `GOOGLE_API_KEY`
   - `llm.type: openai` requires `OPENAI_API_KEY` or an inline `openai.api_key`
   - `llm.type: ollama` requires a reachable Ollama server at the configured `base_url`
4. Prefer `--dry-run` first when the goal is pipeline validation, prompt inspection, or benchmark debugging.
5. After execution, inspect the artifacts in this order:
   - `judge_bundle.json`
   - `prompts/*.prompt.md`
   - `judge_results.json` when a real judge run was executed
   - `judge_raw_outputs.json` when parsing or score normalization looks suspicious
6. Summarize the benchmark with concrete evidence from artifacts instead of restating assumptions.

## Guardrails

- Reuse the repository CLIs in `evaluate/`; do not reimplement the benchmark flow in ad hoc scripts unless the user explicitly asks for automation.
- Treat the JSON sidecar as optional enrichment. The log is the primary source of truth.
- Keep each run in its own output directory so results stay comparable.
- When comparing logs, prompts, or configs, produce separate output directories and compare the generated artifacts rather than mixing runs.
- Do not claim a final score formula from memory; use `references/output-review.md`.
- Do not infer API availability. If credentials or the target LLM backend are missing, stop at dry-run or state the blocker clearly.

## Deliverables

When this skill is used, finish with:

- the exact command or command family that was run,
- the input log and optional JSON path,
- the output directory,
- whether the run was bundle-only, dry-run, or full judge,
- the main benchmark findings or blockers.

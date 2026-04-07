# Output Review

## Artifact Map

### `judge_bundle.json`

This is the normalized intermediate artifact built from the game log.

Key sections:

- `game_summary`
- `player_packets`

Use it to verify:

- the log parsed,
- agent identities and roles look correct,
- private information is only marked available where expected,
- the benchmark is scoring the game you think it is scoring.

### `prompts/*.prompt.md`

One rendered prompt per player packet.

Use these files to verify:

- the rubric text is included,
- the judge schema is embedded,
- the right player packet was rendered,
- prompt regressions are caused by packet/template changes rather than model output.

### `judge_results.json`

Present only after a real judge run.

Each object should include:

- `validity`
- `quality`
- `reasoning_summary`
- `strengths`
- `weaknesses`
- `key_evidence`
- `confidence`
- normalized fields added by the pipeline such as `final_judge_score`, `agent`, `agent_idx`, `role`, `team`, `judge_scope`, and `used_private_info`

### `judge_raw_outputs.json`

Present only after a real judge run.

Use this when:

- model output is wrapped in code fences,
- JSON parsing fails,
- a result is missing required fields,
- normalized scores look inconsistent with the raw model response.

## Score Interpretation

The quality layer contains:

- `strategy_quality_score`
- `role_consistency_score`
- `teamplay_breakdown`

`teamplay_score` is computed as the mean of:

- `alignment_score`
- `coordination_signals_score`
- `vote_formation_score`
- `role_aware_teamplay_score`

The validity layer contains:

- `anti_hallucination_penalty`
- `rules_compliance_penalty`

The final normalized score is:

`clamp(mean(strategy_quality_score, role_consistency_score, teamplay_score) - anti_hallucination_penalty - rules_compliance_penalty, 0, 5)`

## Review Checklist

When summarizing a benchmark result, check:

1. Did the run produce all expected files for the selected mode?
2. Does `judge_bundle.json` match the intended log and players?
3. Do prompt files reflect the expected rubric and schema?
4. If a real run was executed, are the scores internally consistent with the penalties and teamplay breakdown?
5. Do `key_evidence` and `reasoning_summary` point to concrete events instead of vague claims?

## Regression Triage

If benchmark output changed unexpectedly:

- compare the new and old prompt files first,
- then compare `judge_bundle.json`,
- then compare `judge_raw_outputs.json`,
- and only after that attribute the change to model behavior.

This order separates:

- parsing/packet regressions,
- prompt-template regressions,
- and backend/model variability.

# Postgame Judge Rubric

This rubric evaluates one player at a time in a completed AIWolf game.

## Scope

- Judge scope is `postgame_full_info`.
- Hidden information may be used to identify camp, role, whisper coordination, and actual wolf teamwork.
- Hidden information must not be used to punish a player for failing to know something that was not publicly knowable at the time.
- The judge should score effectiveness, not just surface plausibility.

## Validity Layer

### Anti-hallucination

Focus: whether the player's statements contradict already public facts at the time.

Examples:
- Treating a dead player as alive.
- Referring to a divine or identify result that never happened.
- Claiming a vote target or public event that is absent from the record.

Scoring method:
- Record violations, then assign `anti_hallucination_penalty`.
- Typical range:
  - `0.0`: no issue.
  - `0.5-1.0`: minor factual drift.
  - `1.5-3.0`: repeated or serious contradictions.

### Rules compliance

Focus: whether the player obeyed observable output and phase constraints.

Examples:
- Violating format or stage restrictions that are externally visible.
- Producing obviously non-compliant action text.
- Acting outside the allowed phase intent.

Scoring method:
- Record violations, then assign `rules_compliance_penalty`.
- Typical range:
  - `0.0`: compliant.
  - `0.5-1.0`: mild formatting or stage issues.
  - `1.5-3.0`: repeated or severe rule breaks.

## Quality Layer

### Strategy quality score

Question: did the player's speech create actionable progress instead of empty words?

`0`
- Pure noise, filler, or harmful drift.

`1`
- Mostly generic comments with little execution value.

`2`
- Some usable reasoning, but vague, weak, or late.

`3`
- Solid and usable reasoning that helps move the day.

`4`
- Strong actionable reasoning with clear targets or process guidance.

`5`
- Consistently high-impact reasoning that materially shapes correct or strategically useful action.

### Role consistency score

Question: did the player behave in a way that fits the role's actual job and timing?

Examples:
- Seer or Medium converting information into public team utility.
- Bodyguard acting around information preservation and threat management.
- Villager helping process and vote consolidation.
- Werewolf coordinating deception and preserving wolf equity.
- Possessed helping the wolf side instead of freelancing into anti-synergy.

`0`
- Role behavior strongly contradicts role goals.

`1`
- Mostly off-role or self-defeating.

`2`
- Partially role-consistent, but weak or inconsistent.

`3`
- Generally role-consistent and helpful.

`4`
- Strong role execution with good timing.

`5`
- Excellent role execution that clearly increases faction win chances.

### Teamplay score

Teamplay is the mean of the four sub-scores below.

#### Alignment score

Question: did the player act for faction win rather than personal correctness?

Village side:
- Helps create useful executions and stable process.

Wolf side:
- Helps create executable misdirection and protect allies when needed.

#### Coordination signals score

Question: did the player recognize and respond to partner or core-slot signals?

Village side:
- Tracks trusted pushers, public info roles, and emergent consensus.

Wolf side:
- Uses whisper plans, day cover, and non-destructive spacing with teammates.

#### Vote formation score

Question: did the player help produce a real vote rather than abstract suspicion?

High score requires:
- clear candidate,
- reasons,
- or visible contribution to vote convergence.

#### Role-aware teamplay score

Question: did the player execute team cooperation in a role-appropriate way?

Examples:
- info roles leading or clarifying the team process,
- villagers supporting process discipline,
- wolves sharing burden and night coordination.

For each teamplay sub-score:

`0`
- Strong anti-team behavior.

`1`
- Mostly disconnected from faction coordination.

`2`
- Some team utility, but limited or inconsistent.

`3`
- Clear positive team contribution.

`4`
- Strong and reliable team contribution.

`5`
- Excellent teamwork with visible strategic impact.

## Final score

The final score is not free-form.

Compute it as:

`final_judge_score = clamp(mean(strategy_quality_score, role_consistency_score, teamplay_score) - anti_hallucination_penalty - rules_compliance_penalty, 0, 5)`

## Evidence rules

- Every important judgment should cite concrete event references such as `L12`.
- Prefer short factual evidence over broad summaries.
- Keep the final reasoning compact and decision-oriented.

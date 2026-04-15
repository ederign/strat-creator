---
name: strategy.review
description: Adversarial review of refined strategies. Scores against rubric, then runs independent forked reviewers for detailed prose.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Skill, Agent
---

You are a strategy review orchestrator. Your job is to score and review the strategies in `artifacts/strat-tasks/`, producing per-strategy review files with numeric scores and detailed prose.

## Dry Run Mode

If `--dry-run` is in `$ARGUMENTS`, skip ALL external writes:
- Do NOT write or update any Jira issues
- DO still read from Jira and local artifacts (reads are safe)
- DO still create local review files in `artifacts/strat-reviews/`

## Step 1: Verify Artifacts Exist

Read files in `artifacts/strat-tasks/`. If no strategy artifacts exist or they haven't been refined yet (no "Strategy" section), tell the user to run `/strategy.refine` first and stop.

Check if prior reviews exist in `artifacts/strat-reviews/`. If any exist for the strategies being reviewed, read them — this is a re-review after revisions.

## Step 2: Fetch Architecture Context

```bash
bash scripts/fetch-architecture-context.sh
```

## Step 3: Bootstrap assess-strat

```bash
bash scripts/bootstrap-assess-strat.sh
```

This clones the assess-strat plugin into `.context/assess-strat/`, copies skills and agent definitions, and exports the rubric to `artifacts/strat-rubric.md`.

## Step 4: Score Strategies

For each strategy in `artifacts/strat-tasks/`, launch a strat-scorer agent to produce numeric scores. The assess-strat plugin provides the rubric and agent definition.

Resolve the plugin root: the bootstrap script clones it to `.context/assess-strat/`. Use this path as `{PLUGIN_ROOT}`.

For each strategy file, spawn one agent (model: opus, run_in_background: true, subagent_type: assess-strat:strat-scorer) with this prompt:

```
You are a strategy quality assessor. Your task:
1. Read `{PROMPT_PATH}` for the full scoring rubric.
2. Follow its instructions exactly, substituting {KEY} for the strategy key and {RUN_DIR} for the run directory. Read the strategy from {DATA_FILE} (not the path in the rubric's step 1).
3. If architecture context is available at `.context/architecture-context/`, use Glob and Grep to validate architecture claims against real component docs.
Strategy key: {KEY}
Data file: {DATA_FILE}
Run directory: {RUN_DIR}
```

Substitute all placeholders:
- `{PROMPT_PATH}` → absolute path of `{PLUGIN_ROOT}/scripts/agent_prompt.md`
- `{DATA_FILE}` → the strategy file path (e.g., `artifacts/strat-tasks/RHAISTRAT-1469.md`)
- `{KEY}` → the strategy key (e.g., `RHAISTRAT-1469`)
- `{RUN_DIR}` → `/tmp/strat-assess/review` (create this directory first with `mkdir -p`)

After all scorer agents complete, read each `.result.md` file from `{RUN_DIR}` to extract scores. Parse the scoring table to get Feasibility, Testability, Scope, and Architecture scores (each 0-2).

**Compute the verdict deterministically from the scores** — do not use LLM judgment:
```
APPROVE:  total >= 6  AND  no zeros
SPLIT:    scope = 0   AND  all others >= 1  AND  sum(others) >= 3
REVISE:   total >= 3  AND  at most one zero  AND  not SPLIT
REJECT:   total < 3   OR   2+ zeros
```

Only APPROVE gets `needs_attention=false`. Everything else gets `needs_attention=true`.

## Step 5: Run Prose Reviews

Use the **Skill tool** to invoke each of these reviewer skills in parallel. Call all four via the Skill tool simultaneously — each runs in its own isolated context and no reviewer sees another's output.

```
Skill(skill="strategy-feasibility-review")
Skill(skill="strategy-testability-review")
Skill(skill="strategy-scope-review")
Skill(skill="strategy-architecture-review")
```

Do NOT use the Agent tool for reviews. Use the Skill tool — the reviewer skills are defined in `.claude/skills/` and contain specific review instructions.

- **`strategy-feasibility-review`**: Can we build this with the proposed approach? Are effort estimates credible?
- **`strategy-testability-review`**: Are acceptance criteria testable? What edge cases are missing?
- **`strategy-scope-review`**: Is each strategy right-sized? Does the effort match the scope?
- **`strategy-architecture-review`** (if architecture context available): Are dependencies correctly identified? Are integration patterns correct?

Each reviewer receives:
- The strategy artifacts (`artifacts/strat-tasks/`)
- The source RFEs (`artifacts/rfes.md`, `artifacts/rfe-tasks/`)
- Prior review files from `artifacts/strat-reviews/` (if this is a re-review)

## Step 6: Write Per-Strategy Review Files

For each reviewed strategy, write a review file to `artifacts/strat-reviews/`. First, read the schema to know exact field names and allowed values:

```bash
python3 scripts/frontmatter.py schema strat-review
```

Then for each strategy, write the review body to `artifacts/strat-reviews/{id}-review.md`, then set frontmatter using the scores from Step 4 and prose verdicts from Step 5:

```bash
python3 scripts/frontmatter.py set artifacts/strat-reviews/<id>-review.md \
    strat_id=<strat_id> \
    recommendation=<verdict_from_scores> \
    needs_attention=<true_or_false> \
    scores.feasibility=<score> \
    scores.testability=<score> \
    scores.scope=<score> \
    scores.architecture=<score> \
    scores.total=<total> \
    reviewers.feasibility=<prose_verdict> \
    reviewers.testability=<prose_verdict> \
    reviewers.scope=<prose_verdict> \
    reviewers.architecture=<prose_verdict>
```

**The `recommendation` field comes from the numeric scores, not from the prose reviewers.** Scores govern the verdict; prose provides justification.

The review file body should contain:

```markdown
## Scores

| Criterion | Score | Notes |
|-----------|-------|-------|
| Feasibility | X/2 | [from scorer agent] |
| Testability | X/2 | [from scorer agent] |
| Scope | X/2 | [from scorer agent] |
| Architecture | X/2 | [from scorer agent] |
| **Total** | **X/8** | **VERDICT** |

## Feasibility
<assessment from feasibility reviewer>

## Testability
<assessment from testability reviewer>

## Scope
<assessment from scope reviewer>

## Architecture
<assessment from architecture reviewer, or "skipped — no context">

## Agreements
<where reviewers aligned>

## Disagreements
<where reviewers diverged — preserve both views>
```

Important: **Preserve disagreements.** If the feasibility reviewer says "this is fine" but the scope reviewer says "this is too big," report both views. Do not average or harmonize.

## Step 7: Advise the User

Based on the results:
- **All approved** (`needs_attention=false`): Tell the user strategies are ready for `/strat.prioritize`.
- **Some need revision** (`needs_attention=true`, verdict=REVISE): List specific issues by dimension. Tell the user to edit the strategy files, remove `needs-attention`, and re-run `/strategy.review`.
- **Split needed** (`needs_attention=true`, verdict=SPLIT): The strategy bundles too many features. Tell the user to decompose it into focused strategies.
- **Fundamental problems** (`needs_attention=true`, verdict=REJECT): Recommend revisiting the RFE or re-running `/strategy.refine` with different constraints.

$ARGUMENTS

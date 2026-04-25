---
name: strategy-review
description: Adversarial review of refined strategies. Scores against rubric, then runs independent forked reviewers for detailed prose.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Skill, Agent
---

You are a strategy review orchestrator. Your job is to score and review the strategies in `artifacts/strat-tasks/`, producing per-strategy review files with numeric scores and detailed prose.

## Dry Run Mode

If `--dry-run` is in `$ARGUMENTS`, skip ALL external writes:
- Do NOT write or update any Jira issues
- Do NOT post review comments to Jira — save them to `artifacts/strat-reviews/{id}-review-comment.md` instead
- DO still read from Jira and local artifacts (reads are safe)
- DO still create local review files in `artifacts/strat-reviews/`

## Step 1: Verify Artifacts Exist

Read files in `artifacts/strat-tasks/`. If no strategy artifacts exist or they haven't been refined yet (no "Strategy" section), tell the user to run `/strategy-refine` first and stop.

Check if prior reviews exist in `artifacts/strat-reviews/`. If any exist for the strategies being reviewed, read them — this is a re-review after revisions.

## Step 1a: Pipeline Label Gate

For each strategy found in `artifacts/strat-tasks/`, read its frontmatter to get the `jira_key`. If `jira_key` is not null, fetch the STRAT's labels from Jira:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_issue.py RHAISTRAT-NNNN --fields labels --markdown
```

If the STRAT has either `strat-creator-rubric-pass` or `strat-creator-needs-attention` in its labels, **skip this strategy** — it has already been processed by the pipeline:
- Do NOT review it
- Print `[SKIP] RHAISTRAT-NNNN — already has <label>, skipping review`
- Continue to the next strategy

If all strategies are skipped, print a summary and stop.

## Step 2: Fetch Architecture Context

If `--architecture-context <path>` is in `$ARGUMENTS`, use the local path:

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/fetch-architecture-context.sh <path>
```

Otherwise, fetch from remote:

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/fetch-architecture-context.sh
```

## Step 3: Bootstrap assess-strat

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/bootstrap-assess-strat.sh
```

This clones the assess-strat plugin into `.context/assess-strat/`, copies skills and agent definitions, and exports the rubric to `artifacts/strat-rubric.md`.

## Step 4: Score Strategies

For each strategy in `artifacts/strat-tasks/`, launch a strat-scorer agent to produce numeric scores. The assess-strat plugin provides the rubric and agent definition.

Resolve the plugin root: the bootstrap script clones it to `.context/assess-strat/`. Use this path as `{PLUGIN_ROOT}`.

Create the run directory:

```bash
mkdir -p /tmp/strat-assess/review
```

For each strategy file, spawn one agent (model: opus, run_in_background: true) with this prompt:

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
- `{RUN_DIR}` → `/tmp/strat-assess/review`

Wait for all scorer agents to complete.

## Step 5: Parse Scores and Apply Verdicts (AUTOMATED — no LLM judgment)

After all scorer agents have completed, run the scoring scripts to deterministically compute verdicts and apply them to review files:

```bash
# Parse .result.md files → scores.csv with deterministic verdicts
python3 .context/assess-strat/scripts/parse_results.py /tmp/strat-assess/review/

# Apply scores and verdicts to review file frontmatter
python3 ${CLAUDE_SKILL_DIR}/scripts/apply_scores.py /tmp/strat-assess/review/scores.csv \
    --review-dir artifacts/strat-reviews \
    --result-dir /tmp/strat-assess/review

# Print summary statistics
python3 .context/assess-strat/scripts/summarize_run.py /tmp/strat-assess/review/
```

**Do NOT manually extract scores, compute verdicts, or set frontmatter.** The scripts handle this deterministically. The verdict rules are:
```
APPROVE:  total >= 6  AND  no zeros       → needs_attention=false
REVISE:   total >= 3  AND  ≤1 zero        → needs_attention=true
REJECT:   total < 3   OR   2+ zeros       → needs_attention=true
```

## Step 6: Run Prose Reviews

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

## Step 7: Write Prose to Review Files

For each reviewed strategy, update the review file body in `artifacts/strat-reviews/{id}-review.md` with the prose from all four reviewers. The scores table was already written by `apply_scores.py` in Step 5 — add the prose sections after it.

The review file body should contain:

```markdown
## Scores
[already written by apply_scores.py — do not overwrite]

## Feasibility Review: {STRAT_ID} — {title}
<assessment from feasibility reviewer>

## Testability Review: {STRAT_ID} — {title}
<assessment from testability reviewer>

## Scope Review: {STRAT_ID} — {title}
<assessment from scope reviewer>

## Architecture Review: {STRAT_ID} — {title}
<assessment from architecture reviewer, or "skipped — no context">

## Agreements
<where reviewers aligned>

## Disagreements
<where reviewers diverged — preserve both views>
```

After writing prose, update the `reviewers.*` frontmatter fields with each prose reviewer's individual verdict:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/frontmatter.py set artifacts/strat-reviews/<id>-review.md \
    reviewers.feasibility=<prose_verdict> \
    reviewers.testability=<prose_verdict> \
    reviewers.scope=<prose_verdict> \
    reviewers.architecture=<prose_verdict>
```

**Important:** The `recommendation` field is NEVER changed by prose reviewers. It comes from the numeric scores only. Prose reviewers set their own `reviewers.*` verdicts for informational purposes — these do NOT affect the gate decision.

**Preserve disagreements.** If the feasibility reviewer says "this is fine" but the scope reviewer says "this is too big," report both views. Do not average or harmonize.

## Step 7a: Post Review Summary to Jira

For each reviewed strategy, compose a review summary comment and post it to the RHAISTRAT issue (or save to file in dry-run mode).

Read the review file frontmatter to get scores and recommendation:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/frontmatter.py read artifacts/strat-reviews/{id}-review.md
```

Compose the comment in markdown using this format:

```markdown
*[Strat Creator]* Strategy Review — {VERDICT} (Score: {total}/8)

| Criterion | Score | Status |
|-----------|-------|--------|
| Feasibility | {F}/2 | {✓ if 2, ⚠ if 1, ✗ if 0} |
| Testability | {T}/2 | {✓ if 2, ⚠ if 1, ✗ if 0} |
| Scope | {S}/2 | {✓ if 2, ⚠ if 1, ✗ if 0} |
| Architecture | {A}/2 | {✓ if 2, ⚠ if 1, ✗ if 0} |

{For each dimension scored < 2, one sentence summarizing the issue from the prose review.}

**Action:** {verdict-specific guidance}
```

Action text by verdict:
- **APPROVE**: "No action needed — strategy passed quality review."
- **REVISE**: "Edit the strategy to address flagged issues, then remove the `needs-attention` label. The pipeline will re-evaluate automatically."
- **REJECT**: "This strategy has fundamental problems. Consider revisiting the source RFE or re-running `/strategy-refine` with different constraints."

**Posting:**

Save the composed markdown to a temp file, then post:

```bash
python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from jira_utils import add_comment, markdown_to_adf
import os
comment_md = open(sys.argv[1]).read()
add_comment(os.environ['JIRA_SERVER'], os.environ['JIRA_USER'],
            os.environ['JIRA_TOKEN'], sys.argv[2], markdown_to_adf(comment_md))
" /tmp/strat-review-comment-{KEY}.md RHAISTRAT-NNNN
```

- **Dry-run mode**: Write the comment markdown to `artifacts/strat-reviews/{id}-review-comment.md` instead. Print `[DRY RUN] Review comment saved to artifacts/strat-reviews/{id}-review-comment.md`.
- **Jira credentials unavailable**: Save to file (same as dry-run) and notify the user.

## Step 7b: Attach Full Review File to Jira

If NOT in dry-run mode and `jira_key` is not null, attach the full review file to the RHAISTRAT issue as a Jira attachment. This gives reviewers access to the complete prose reviews alongside the summary comment.

```bash
python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from jira_utils import add_attachment, require_env
s, u, t = require_env()
add_attachment(s, u, t, sys.argv[1], sys.argv[2])
" RHAISTRAT-NNNN artifacts/strat-reviews/{id}-review.md
```

Print `[ATTACHMENT] Review file attached to RHAISTRAT-NNNN`.

In dry-run mode, skip and print `[DRY RUN] Skipping attachment for RHAISTRAT-NNNN`.

## Step 7c: Apply Verdict Labels

If NOT in dry-run mode and `jira_key` is not null, add the appropriate label based on the verdict:

```bash
python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from jira_utils import add_labels, require_env
s, u, t = require_env()
add_labels(s, u, t, sys.argv[1], sys.argv[2:])
" RHAISTRAT-NNNN <labels>
```

Labels by verdict:
- **APPROVE**: add `strat-creator-rubric-pass`
- **REVISE**: add `strat-creator-needs-attention`
- **REJECT**: add `strat-creator-needs-attention`

Print `[LABEL] <label> added to RHAISTRAT-NNNN`.

In dry-run mode, skip and print `[DRY RUN] Skipping labels for RHAISTRAT-NNNN`.

## Step 8: Advise the User

Based on the results:
- **All approved** (`needs_attention=false`): Tell the user strategies are ready for `/strat.prioritize`.
- **Some need revision** (`needs_attention=true`, verdict=REVISE): List specific issues by dimension. Tell the user to edit the strategy files, remove `needs-attention`, and re-run `/strategy-review`.
- **Fundamental problems** (`needs_attention=true`, verdict=REJECT): Recommend revisiting the RFE or re-running `/strategy-refine` with different constraints.

$ARGUMENTS

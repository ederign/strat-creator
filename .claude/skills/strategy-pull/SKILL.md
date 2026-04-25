---
name: strategy-pull
description: Pull a RHAISTRAT issue from Jira into the local/ workspace for human review. Only works on post-CI strategies.
user-invocable: true
allowed-tools: Read, Write, Bash, Glob, Grep
---

You are pulling a strategy from Jira into the local workspace so a human can review and iterate on it.

## Input

`$ARGUMENTS` must contain a RHAISTRAT key (e.g., `RHAISTRAT-1520`). If no key is provided, ask the user for one.

## Pull the Strategy

Run the pull script:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/pull_strategy.py $ARGUMENTS
```

This will:
1. Validate the strategy has a post-CI label (`strat-creator-rubric-pass` or `strat-creator-needs-attention`)
2. Fetch the strategy description from Jira
3. Write `local/strat-tasks/RHAISTRAT-NNNN.md` with `workflow: local` frontmatter
4. Fetch the linked RFE original and comments into `local/strat-originals/`
5. Fetch the review comment into `local/strat-reviews/`

If the script exits with code 1 (missing labels or not found), explain that only post-CI strategies can be pulled. If code 2 (missing credentials), tell the user to set `JIRA_SERVER`, `JIRA_USER`, and `JIRA_TOKEN`.

## After Pulling

Read the pulled strategy file and the review file (if present). Summarize for the user:

1. **Strategy title and priority**
2. **CI verdict**: approved (rubric-pass) or needs attention
3. **Review highlights**: if a review file was pulled, summarize the key findings
4. **Source RFE**: which RFE this strategy is derived from

Then advise the user on next steps:

- **If rubric-pass**: "The strategy passed CI review. Run `/strategy-refine` and `/strategy-review` to iterate locally, then `/strategy-signoff` when you're satisfied."
- **If needs-attention**: "The strategy was flagged by CI. Run `/strategy-refine` and `/strategy-review` to fix issues locally, then `/strategy-push` to resubmit to CI."

$ARGUMENTS

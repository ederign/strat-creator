---
name: strategy-push
description: Push a locally-refined strategy back to Jira and resubmit to CI. For needs-attention strategies only.
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

You are pushing an improved strategy back to Jira so CI can re-evaluate it. This skill is for strategies that were flagged with `strat-creator-needs-attention`.

## Input

`$ARGUMENTS` must contain a RHAISTRAT key (e.g., `RHAISTRAT-1520`). If no key is provided, ask the user for one.

## Step 1: Validate Pre-Conditions

Read the strategy file from `local/strat-tasks/RHAISTRAT-NNNN.md`. Verify it exists and has `workflow: local` in its frontmatter.

Then fetch the current labels from Jira:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_issue.py RHAISTRAT-NNNN --fields labels --markdown
```

**Guard checks:**

- If the issue has `strat-creator-rubric-pass` (not `needs-attention`): tell the user this strategy is already CI-approved and they should use `/strategy-signoff` instead. **Stop here.**
- If the issue does NOT have `strat-creator-needs-attention`: tell the user this strategy hasn't been through CI review yet and cannot be pushed. **Stop here.**
- If the local file does not exist: tell the user to run `/strategy-pull RHAISTRAT-NNNN` first. **Stop here.**

## Step 2: Push Strategy Content

Push the updated strategy section to Jira:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/push_strategy.py RHAISTRAT-NNNN local/strat-tasks/RHAISTRAT-NNNN.md
```

## Step 3: Remove needs-attention Label

Remove the `strat-creator-needs-attention` label to allow CI to re-process:

```bash
python3 -c "
import sys; sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from jira_utils import remove_labels, require_env
s, u, t = require_env()
remove_labels(s, u, t, 'RHAISTRAT-NNNN', ['strat-creator-needs-attention'])
"
```

Print `[LABEL] strat-creator-needs-attention removed from RHAISTRAT-NNNN`.

## Step 4: Advise the User

Tell the user:

- "Strategy pushed and resubmitted to CI. The pipeline will re-evaluate on the next run."
- "Once CI approves (adds `strat-creator-rubric-pass`), use `/strategy-pull RHAISTRAT-NNNN` again and `/strategy-signoff RHAISTRAT-NNNN` to complete the review."

$ARGUMENTS

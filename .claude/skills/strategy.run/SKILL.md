---
name: strategy.run
description: Reference for the full strategy pipeline sequence. For batch execution, run each step as a separate Claude session.
user-invocable: false
allowed-tools: Read, Glob, Grep
---

# Strategy Pipeline Sequence

The full pipeline runs **create → refine → review** in sequence. Artifacts on disk are the handoff between steps.

## Important: Run Each Step in a Separate Session

Per Lesson 1 ("The Agent Forgets Mid-Run") and Lesson 12 ("Thin Dispatcher Pattern") from the AgenticCI lessons: chaining multiple skills in a single Claude session causes context compression to destroy instructions at scale. Each step should run in its own Claude session with a fresh context window.

### Manual (local)

Run each command in a **separate Claude session**:

```
# Session 1
/strategy.create config/test-rfes.yaml --dry-run

# Session 2 (new Claude session)
/strategy.refine --dry-run

# Session 3 (new Claude session)
/strategy.review --dry-run
```

### CI (GitLab)

Each step is a separate `run-claude.sh` invocation in the CI script:

```yaml
script:
  - run-claude.sh "/strategy.create config/test-rfes.yaml --dry-run"
  - run-claude.sh "/strategy.refine --dry-run"
  - run-claude.sh "/strategy.review --dry-run"
```

## Pipeline Steps

| Step | Skill | Input | Output | Verification |
|------|-------|-------|--------|--------------|
| 1 | `strategy.create` | RFE IDs or config YAML | `artifacts/strat-tasks/STRAT-*.md` (Draft) | Stub file exists for each RFE |
| 2 | `strategy.refine` | Draft stubs + architecture context | `artifacts/strat-tasks/STRAT-*.md` (Refined) | Frontmatter status = Refined |
| 3 | `strategy.review` | Refined strategies | `artifacts/strat-reviews/*-review.md` | Review file exists for each strategy |

## Flags

- `--dry-run` — Pass to every step. Skips all Jira writes, still creates local artifacts.

$ARGUMENTS

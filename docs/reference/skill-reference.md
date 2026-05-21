# Skill Reference

All Claude Code skills defined in `.claude/skills/` for the strat-creator pipeline.

## CI Pipeline Skills

### strategy-create

Creates strategy stubs from approved RFEs.

| | |
|---|---|
| **Invocation** | `/strategy-create` |
| **Inputs** | RFE IDs (from JQL or batch config) |
| **Outputs** | `artifacts/strat-tasks/RHAISTRAT-NNNN.md`, `artifacts/strat-originals/RHAIRFE-NNNN.md` |
| **Labels set** | `strat-creator-auto-created` |
| **Dry-run** | Yes (`--dry-run`) |
| **Scripts** | `scripts/clone_issue.py`, `scripts/fetch_issue.py`, `scripts/frontmatter.py` |

Gate: Skips RFEs that already have a RHAISTRAT with `strat-creator-auto-created`, `strat-creator-rubric-pass`, or `strat-creator-needs-attention`.

### strategy-refine

Adds technical approach using architecture context. Applies size-scaled templates.

| | |
|---|---|
| **Invocation** | `/strategy-refine [RHAISTRAT-NNNN]` |
| **Inputs** | Strategy files in `artifacts/strat-tasks/` (or `local/strat-tasks/`) |
| **Outputs** | Updated strategy files with technical approach, dependencies, NFRs |
| **Labels set** | `strat-creator-auto-refined` |
| **Dry-run** | Yes (`--dry-run`) |
| **Scripts** | `scripts/fetch-architecture-context.sh`, `scripts/frontmatter.py` |

Accepts `--architecture-context <path>` for local overlay testing.

### strategy-review

Orchestrates scoring and prose reviews.

| | |
|---|---|
| **Invocation** | `/strategy-review [RHAISTRAT-NNNN]` |
| **Inputs** | Refined strategies in `artifacts/strat-tasks/` (or `local/strat-tasks/`) |
| **Outputs** | `artifacts/strat-reviews/RHAISTRAT-NNNN-review.md` |
| **Labels set** | `strat-creator-rubric-pass` or `strat-creator-needs-attention` |
| **Dry-run** | Yes (`--dry-run`) |
| **Scripts** | `scripts/bootstrap-assess-strat.sh`, `scripts/apply_scores.py` |

Bootstraps the assess-strat plugin, spawns a scorer agent, then invokes 5 prose reviewer skills in parallel.

## Prose Reviewer Skills

These are invoked by `strategy-review`, not directly by users.

### strategy-feasibility-review

| | |
|---|---|
| **Focus** | Technical viability, implementation complexity, effort estimate credibility |
| **Scores** | Contributes to numeric feasibility score (0-2) |
| **Inputs** | Strategy files, RFE originals, prior reviews |

### strategy-testability-review

| | |
|---|---|
| **Focus** | Acceptance criteria measurability, edge cases, test strategy |
| **Scores** | Contributes to numeric testability score (0-2) |
| **Inputs** | Strategy files, RFE originals, prior reviews |

### strategy-scope-review

| | |
|---|---|
| **Focus** | Right-sizing, effort/scope matching, RFE coverage completeness |
| **Scores** | Contributes to numeric scope score (0-2) |
| **Inputs** | Strategy files, RFE originals, prior reviews |

### strategy-architecture-review

| | |
|---|---|
| **Focus** | Dependencies, integration patterns, component interactions |
| **Scores** | Contributes to numeric architecture score (0-2) |
| **Inputs** | Strategy files, RFE originals, prior reviews, architecture context |

### strategy-security-review

| | |
|---|---|
| **Focus** | Auth, data protection, cryptographic compliance, network security, supply chain, agent/MCP risks |
| **Scores** | **Prose-only. Does not contribute to numeric score.** |
| **Inputs** | Strategy files, RFE originals, prior reviews, NFR checklist |

Uses a 47-item NFR checklist across 11 security categories.

## Human Review Skills

### strategy-pull

| | |
|---|---|
| **Invocation** | `/strategy-pull RHAISTRAT-NNNN` |
| **Inputs** | A RHAISTRAT key with `strat-creator-rubric-pass` or `strat-creator-needs-attention` |
| **Outputs** | `local/strat-tasks/`, `local/strat-originals/`, `local/strat-reviews/` |
| **Scripts** | `scripts/pull_strategy.py`, `scripts/fetch_issue.py` |

Fetches strategy, original RFE, and review into the `local/` workspace for human review.

### strategy-push

| | |
|---|---|
| **Invocation** | `/strategy-push RHAISTRAT-NNNN` |
| **Inputs** | Locally refined strategy in `local/strat-tasks/` |
| **Outputs** | Updated RHAISTRAT in Jira, `strat-creator-needs-attention` label removed |
| **Scripts** | `scripts/push_strategy.py` |

Pushes fixes back to Jira and resubmits for CI re-evaluation. Only works on needs-attention strategies.

### strategy-signoff

| | |
|---|---|
| **Invocation** | `/strategy-signoff RHAISTRAT-NNNN` |
| **Inputs** | Strategy with `strat-creator-rubric-pass` label |
| **Outputs** | `strat-creator-human-sign-off` label applied, review posted to Jira |
| **Scripts** | `scripts/push_strategy.py` |

Signs off a rubric-pass strategy as feature-ready. Pushes content, posts review summary comment, attaches full review file.

## Utility Skills

### export-rubric

| | |
|---|---|
| **Invocation** | `/export-rubric` |
| **Outputs** | `artifacts/strat-rubric.md` |

Exports the assess-strat scoring rubric for reference.

## External Dependencies

These are not Claude Code skills in `.claude/skills/`. They are bootstrapped at runtime.

### assess-strat (plugin)

Scoring rubric and scorer agent definition. Cloned into `.context/assess-strat/` by `scripts/bootstrap-assess-strat.sh`. Provides the rubric that `strat-scorer` uses to produce numeric scores.

### strat-scorer (agent)

Restricted agent (Read/Write/Glob/Grep only) defined in `.claude/agents/strat-scorer.md`. Generated by the assess-strat bootstrap. Produces numeric scores against the rubric.

# strat-creator

Strategy refinement pipeline for RHAI (Red Hat AI) features. Takes approved RFEs from the RFE assessment pipeline and produces structured strategy documents ready for development planning.

## What This Does

Given an approved RFE (from the `rfe-creator` pipeline), this pipeline:

1. **Creates** a strategy stub from the RFE data (`strategy.create`)
2. **Refines** the stub into a structured strategy using architecture context (`strategy.refine`)
3. **Reviews** the strategy across 4 dimensions — feasibility, testability, scope, architecture (`strategy.review`)
4. **Revises** based on review feedback with human-in-the-loop (planned)
5. **Submits** the final strategy to Jira as a RHAISTRAT issue (planned)

Each step runs in its own Claude session. Artifacts on disk are the handoff between steps.

## Implementation Status

| Skill | Status | Description |
|-------|--------|-------------|
| `strategy.create` | Implemented | Creates strategy stubs from approved RFEs, saves original RFE snapshots |
| `strategy.refine` | Implemented | Adds technical approach using architecture context, size-scaled templates |
| `strategy.review` | Implemented | Orchestrates 4 independent forked reviewers |
| `strategy-feasibility-review` | Implemented | Technical viability and effort credibility |
| `strategy-testability-review` | Implemented | Measurable criteria and edge cases |
| `strategy-scope-review` | Implemented | Right-sizing and scope boundaries |
| `strategy-architecture-review` | Implemented | Platform fit and dependency correctness |
| `strategy.run` | Reference | Pipeline sequence documentation (not invocable — each step runs in its own session) |
| `generate-report.py` | Implemented | HTML report with summary table and drill-down details |
| `strategy.revise` | Not started | Revision cycle until rubric-pass or human exclusion |
| `strategy.submit` | Not started | Deterministic Jira writes via script |
| `security-review` | Not started | Security dimension reviewer |
| `api-readiness-review` | Not started | API readiness dimension reviewer |

## Project Structure

```
strat-creator/
├── scripts/          # Reusable Python/shell scripts (Jira, frontmatter, state, report)
├── .claude/skills/   # Claude Code skills defining each pipeline step
├── config/           # Test RFE IDs and pipeline configuration
├── rubric/           # Quality rubric with scoring criteria (planned)
└── artifacts/        # Pipeline output (gitignored)
    ├── strat-tasks/      # Generated strategy documents
    ├── strat-reviews/    # Review outputs per dimension
    ├── strat-originals/  # Original RFE snapshots
    └── reports/          # Timestamped HTML reports
```

## Related Projects

- **rfe-creator** — Phase 1: RFE assessment pipeline (upstream). Has `strat.*` skill stubs that these skills were forked from.
- **strat-pipeline** (GitLab) — CI runner for this pipeline

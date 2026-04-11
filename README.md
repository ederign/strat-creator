# strat-creator

Strategy refinement pipeline for RHAI (Red Hat AI) features. Takes approved RFEs from the RFE assessment pipeline and produces structured strategy documents ready for development planning.

## What This Does

Given an approved RFE (from the `rfe-creator` pipeline, score >= 7, no zeros), this pipeline:

1. **Creates** a strategy stub from the RFE data (`strat.create`)
2. **Refines** the stub into a structured strategy using architecture context (`strat.refine`)
3. **Reviews** the strategy across multiple dimensions — feasibility, testability, scope, architecture (`strat.review`)
4. **Revises** based on review feedback (planned)
5. **Submits** the final strategy to Jira as a RHAISTRAT issue (planned)

## Project Structure

```
strat-creator/
├── scripts/          # Reusable Python/shell scripts (Jira, frontmatter, state)
├── .claude/skills/   # Claude Code skills defining each pipeline step
├── config/           # Test RFE IDs and pipeline configuration
├── rubric/           # Quality rubric with scoring criteria
└── artifacts/        # Pipeline output (gitignored)
    ├── strat-tasks/      # Generated strategy documents
    ├── strat-reviews/    # Review outputs per dimension
    └── strat-originals/  # Original RFE snapshots
```

## Related Projects

- **rfe-creator** — Phase 1: RFE assessment pipeline (upstream)
- **strat-pipeline** (GitLab) — CI runner for this pipeline

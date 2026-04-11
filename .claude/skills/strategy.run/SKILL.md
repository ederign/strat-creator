---
name: strategy.run
description: Run the full strategy pipeline (create → refine → review) on one or more RFEs.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Skill, AskUserQuestion
---

You are a pipeline orchestrator. Your job is to run the full strategy pipeline on the provided RFEs by invoking each skill in sequence.

## Dry Run Mode

If `--dry-run` is in `$ARGUMENTS`, pass `--dry-run` to every skill invocation. This prevents all Jira writes while still creating local artifacts.

## Step 1: Parse Arguments

Extract RFE IDs and flags from `$ARGUMENTS`. RFE IDs look like `RHAIRFE-NNNN`. If no RFE IDs are provided, check `config/test-rfes.yaml` and offer to run on all configured RFEs.

## Step 2: Run strategy.create

Invoke `/strategy.create` with all RFE IDs and flags:

```
/strategy.create <RFE-IDs> [--dry-run]
```

Wait for completion. Verify that `artifacts/strat-tasks/` contains a stub file for each RFE before proceeding. If any are missing, report the failure and stop.

## Step 3: Run strategy.refine

Invoke `/strategy.refine` with flags:

```
/strategy.refine [--dry-run]
```

Wait for completion. Verify that each strategy file in `artifacts/strat-tasks/` has status `Refined` (check frontmatter). If any failed to refine, report but continue with the ones that succeeded.

## Step 4: Run strategy.review

Invoke `/strategy.review` with flags:

```
/strategy.review [--dry-run]
```

Wait for completion. Verify that `artifacts/strat-reviews/` contains a review file for each refined strategy.

## Step 5: Summary

Print a summary table:

```
| RFE | Strat ID | Created | Refined | Reviewed | Recommendation |
|-----|----------|---------|---------|----------|----------------|
| RHAIRFE-NNNN | STRAT-NNNN | yes | yes | yes | approve/revise/reject |
```

Report any failures or skipped steps.

$ARGUMENTS

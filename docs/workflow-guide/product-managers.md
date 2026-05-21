# Workflow Guide: Product Managers

You own RFEs in Jira and need to track how they become strategies. Here's what happens at each stage and what you need to do.

## Your Role in the Pipeline

As a PM, you primarily interact with the pipeline through Jira. You create or approve RFEs, and the automation handles turning them into strategies. Your main responsibility is making sure RFEs are well-formed and tracking their progress.

## Step 1: Ensure Your RFE is Pipeline-Ready

For an RFE to enter the strategy pipeline, it needs:

1. **Correct project**: Must be in `RHAIRFE`
2. **Scope label**: `strat-creator-3.5` (or a matching Target Version like `rhoai-3.5`)
3. **Quality gate**: At least one of:
    - `rfe-creator-autofix-rubric-pass` (CI-approved by rfe-creator)
    - `tech-reviewed` (manually approved by a human reviewer)
4. **Not closed**: Status must not be `Closed`, `Resolved`, or `Draft`

If your RFE was processed by the [rfe-creator pipeline](../pipeline-stages/rfe-creation.md), these labels are applied automatically. If you created the RFE manually, add `strat-creator-3.5` and `tech-reviewed` yourself.

## Step 2: Wait for CI Processing

Once your RFE meets the criteria above, the CI pipeline will pick it up automatically in the next batch run. The pipeline:

1. Creates a RHAISTRAT ticket linked to your RHAIRFE via a Cloners link
2. Refines it into a full strategy with technical approach, dependencies, and NFRs
3. Scores it on feasibility, testability, scope, and architecture

You don't need to do anything during this stage. Processing typically completes within a single pipeline run.

## Step 3: Check the Verdict

After CI finishes, check the RHAISTRAT ticket linked to your RFE. Look for one of these labels:

| Label | What It Means | What Happens Next |
|-------|--------------|-------------------|
| `strat-creator-rubric-pass` | Strategy passed quality checks | A staff engineer will review and sign off |
| `strat-creator-needs-attention` | Strategy needs human fixes | A staff engineer will fix inputs and resubmit |

You can also check the [dashboard](https://strat-dashboard-0f1209.gitlab.io/) for an overview of all strategies and their scores.

## Step 4: Track to Completion

A strategy is fully complete when it has the `strat-creator-human-sign-off` label on the RHAISTRAT ticket. At that point, it's feature-ready for backlog grooming and sprint planning.

**JQL to find your completed strategies:**

```
project = RHAISTRAT AND labels = "strat-creator-human-sign-off" AND issueFunction in linkedIssuesOf("project = RHAIRFE AND reporter = currentUser()")
```

## Summary

| When | What You Do |
|------|------------|
| RFE created | Ensure it has `strat-creator-3.5` label and quality gate label |
| CI running | Nothing; wait for pipeline to process |
| Verdict arrives | Check RHAISTRAT label or dashboard |
| Sign-off complete | Strategy is feature-ready |

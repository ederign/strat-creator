# Workflow Guide: Engineering Managers

You track pipeline progress, configure batch runs, and ensure strategies move through the pipeline toward feature-readiness.

## Your Role in the Pipeline

You oversee the strategy pipeline at a macro level: which RFEs are being processed, how strategies are scoring, which ones need human attention, and overall progress toward the release.

## Monitoring Progress

### Dashboard

The [strat-dashboard](https://strat-dashboard-0f1209.gitlab.io/) shows:

- **Aggregate scores** across all strategies in the current release
- **Per-run trends** showing how scores change over pipeline iterations
- **Strategy status breakdown**: rubric-pass vs needs-attention vs signed-off
- **Pipeline diagram** showing the flow of strategies through stages

### JQL Queries

Track strategies by status:

```
-- All strategies for current release
project = RHAISTRAT AND labels = "strat-creator-3.5"

-- Awaiting human review
project = RHAISTRAT AND labels = "strat-creator-rubric-pass" AND labels != "strat-creator-human-sign-off"

-- Needs attention (blocked on human fixes)
project = RHAISTRAT AND labels = "strat-creator-needs-attention"

-- Completed (feature-ready)
project = RHAISTRAT AND labels = "strat-creator-human-sign-off"

-- Stuck in processing (possible crash)
project = RHAISTRAT AND labels = "strat-creator-processing"
```

## Configuring Batch Runs

The pipeline processes RFEs in batches. You control which RFEs enter each batch.

### JQL Mode (automatic)

The default mode queries Jira using filters from `config/pipeline-settings.yaml`. To check which RFEs would be selected:

```bash
python3 scripts/list-rfe-ids.py --jql-default
```

Adjust batch size:

```bash
python3 scripts/list-rfe-ids.py --jql-default --batch-size 20
```

### Config File Mode (manual)

For targeted runs, create a YAML batch file in `config/engineering35-batches/`:

```yaml
rfe_ids:
  - RHAIRFE-1234
  - RHAIRFE-5678
```

Then run with `--config config/engineering35-batches/your-batch.yaml`.

## Triaging Needs-Attention Strategies

When strategies get `strat-creator-needs-attention`:

1. Check the review on the [dashboard](https://strat-dashboard-0f1209.gitlab.io/) or in Jira to understand what failed
2. Assign to the appropriate staff engineer or SME based on the domain
3. Track until the strategy gets `strat-creator-rubric-pass` and then `strat-creator-human-sign-off`

## Handling Stuck Processing

If a strategy has `strat-creator-processing` for more than an hour, the pipeline job may have crashed. To unlock:

```bash
python3 scripts/lock_issues.py unlock RHAIRFE-NNNN
```

See [Troubleshooting](../reference/troubleshooting.md) for more details.

## Understanding Pre-Filter Gaps

The pipeline's pre-filter sometimes excludes valid RFEs or passes through already-processed ones. See [RFE Discovery & Filtering](../pipeline-stages/rfe-discovery-filtering.md) for the full explanation and the `--include-processed` bypass flag.

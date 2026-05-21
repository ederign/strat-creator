# Jira Labels & Fields

Complete reference for labels and fields used by the strat-creator and rfe-creator pipelines.

## RHAISTRAT Labels (strat-creator)

| Label | Meaning | Applied By |
|-------|---------|------------|
| `strat-creator-3.5` | In scope for 3.5 release pipeline | Manual or batch config |
| `strat-creator-auto-created` | Strategy was created by CI | `strategy-create` skill |
| `strat-creator-auto-refined` | Strategy was refined by CI | `strategy-refine` skill |
| `strat-creator-auto-revised` | Strategy content was revised during review | `strategy-review` skill |
| `strat-creator-rubric-pass` | CI verdict: passed quality rubric | `strategy-review` skill |
| `strat-creator-needs-attention` | CI verdict: needs human intervention | `strategy-review` skill |
| `strat-creator-processing` | Concurrency lock: pipeline is actively processing | `scripts/lock_issues.py` |
| `strat-creator-ignore` | Manual exclusion from pipeline runs | Manual |
| `strat-creator-human-sign-off` | Human reviewed and approved | `strategy-signoff` skill |

## RHAIRFE Labels (referenced by strat-creator)

| Label | Meaning |
|-------|---------|
| `strat-creator-3.5` | RFE is in scope for strategy pipeline |
| `rfe-creator-autofix-rubric-pass` | RFE passed rfe-creator quality rubric |
| `tech-reviewed` | RFE was manually tech-reviewed |
| `rfe-creator-auto-created` | RFE was created by automation |
| `rfe-creator-auto-revised` | RFE content was modified by auto-revision |
| `rfe-creator-split-original` | Parent RFE that was decomposed |
| `rfe-creator-split-result` | Child RFE from a split |
| `rfe-creator-needs-attention` | Automation couldn't fully resolve issues |
| `rfe-creator-feasibility-pass` | Feasibility check passed |
| `rfe-creator-feasibility-fail` | Feasibility check failed |
| `rfe-creator-feasibility-unknown` | Feasibility indeterminate |

## Jira Field Mappings

### RHAISTRAT Project

| Field | Value |
|-------|-------|
| **Project** | `RHAISTRAT` |
| **Issue Type** | `Feature` |
| **Clone link type** | `Cloners` (outward: "clones", inward: "is cloned by") |
| **Related link type** | `Related` |

### RHAIRFE Project (source, read-only)

| Field | Value |
|-------|-------|
| **Project** | `RHAIRFE` |
| **Issue Type** | `Feature Request` |

## JQL Filters

From `config/pipeline-settings.yaml`:

### RFE Selection Query

```sql
project = RHAIRFE
AND (labels = "strat-creator-3.5"
     OR cf[10855] in ("rhoai-3.5", "rhoai-3.5.EA1", "rhoai-3.5.EA2"))
AND (labels = "rfe-creator-autofix-rubric-pass"
     OR labels = "tech-reviewed")
AND status NOT IN ("Closed", "Resolved", "Draft")
ORDER BY key ASC
```

### Skip Labels (pre-filter)

Strategies with these labels cause their source RFE to be excluded from batching:

- `strat-creator-rubric-pass`
- `strat-creator-needs-attention`
- `strat-creator-processing`

### Excluded STRAT Statuses

Strategies in these statuses cause their source RFE to be excluded:

- `In Progress`
- `Review`
- `Release Pending`
- `Closed`
- `Resolved`

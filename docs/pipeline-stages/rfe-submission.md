# RFE Submission

> **Owner:** rfe-creator pipeline
> **Last verified:** 2026-05-21

## What Happens

RFEs that passed assessment (recommendation = submit) are pushed to the RHAIRFE Jira project as Feature Request tickets.

### For New RFEs

- Creates a new Jira ticket (RHAIRFE-NNNN)
- Renames the local file from `RFE-NNN.md` to `RHAIRFE-NNNN.md`
- Sets status to `Submitted` in frontmatter

### For Existing RFEs

- Updates the Jira description with revised content
- Keeps the existing Jira key

### Labels Applied

| Label | Applied When |
|-------|-------------|
| `rfe-creator-auto-created` | New ticket created by automation |
| `rfe-creator-auto-revised` | Content was modified by auto-revision |
| `rfe-creator-autofix-rubric-pass` | Passed quality rubric (recommendation = submit) |
| `rfe-creator-split-original` | Parent RFE that was decomposed |
| `rfe-creator-split-result` | Child RFE from a split |
| `rfe-creator-needs-attention` | Automation couldn't fully resolve issues |
| `rfe-creator-feasibility-pass` | Feasibility check passed |
| `rfe-creator-feasibility-fail` | Feasibility check failed |
| `rfe-creator-feasibility-unknown` | Feasibility indeterminate |

## What Triggers This Stage

- An RFE with recommendation = submit after the assessment stage

## What It Produces

- An RHAIRFE ticket in Jira with appropriate labels
- Status in Jira: `New`

## Next Stage

[RFE Discovery & Filtering](rfe-discovery-filtering.md): The strat-creator pipeline queries Jira to find eligible RFEs for strategy creation.

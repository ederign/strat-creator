# RFE Creation

> **Owner:** rfe-creator pipeline
> **Last verified:** 2026-05-21

## What Happens

An RFE (Request for Enhancement) captures a business need. It describes the WHAT and WHY but never the HOW. RFEs can be created two ways:

1. **Via rfe-creator pipeline** (`/rfe.create`): Claude asks 2-5 clarifying questions to validate the need, then generates a structured RFE
2. **Manually in Jira**: Create a Feature Request in the RHAIRFE project directly

### Key Rules

- One RFE per distinct business need. If the input describes multiple needs, rfe-creator creates multiple RFEs.
- RFEs must not include technical approach, dependencies, or implementation details. That's what strategies are for.
- Each RFE gets a priority (Blocker/Critical/Major/Normal/Minor) and size (S/M/L/XL)

## What Triggers This Stage

- A PM or stakeholder identifies a business need
- The rfe-creator pipeline is invoked with `/rfe.create`

## What It Produces

- An RHAIRFE ticket in Jira (or a local `RFE-NNN.md` file pre-submission)
- Status: `Draft` (local) or `New` (in Jira)

## Next Stage

[RFE Assessment](rfe-assessment.md): The RFE is scored against a quality rubric and checked for technical feasibility.

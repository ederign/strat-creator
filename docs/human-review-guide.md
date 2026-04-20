# Human Review Guide

How to handle strategies that the pipeline flagged as needing attention?

> **Audience**: Staff engineers and architects on the RHAI team who receive `strat-creator-needs-attention` notifications from the strategy pipeline.
>
> **Entry gate labels**: `strat-creator-3.5` + (`rfe-creator-autofix-rubric-pass` or `tech-reviewed`)
> **Approval label**: `strat-creator-rubric-pass`
> **Human Escalation label**: `strat-creator-needs-attention`
>
> **WARNING: Always use `--dry-run` when running locally.** Dry-run mode reads from Jira but never writes back — no labels, no comments, no tickets are modified. Running without `--dry-run` will create and update real Jira tickets.

## What Is This?

The strategy pipeline (strat-creator) takes approved RFEs, which describe the WHAT and WHY, and produces the HOW: actionable implementation strategies grounded in real platform architecture. It runs three phases: **create** (fetch the RFE and produce a strategy stub), **refine** (enrich it with technical approach, dependencies, and NFRs), and **review** (score it on feasibility, testability, scope, and architecture). Strategies that pass review are ready for team planning. Strategies that don't pass land here, with you.

The quality of the pipeline's output depends directly on the quality of its inputs. The single most important input is the **architecture and design context** maintained in `opendatahub-io/architecture-context`. This is the brain of the system, it's what the pipeline uses to check technical feasibility against architecture context, understand component boundaries, integration patterns, dependencies, and platform constraints. When the pipeline produces a strategy with wrong dependencies or misunderstood component interactions, the root cause is almost always that the architecture context is incomplete or outdated.

This means that improving the architecture context is the highest-leverage fix you can make. It doesn't just fix one strategy, it improves every future strategy the pipeline generates. If you find yourself repeatedly correcting the same kind of issue, that's a strong signal that the architecture context needs updating. Please flag these gaps to the architecture context maintainers (James Tanner, Luca Burgazzoli) so the source material stays accurate for everyone. Staff engineers and architects are the ones who know the platform best , your corrections make the whole system smarter.

## When Does This Happen?

The strategy pipeline scores every strategy on four dimensions (Feasibility, Testability, Scope, Architecture), each 0-2. Only strategies that score **6+ total with no zeros** auto-approve. Everything else gets a `strat-creator-needs-attention` label and waits for you.

| Verdict | Trigger | What It Means |
|---------|---------|---------------|
| **REVISE** | total >= 3, at most 1 zero | Fixable quality issues. A dimension or two scored low but the approach is sound |
| **REJECT** | total < 3 or 2+ zeros | Fundamental problems. The strategy won't work as written |

## What You'll See

> **Note:** Jira integration is not yet active. The pipeline currently runs in dry-run mode, so Jira labels and comments described below are planned but not yet applied. For now, use the [strat-creator dashboard](https://strat-dashboard-0f1209.gitlab.io/) to browse strategies, scores, and review details.

Once Jira integration is live, you will see:

1. A **Jira comment** on the RHAISTRAT ticket with the score table and a summary of issues
2. The `strat-creator-needs-attention` label on the ticket
3. A **review file** in `artifacts/strat-reviews/STRAT-NNN-review.md` with detailed prose from 4 independent reviewers (feasibility, testability, scope, architecture)

Read the review file first. It tells you exactly what each AI reviewer found.

## The Golden Rule

**Never edit the strategy text directly.** The strategy text (under `## Strategy`) is AI-generated output. If you edit it, the next refine run will overwrite your changes.

Instead, you have two inputs that feed into strategy refinement:

1. **Staff Engineer Input section**, in the strategy file itself, under `## Staff Engineer Input`
2. **Architecture context**, the platform architecture docs in opendatahub-io/architecture-context

Edit the inputs, rerun the pipeline, and let it regenerate the output.

## How to Fix a Strategy

### Local Setup

#### Prerequisites

1. Install [Claude Code](https://docs.anthropic.com/en/docs/claude-code) if you don't have it yet.

2. Set the required environment variables:

```bash
# Jira credentials (required, the pipeline fetches RFEs from Jira)
export JIRA_SERVER="https://redhat.atlassian.net"
export JIRA_USER="your-email@redhat.com"
export JIRA_TOKEN="your-atlassian-api-token"

# Anthropic API key (required, powers the AI pipeline)
export ANTHROPIC_API_KEY="sk-ant-your-key"
```

To generate a Jira API token, go to https://id.atlassian.com/manage-profile/security/api-tokens.

3. Clone the strat-creator repo (you only need to do this once):

```bash
git clone https://github.com/ederign/strat-creator.git
cd strat-creator
```

#### Generate Artifacts Locally

Run the full pipeline in dry-run mode for the RFE you want to work on. Dry-run is safe, it reads from Jira but never writes back:

```bash
# Replace RHAIRFE-1146 with the RFE ID for your strategy
claude -p "/strategy.create RHAIRFE-1397 --dry-run"
claude -p "/strategy.refine --dry-run"
claude -p "/strategy.review --dry-run"
```

To see real-time progress, run interactively instead (drop the `-p` flag):

```bash
claude "/strategy.create RHAIRFE-1397 --dry-run"
```

After the run completes, you'll have:
- Strategy files in `artifacts/strat-tasks/`
- Review files in `artifacts/strat-reviews/`
- An HTML report in `artifacts/reports/report.html`

### Step 1: Read the Review

Browse the review in our [dashboard](https://strat-dashboard-0f1209.gitlab.io/), or open `artifacts/strat-reviews/STRAT-NNN-review.md` locally. Look at:
- The **score table**: which dimensions failed?
- The **prose reviews**: what specifically did each reviewer flag?
- The **disagreements section**: where did reviewers diverge?

> **Note on scoring drift:** LLM-based grading is non-deterministic. Scores may vary slightly between runs, even with the same input. Use scores as directional signals, not exact measurements. If a score seems borderline or surprising, focus on the prose reviews. They explain the reasoning behind the score.

### Step 2: Choose Your Fix Path

| Path | When to Use | What to Edit | What to Rerun |
|------|------------|-------------|---------------|
| **A: Add an overlay** (recommended) | The reviewer found wrong dependencies, outdated platform info, version mismatches, or component gaps that affect multiple strategies | `overlays/` directory in opendatahub-io/architecture-context | refine → review |
| **B: Strategy-specific fix** | The issue is specific to this one strategy (wrong effort estimate, missing test criteria, scope needs narrowing) | `## Staff Engineer Input` section in the strategy file | refine → review |
| **C: Update architecture context directly** | Major structural changes to component docs (ownership, boundaries, integration patterns) | Architecture context repo (opendatahub-io/architecture-context) | refine → review |
| **D: Combination** | Architecture gaps AND strategy-specific issues | Overlays or architecture context AND Staff Engineer Input | refine → review |

**Path A (overlays) is the recommended default.** Overlays are fast to create, easy to test locally, and apply across all matching strategies. They are the right tool for version bumps, maturity changes, dependency shifts, and factual corrections. The process for updating the generated architecture docs directly is being defined by James Tanner, Kevin Bader, and Luca Burgazzoli — until that process is finalized, use overlays.

Use Path B only when the issue is truly unique to one strategy (e.g., a specific effort estimate or a scope decision that doesn't generalize).

Use Path C only for major structural changes that overlays can't express (e.g., adding a new component, restructuring component boundaries).

**All paths require rerunning refine then review.** Refine regenerates the strategy text using your inputs. Review re-scores the regenerated output.

### Step 3: Write Your Input

#### Path A: Add an Overlay (Recommended)

Overlays are architecture updates that apply across all matching strategies. They are the fastest way to correct version mismatches, maturity changes, dependency shifts, and other factual gaps in the architecture context.

##### How to Create an Overlay

1. Clone or navigate to the architecture-context repo:

```bash
git clone git@github.com:opendatahub-io/architecture-context.git
cd architecture-context
```

2. Find the next available ID by checking existing overlays:

```bash
ls overlays/*.md | sort
```

3. Create a new overlay file using the naming convention `NNNN-short-kebab-description.md`:

```bash
cat > overlays/0002-your-overlay-name.md << 'OVERLAY'
---
id: "0002"
title: Short description of what changed
status: active
created: 2026-04-20
affects:
  - component-name-1
  - component-name-2
release:
  - "3.5"
provenance:
  - https://github.com/opendatahub-io/some-repo/pull/123
author: Your Name
superseded_by: null
---

## Fact

What changed, in 1-3 sentences. Include the specific version, PR, or decision.

## Impact on Strategies

- How this affects strategies (be specific: "use X, not Y")
- What strategies should reference instead

## Context

Why this overlay exists — typically the generated architecture docs
reference an older state because a newer branch hasn't been analyzed yet.
OVERLAY
```

Key fields:
- `affects`: component names matching files in `architecture/*.md` (e.g., `data-science-pipelines`, `notebooks`). Use `platform` for platform-wide facts.
- `release`: which RHOAI releases this applies to. Use `["all"]` for timeless facts.
- `provenance`: links to the PRs, issues, or decisions that establish this fact.

##### How to Test an Overlay Locally

Before pushing upstream, test that the overlay is picked up correctly by the pipeline:

```bash
# From the strat-creator directory, point at your local architecture-context
claude -p "/strategy.refine --dry-run --architecture-context /path/to/your/architecture-context"
claude -p "/strategy.review --dry-run --architecture-context /path/to/your/architecture-context"
```

The pipeline will print which overlays were applied. Verify your overlay appears in the list and that the refined strategy reflects the updated facts.

##### How to Submit an Overlay

Once tested, commit and open a PR against the upstream repo:

```bash
cd architecture-context
git checkout -b overlay-your-description
git add overlays/NNNN-your-overlay-name.md
git commit -m "Add overlay: short description"
git push -u origin overlay-your-description
gh pr create --repo opendatahub-io/architecture-context
```

After the PR is merged, the pipeline will automatically pick up the overlay on the next run (no `--architecture-context` flag needed).

##### When to Mark an Overlay as Superseded

When the architecture context is regenerated and includes the fact from an overlay, update the overlay:

```yaml
status: superseded
superseded_by: "architecture context regenerated for rhoai-3.5"
```

The pipeline ignores superseded overlays. The file stays in the repo for audit trail.

#### Path B: Strategy-Specific Fix

Open the strategy file (`artifacts/strat-tasks/STRAT-NNN.md`) and find the `## Staff Engineer Input` section. Add your guidance there. Examples:

**For a REVISE (testability gap):**
```markdown
## Staff Engineer Input

The acceptance criteria need to include API response time benchmarks.
Target: p95 < 200ms for the model registry lookup endpoint.
Edge case the reviewer missed: handle the case where the registry
returns a 404 for a model that was soft-deleted.
```

**For a REVISE (effort estimate):**
```markdown
## Staff Engineer Input

Effort estimate is too low. This touches the inference controller
and the model registry, two teams need to coordinate. Estimate
should be M not S. Add a dependency on RHAISTRAT-1200 which is
refactoring the registry API.
```

**For a scope issue:**
```markdown
## Staff Engineer Input

Scope is too broad. Tighten to model registry API for version
management only. Dashboard UI for model version comparison should
be a separate RFE.
```

> **Important:** If you edited the `## Staff Engineer Input` section during this dry-run stage, send the updated markdown file to Eder so he can include it in the production run on Jira.

#### Path C: Update Architecture Context Directly

For major structural changes that overlays can't express (adding a new component, restructuring component boundaries, rewriting integration patterns), update the generated docs in opendatahub-io/architecture-context directly.

> **Note:** The process for updating architecture context docs is being defined by James Tanner, Kevin Bader, and Luca Burgazzoli. Contact them for instructions. Until that process is finalized, prefer overlays (Path A) for most corrections.

After updating the architecture context, rerun `/strategy.refine`. It will fetch the updated context and regenerate the strategy accordingly.

### Step 4: Rerun the Pipeline

From your local `strat-creator` directory (see [Local Setup](#local-setup)), rerun refine and review:

```bash
claude -p "/strategy.refine --dry-run"
claude -p "/strategy.review --dry-run"
```

In CI, this happens automatically on the next pipeline run after you remove the `strat-creator-needs-attention` label.

### Step 5: Check the Result

Look at the new review file. Did the scores improve? If the strategy now scores 6+ with no zeros, it auto-approves.

If it still doesn't pass, repeat from Step 1. The cycle continues until the strategy approves.

## What Each Verdict Typically Needs

### REVISE

Most common. Usually one or two dimensions scored low. Typical fixes:

| Low Dimension | Common Fix |
|--------------|-----------|
| **Feasibility** | Add risk mitigation, clarify technical approach, adjust effort estimate |
| **Testability** | Add measurable acceptance criteria, specify edge cases, define test matrix |
| **Scope** | Tighten boundaries, remove bundled concerns, clarify what's out of scope |
| **Architecture** | Correct component dependencies, specify integration patterns, align with platform direction |

### REJECT

Rare but serious. Two or more dimensions have fundamental problems. Options:
- Go back to the source RFE, maybe the RFE itself needs rework
- Write extensive Staff Engineer Input to redirect the strategy approach entirely
- Flag to the team that this feature needs a design discussion before pipeline re-entry

## Pipeline Flow Diagram

See the **Pipeline tab** in the [strat-creator dashboard](https://strat-dashboard-0f1209.gitlab.io/) for the full pipeline diagram including the human review loop.

## Key Rules

1. **Never edit strategy text directly.** Edit the inputs (architecture context or Staff Engineer Input), not the output
2. **Prefer architecture context fixes.** They're durable and benefit all future strategies, not just the one you're fixing
3. **Always rerun refine before review.** Review scores what refine produces, not what you wrote
4. **`strat-creator-needs-attention` is one-way.** Only humans remove it, automation never clears it
5. **Use Staff Engineer Input for one-off fixes.** Effort estimates, scope decisions, and other things that don't generalize

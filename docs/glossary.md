# Concepts & Glossary

Key terms used throughout the strat-creator documentation.

## Pipeline Concepts

**RFE (Request for Enhancement)**
: A business need submitted to the RHAIRFE Jira project. Describes the WHAT and WHY but not the HOW. Created by the rfe-creator pipeline or manually.

**Strategy**
: An implementation plan in the RHAISTRAT Jira project. Adds the HOW to an RFE: technical approach, dependencies, impacted teams, non-functional requirements.

**Cloners link**
: A Jira issue link type that connects a RHAISTRAT strategy to its source RHAIRFE. Used to trace provenance and prevent duplicate processing.

**Architecture context**
: Component documentation from [opendatahub-io/architecture-context](https://github.com/opendatahub-io/architecture-context). Provides real platform architecture data (component boundaries, dependencies, API surfaces) that the refinement stage uses to ground strategies in reality.

**Overlays**
: Cross-strategy architectural patches that live in the `overlays/` directory of the architecture-context repo. They capture facts that emerged between architecture context regeneration cycles (version bumps, maturity changes, dependency shifts). Preferred fix path because they benefit all future strategies.

## Scoring & Review

**Scorer agent (strat-scorer)**
: A restricted Claude agent (read/write/glob/grep only) that produces numeric scores against the quality rubric. Runs as part of the strategy-review stage.

**Prose reviewer**
: An independent Claude skill that produces narrative feedback on one dimension (feasibility, testability, scope, architecture, or security). Five prose reviewers run in parallel during strategy-review.

**Rubric-pass**
: CI verdict meaning the strategy scored 6+ out of 8 with no zero scores. Ready for human review and sign-off. Labeled `strat-creator-rubric-pass`.

**Needs-attention**
: CI verdict meaning the strategy scored below the pass threshold or had zero scores. Needs human intervention before it can be signed off. Labeled `strat-creator-needs-attention`.

## Artifacts & Files

**Frontmatter**
: YAML metadata block at the top of strategy and review files (between `---` markers). Contains structured data like scores, labels, status, and workflow state.

**Staff Engineer / SME Input**
: A section in strategy files where human reviewers add corrections, context, and guidance. This input is consumed by `/strategy-refine` when regenerating the strategy. One-off fixes go here; systemic fixes should be overlays instead.

## Pipeline Operations

**Dry-run mode**
: The `--dry-run` flag available on create, refine, and review skills. Skips all Jira writes while still producing local artifacts. Used for testing changes locally without affecting Jira.

**Concurrency lock (strat-creator-processing)**
: A Jira label applied by `scripts/lock_issues.py` to prevent two pipeline jobs from processing the same RFE simultaneously. Automatically removed when processing completes. If a pipeline job crashes, the label may need manual removal.

**Pre-filter**
: The second stage of RFE discovery that removes RFEs already having processed strategies (via Cloners links). Prevents wasting batch slots on RFEs that already have rubric-pass or needs-attention strategies.

**Batch**
: A set of RFEs processed in a single pipeline run. Controlled by `batch_size` in `config/pipeline-settings.yaml` (default: 10). Can also be defined manually via YAML batch files.

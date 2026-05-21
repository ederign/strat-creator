# Strategy Review

> **Owner:** strat-creator CI pipeline
> **Last verified:** 2026-05-21

## What Happens

The `strategy-review` skill orchestrates a two-phase review: numeric scoring followed by prose reviews from independent reviewers.

```mermaid
flowchart TD
    A["Refined strategy"] --> B["Bootstrap\nassess-strat"]
    B --> C["Scorer agent\n(numeric scores)"]
    C --> D["Parse scores &\napply verdicts"]
    D --> E["5 Prose reviewers\n(parallel)"]
    E --> F["Write review file"]
    F --> G["Apply Jira labels"]

    E --- E1["Feasibility"]
    E --- E2["Testability"]
    E --- E3["Scope"]
    E --- E4["Architecture"]
    E --- E5["Security"]
```

## Scoring Pipeline Detail

```mermaid
flowchart TD
    A["Refined Strategy"] --> B["Bootstrap assess-strat\nfrom GitHub"]
    B --> C["Export rubric to\nartifacts/strat-rubric.md"]
    C --> D["Spawn strat-scorer agent\n(restricted: Read/Write/Glob/Grep)"]
    D --> E["Score against 4 dimensions"]
    E --> F["parse_results.py\n(deterministic)"]
    F --> G["apply_scores.py\n(update frontmatter)"]
    G --> H{Total >= 6\nno zeros?}
    H -->|Yes| I["APPROVE\nrubric-pass"]
    H -->|No| J{Total >= 3\n≤1 zero?}
    J -->|Yes| K["REVISE\nneeds-attention"]
    J -->|No| L["REJECT\nneeds-attention"]

    I --> M["5 Prose Reviews\n(parallel skills)"]
    K --> M
    L --> M

    M --> M1["Feasibility"]
    M --> M2["Testability"]
    M --> M3["Scope"]
    M --> M4["Architecture"]
    M --> M5["Security\n(prose-only)"]

    M1 --> N["Merge prose into\nreview file"]
    M2 --> N
    M3 --> N
    M4 --> N
    M5 --> N

    N --> O["Post to Jira\n(comment + attachment)"]

    style I fill:#c8e6c9,stroke:#2e7d32
    style K fill:#fff9c4,stroke:#f9a825
    style L fill:#ffcdd2,stroke:#c62828
    style M5 fill:#e1f5fe,stroke:#0277bd
```

### Phase 1: Numeric Scoring

A restricted scorer agent (`strat-scorer`) evaluates the strategy against 4 dimensions:

| Dimension | What It Checks | Score Range |
|-----------|---------------|-------------|
| **Feasibility** | Can we build this with the proposed approach? | 0-2 |
| **Testability** | Are acceptance criteria measurable? | 0-2 |
| **Scope** | Is this right-sized? Does effort match scope? | 0-2 |
| **Architecture** | Do dependencies and integrations check out? | 0-2 |

**Maximum total: 8**

Scores are parsed and verdicts computed deterministically by `parse_results.py` and `apply_scores.py`. No LLM judgment is involved in verdict assignment.

### Verdicts

| Verdict | Condition | Label Applied |
|---------|-----------|---------------|
| **APPROVE** | Total >= 6, no zeros | `strat-creator-rubric-pass` |
| **REVISE** | Total >= 3, at most 1 zero | `strat-creator-needs-attention` |
| **REJECT** | Total < 3 or 2+ zeros | `strat-creator-needs-attention` |

### Phase 2: Prose Reviews

After scoring, 5 independent prose reviewers run in parallel. Each produces narrative feedback on its dimension:

| Reviewer | Focus |
|----------|-------|
| **Feasibility** | Technical viability, implementation complexity, effort credibility |
| **Testability** | Acceptance criteria measurability, edge cases, test strategy |
| **Scope** | Right-sizing, effort/scope matching, RFE coverage |
| **Architecture** | Dependencies, integration patterns, component interactions |
| **Security** | Auth, data protection, cryptographic compliance, supply chain, agent/MCP risks |

!!! note
    The security reviewer is **prose-only**. It does not contribute to the numeric score. It provides narrative feedback on security posture but does not affect the APPROVE/REVISE/REJECT verdict.

Prose reviewers set their own individual verdicts (`reviewers.feasibility`, etc.) for informational purposes, but these do NOT affect the gate decision. The gate is purely numeric.

### Disagreements Are Preserved

If the feasibility reviewer says "this is fine" but the scope reviewer says "this is too big," both views are reported. Reviewers never see each other's output.

## What Triggers This Stage

- A refined strategy from [Strategy Refinement](strategy-refinement.md)

## What It Produces

- `artifacts/strat-reviews/RHAISTRAT-NNNN-review.md`: Review file with scores table and prose from all reviewers
- Jira label: `strat-creator-rubric-pass` or `strat-creator-needs-attention`
- Jira comment: Summary of scores and verdict
- Jira attachment: Full review file

## Next Stage

[Human Review & Sign-off](human-review-signoff.md): A staff engineer reviews the scored strategy and signs off.

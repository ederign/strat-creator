# Scoring & Rubric

How strategies are scored and what the verdicts mean.

## Dimensions

Each strategy is scored on 4 dimensions by the `strat-scorer` agent:

| Dimension | Score | Criteria |
|-----------|-------|----------|
| **Feasibility** | 0-2 | Can we build this with the proposed approach? Are effort estimates credible? |
| **Testability** | 0-2 | Are acceptance criteria measurable? Are edge cases covered? Is there a test strategy? |
| **Scope** | 0-2 | Is this right-sized? Does effort match scope? Does it fully cover the RFE? |
| **Architecture** | 0-2 | Do dependencies check out? Are integration patterns correct? Does it align with platform architecture? |

**Maximum total: 8**

### Score Meanings

| Score | Meaning |
|-------|---------|
| **0** | Fundamental problem. Missing, wrong, or contradictory. |
| **1** | Partial. Some issues but salvageable. |
| **2** | Solid. Meets expectations for this dimension. |

## Verdicts

Verdicts are computed deterministically by `parse_results.py`. No LLM judgment is involved.

| Verdict | Condition | Label | Meaning |
|---------|-----------|-------|---------|
| **APPROVE** | Total >= 6 AND no zeros | `strat-creator-rubric-pass` | Ready for human sign-off |
| **REVISE** | Total >= 3 AND at most 1 zero | `strat-creator-needs-attention` | Fixable issues |
| **REJECT** | Total < 3 OR 2+ zeros | `strat-creator-needs-attention` | Fundamental problems |

Both REVISE and REJECT get the same Jira label (`strat-creator-needs-attention`). The distinction is in the review prose, which tells the staff engineer how severe the issues are.

## Security Review (Prose-Only)

In addition to the 4 scored dimensions, a security reviewer provides narrative feedback on:

- Authentication and authorization
- Data protection and privacy
- Cryptographic compliance
- Network security
- Supply chain risks
- Agent and MCP risks

The security review does **not** produce a numeric score and does **not** affect the APPROVE/REVISE/REJECT verdict. It provides supplementary feedback for human reviewers.

## Rubric Source

The scoring rubric is maintained in the [assess-strat](https://github.com/n1hility/assess-strat) plugin. It's bootstrapped into `.context/assess-strat/` at runtime. To export a local copy:

```bash
claude "/export-rubric"
```

This writes the rubric to `artifacts/strat-rubric.md`.

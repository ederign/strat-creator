# Strategy Quality Rubric

Scored criteria for assessing RHAISTRAT strategy quality. Follows the same pattern as assess-rfe: numeric scores per dimension, deterministic pass/fail thresholds, calibration examples from real pipeline output.

## Criteria

Four dimensions, each scored 0-2. Total: 8 points.

| Dimension | What it measures | 0 | 1 | 2 |
|-----------|-----------------|---|---|---|
| **Feasibility** | Can we build this as described? | Hard blocker with no fallback, or fundamentally infeasible | Technically feasible but missing contingency plans, unresolved design questions, or underspecified critical paths | Feasible with credible effort estimate, identified risks have mitigations, no unresolved blockers |
| **Testability** | Can we verify this works? | Acceptance criteria are aspirational or untestable; no verification protocol | Criteria exist but lack concrete thresholds, test matrix is undefined, or edge cases are missing | All criteria have binary pass/fail verification methods, measurable thresholds, edge cases covered |
| **Scope** | Is it right-sized? | Bundles 3+ independent features, or scope is unbounded | Bundles 1-2 separable features, or effort is underestimated, or scope has minor ambiguity | Focused single deliverable, finite enumerated work items, effort matches scope, clear definition of done |
| **Architecture** | Are integration patterns correct? | Core architectural assumption is wrong, or fundamental component interaction is misunderstood | Dependencies identified but minor gaps, or one unresolved cross-component question | Components correctly identified, integration patterns sound, boundaries respected, no conflicts |

## Pass/Fail Thresholds

Verdicts are **deterministic** — computed from scores, not from reviewer judgment.

```
APPROVE:  total >= 6  AND  no zeros
SPLIT:    scope = 0   AND  all other dimensions >= 1  AND  sum(other dimensions) >= 3
REVISE:   total >= 3  AND  at most one zero  AND  not SPLIT
REJECT:   total < 3   OR   zeros in 2+ dimensions
```

**The "no zeros" rule:** A strategy scoring 2+2+2+0 = 6 does NOT approve. Every dimension is a gate. A fundamentally wrong architecture can't be compensated by excellent scope clarity.

**The split trigger:** Scope = 0 specifically triggers SPLIT (not REVISE) because the fix is decomposition, not revision. The other dimensions must be adequate (all >= 1) — don't split a strategy with fundamental feasibility problems.

## Calibration Examples

All examples are from real pipeline output (strat-pipeline-data/RHAISTRAT/current/).

---

### Feasibility

#### F=2: STRAT-1469 (Llama Stack Distribution Cleanup)

> Effort S is credible for what is essentially a config.yaml edit, Containerfile cleanup, doc update, and test update.

**Why 2:** No external blockers. The strategy describes removing four inline providers from `config.yaml` and letting the build system drop transitive dependencies. The work is bounded, the effort estimate is credible, and breaking change risk is mitigated by EA status. One deliverable, one team, no design questions.

**What to look for:**
- Effort estimate matches the actual work described
- No unresolved "open questions" on the critical path
- External dependencies (if any) have known status and fallback plans
- Risk mitigations are specific, not vague

#### F=1: STRAT-1432 (Structured Output Enforcement)

> The entire Phase 1 depends on xgrammar `structural_tag` (RFC #32142), which is listed as 'in progress' with unknown merge date. The strategy acknowledges this blocks Phase 1 'entirely' but offers only weak mitigation ('track RFC closely; participate in upstream review; evaluate alternative approaches').

**Why 1, not 0:** The technical approach is sound — grammar-based enforcement during tool call generation is the right architecture. But the critical path dependency has no fallback. A strategy that says "track closely" for a hard blocker is not a contingency plan.

**Also contributing to 1:**
- Parser trigger token detection is underspecified (how does it work at the token level?)
- Multi-tool call grammar transitions are acknowledged but undesigned
- Streaming enforcement is treated as a testing concern, not an architecture concern

**The fix that would make it a 2:** Add a Phase 0 that delivers value without `structural_tag` (e.g., `tool_choice="required"` enforcement only), and define concrete trigger detection logic for at least the two most common parser formats.

#### F=0: STRAT-1547 (External Model Registration) — Architecture sub-dimension

> The ExternalModel handler is a stub — the strategy underestimates backend work. [...] Request/response translation is a critical unresolved question, not an open question. [...] The RFE acceptance criteria lists 'MVP providers - OpenAI, Anthropic, Bedrock' — at least two of three MVP providers require request translation. The strategy cannot defer this question.

**Why 0:** The strategy sizes the work as M, but the backend alone is an M and the UI is another M. Two of three MVP providers need request translation that isn't described, sized, or assigned. The hard blocker (RHAISTRAT-1295) has unknown status. When the core scope is unknowable because a fundamental design question is deferred, feasibility is 0.

**What pushes F from 1 to 0:**
- The strategy cannot be sized because a fundamental question is unresolved
- Multiple MVP scope items require work that isn't described
- Hard blocker status is unknown (not just "in progress" — unknown)

---

### Testability

#### T=2: STRAT-1469 (Llama Stack Distribution Cleanup)

> All acceptance criteria are directly testable with concrete verification steps. Each inline provider removal (AC1-4) can be verified by: (a) confirming the provider is absent from `config.yaml`, (b) confirming the corresponding Python dependencies are absent from the built image (`pip list` or `pip show` returning not-found for torch, transformers, faiss-cpu, pymilvus-lite), (c) confirming the provider cannot be instantiated at runtime. These are binary pass/fail checks.

**Why 2:** Every acceptance criterion maps to a concrete, automatable verification step. Image size reduction has a measurable target (2-4 GB). The tests are binary (provider present or absent, dependency installed or not). No subjective judgment needed.

**What to look for:**
- Each criterion has a concrete verification method (not just "works correctly")
- Thresholds are numeric where applicable (size reduction, latency, error rates)
- Edge cases are identified (upgrade path from EA users who used inline providers)
- Tests are binary pass/fail, not subjective assessment

#### T=1: STRAT-1625 (Resource Badges)

> The 'Updated' badge derivation is the weakest testability point. The strategy says 'Updated' applies when an OdhDocument's content changed in the current release but existed in a prior release. The feasibility review flagged that the dashboard has no prior-version state available client-side.

**Why 1, not 2:** Two of three badge types (New, Recommended) have clear verification methods. But the "Updated" badge derivation logic is undefined — the test can't be written until the exact logic is defined. One unclear criterion out of three keeps this from a 2.

**Why 1, not 0:** Most criteria are testable. The gap is narrow (one badge type's derivation logic) and fixable (commit to a specific derivation rule).

#### T=0: STRAT-1432 (Structured Output Enforcement)

> Acceptance criteria 1 ('produces only well-formed, schema-conformant tool calls') is testable in principle but lacks a verification protocol. How do you prove a negative — that malformed tool calls are 'impossible'?

**Why 0:** The primary acceptance criterion asks for proof of a negative ("impossible" to produce malformed calls). No finite test suite can prove this. The test matrix is undefined (which parsers? which models? which schema complexity levels?). Multi-tool call testing is entirely absent despite being the primary production use case. The strategy's own open questions reveal that the acceptance criteria can't be tested until design questions are resolved.

**What pushes T from 1 to 0:**
- Primary criterion is provably untestable as written
- No test matrix defined (parsers x models x modes x streaming)
- Primary use case (parallel tool calls) absent from criteria entirely
- Multiple criteria depend on unresolved design decisions

---

### Scope

#### S=2: STRAT-1469 (Llama Stack Distribution Cleanup)

> The scope is explicitly bounded. The strategy names exactly four providers to remove (inline::milvus, inline::localfs, inline::sentence-transformers, inline::faiss). It does not use phrases like 'and related functionality' or 'all inline providers.' The scope is a closed set.

**Why 2:** Finite, enumerated deliverables. No open-ended phrases. Clear definition of done ("image contains only remote providers"). One team, one component. Effort S credibly matches the work. The strategy delivers a complete capability — no follow-on work needed to realize value.

**What to look for:**
- Deliverables are enumerated (a finite list, not "and related")
- Clear before/after state ("done" is unambiguous)
- Effort estimate matches the work described
- Single team, bounded component set
- No scope expansion risk ("stretch goals", "and more")

#### S=1: STRAT-1432 (Structured Output Enforcement)

> Effort L is underestimated given the actual scope. [...] One scope risk: multi-tool call handling. The strategy leaves parallel tool calling as an open question. In production, parallel tool calls are common for agentic workflows (the RFE's primary use case).

**Why 1, not 2:** The scope is bounded by two phases, but the effort is underestimated. Multi-tool call handling is left as an "open question" but is actually the primary use case. The two-phase approach doubles the test matrix without sizing it.

**Why 1, not 0:** The work is still a single coherent capability (structured output enforcement). It doesn't bundle independent features — phases 1 and 2 are sequential stages of the same feature. The scope is underestimated but not unbounded.

#### S=0: STRAT-1479 (MLflow Integration)

> This is three features bundled as one. [...] Feature A: MLflow logging in KFP pipeline components (data-science-pipelines team). Feature B: Eval Hub MLflow run context passthrough (Responsible AI team). Feature C: Model Registry <-> MLflow bidirectional lineage (Data Science Pipelines + MLflow teams). Each of these is independently valuable and independently deliverable.

**Why 0:** Three independent features bundled. Each has different component owners, different design challenges, and different dependencies. They're independently valuable — Feature A gives pipeline observability without Feature C's lineage. Six components across five teams. The phrase "end-to-end lineage" spanning four systems is a scope trap that invites unbounded creep.

**The split test:** Can each piece ship independently and deliver value? If yes, and there are 3+ such pieces, scope = 0.

**What pushes S from 1 to 0:**
- 3+ independently valuable features bundled
- Different teams own different features
- "End-to-end" or "comprehensive" scope descriptors without bounds
- All-or-nothing delivery risk (features forced to ship together)

---

### Architecture

#### A=2: STRAT-1469 (Llama Stack Distribution Cleanup)

> Dependencies are correctly identified. The strategy lists llama-stack-distribution and llama-stack-k8s-operator as affected components. [...] Removing inline providers from `config.yaml` is the architecturally correct approach — the build system resolves dependencies from the active provider list, so removing providers drops their transitive dependencies. No other RHOAI components depend on the inline providers being present.

**Why 2:** Components correctly identified. Integration pattern (config-driven build) is correct per architecture docs. No cross-component conflicts. The strategy aligns with the platform's architecture pattern of using remote backends rather than bundling ML frameworks.

**What to look for:**
- Component list matches architecture docs
- Integration patterns use existing APIs/CRDs correctly
- No conflicts with other strategies or platform direction
- Cross-component coordination needs identified (or confirmed unnecessary)
- Deployment model is sound

#### A=1: STRAT-1625 (Resource Badges)

> Integration patterns are correct. The strategy proposes a purely client-side computation with no new API calls or backend changes. [...] The dashboard's existing ClusterRole already has `get, list` permissions on `dashboard.opendatahub.io/odhdocuments`.

**Why 1, not 2:** The architecture is correct — all data is available client-side, no new APIs needed, RBAC already exists. The only gap: the strategy doesn't confirm that OdhDocument CRD actually includes a `version` field (it mentions `lastUpdated` as an alternative without committing). This is minor but leaves one architectural question open.

**Why 1, not 0:** The core integration pattern is sound. The gap is a single field name confirmation, not a fundamental misunderstanding of component interaction.

#### A=0: STRAT-1547 (External Model Registration)

> HTTPRoute cannot directly proxy to external endpoints — the strategy's core traffic routing assumption is incorrect. [...] The MaaS gateway accepts HTTPRoutes that reference internal Services. An external endpoint like `api.openai.com` is not a Kubernetes Service.

**Why 0:** The core architectural assumption is wrong. The strategy says the controller creates "an HTTPRoute to proxy requests to the external provider endpoint." But HTTPRoutes route to Kubernetes Services, not external URLs. The MaaS gateway was designed for ingress, not egress proxying. Additionally, rate limiting depends on response body parsing that differs per provider (OpenAI: `usage.prompt_tokens`, Anthropic: `input_tokens`).

**What pushes A from 1 to 0:**
- A core assumption about how a component works is factually wrong
- The error isn't a gap (something missing) — it's a misunderstanding (something wrong)
- Fixing it changes the architecture fundamentally (need ServiceEntry or proxy pod)
- Multiple downstream decisions depend on the wrong assumption

---

## Scoring Summary: Real Strategies

| Strategy | F | T | S | A | Total | Verdict |
|----------|---|---|---|---|-------|---------|
| STRAT-1469 (Llama Stack cleanup) | 2 | 2 | 2 | 2 | 8 | APPROVE |
| STRAT-1625 (Resource badges) | 2 | 1 | 2 | 1 | 6 | APPROVE |
| STRAT-1432 (Structured output) | 1 | 0 | 1 | 1 | 3 | REVISE |
| STRAT-1479 (MLflow integration) | 1 | 1 | 0 | 1 | 3 | SPLIT |
| STRAT-1547 (External models) | 0 | 1 | 1 | 0 | 2 | REJECT |

Note: STRAT-1547 scored 0 in both Feasibility and Architecture (2 zeros) — this triggers REJECT, not REVISE. The original pipeline verdict was "revise" because reviewers lacked numeric thresholds. With the rubric, two fundamental problems (infeasible scope + wrong architecture) correctly maps to REJECT.

## How Reviewers Use This Rubric

Each reviewer reads this rubric and scores their dimension 0-2 with justification. The orchestrator collects the four scores, computes the total, and applies the threshold deterministically.

**Reviewer output format:**

```markdown
## [Dimension] Assessment

**Score: N/2**

**Justification:**
[Evidence-based reasoning referencing specific strategy content]

**Key concerns:**
- [Specific issue 1]
- [Specific issue 2]

**What would raise the score:**
- [Specific fix 1]
- [Specific fix 2]
```

The orchestrator computes the verdict. Reviewers never say "approve" or "revise" — they score 0-2 and explain why.

## Edge Cases

**Disagreement between reviewers and scores:** If a reviewer writes "this is fine" but scores it 1/2, the score governs. Prose can be optimistic; numbers can't.

**Score-verdict mismatch with prior system:** Some strategies that previously received "revise" may now receive "reject" (like STRAT-1547 with two zeros). This is intentional — the prior system was more lenient because the quality bar was implicit.

**Split vs. Reject:** A strategy with scope=0 but feasibility=0 gets REJECT, not SPLIT. Don't decompose a strategy that has fundamental problems — fix the problems first.

**Near-miss detection:** Strategies scoring 5/8 with no zeros are one point from approval. These are high-value revision targets — small improvements yield approval.

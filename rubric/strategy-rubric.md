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

**Needs attention:** Only APPROVE passes the gate automatically. REVISE, SPLIT, and REJECT all require human review.

| Verdict | Needs Attention | What it means |
|---------|-----------------|---------------|
| APPROVE | false | Auto-approved, done |
| REVISE  | true  | Fixable quality issues — human reviews and fixes |
| SPLIT   | true  | Scope problem — human decides decomposition |
| REJECT  | true  | Fundamental problems across multiple dimensions |

## Calibration Examples

All examples are from real RHOAI 3.4 Feature Refinement documents unless noted otherwise. Strategy IDs reference Jira items for traceability.

---

### Feasibility

#### F=2: RHAISTRAT-1161 (MLflow GA Integration in RHOAI)

GA promotion of existing Tech Preview — the work is bounded and precedented, not greenfield design. The support scope table enumerates 20+ MLflow sub-features with explicit In Scope/SDK/No designations, making the effort estimate verifiable. Risks are specific with mitigations: Z architecture support has a concrete fallback ("unless we get IBM support for Z builds"), and the upstream bug dependency (#21516) is tracked. No unresolved blockers on the critical path.

**What to look for:**
- Effort estimate matches the actual work described
- No unresolved "open questions" on the critical path
- External dependencies (if any) have known status and fallback plans
- Risk mitigations are specific, not vague ("track closely" is not a mitigation)
- Risks section is populated. An empty Risks section for a multi-team or L/XL strategy indicates unknowns haven't been surfaced, not that none exist. Each risk should have a concrete mitigation.

#### F=1: RHAISTRAT-1201 (API Key Management for MaaS)

Technical approach is sound — opaque keys, hash-only storage, Authorino gateway integration. But the Risks & Assumptions section is empty for a feature replacing the production authentication model. GA is conditional on an unresolved Jira blocker (RHOAIENG-51950) that the strategy never explains. Pluggable storage backend is hand-waved as "future support" with no design sketch. The approach is credible; the risk analysis is absent.

**Also contributing to 1:**
- Hard blocker status is unknown, not just "in progress"
- Pluggable storage mentioned without design sketch
- Risk analysis absent for a security-critical feature

**The fix that would make it a 2:** Populate the Risks section with specific risks and mitigations, resolve the Jira blocker status, and sketch the storage backend approach.

#### F=0: RHAISTRAT-1172 (RHAII UI — Inference Service SKU)

Status is "Not started." No effort estimate exists. The feature requires a UI that "functions consistently across certified 3rd party Kubernetes engines" (AKS, EKS, OpenShift) — a massive cross-platform undertaking — with zero implementation planning. It depends on at least 3 other undelivered RHAISTRAT features. Prerequisite sections are unanswered template placeholders. This is a vision document, not a strategy — fundamental design questions aren't deferred, they haven't been asked yet.

**What pushes F from 1 to 0:**
- The strategy cannot be sized because fundamental design questions are deferred
- Multiple MVP scope items require work that isn't described
- Hard blocker status is unknown

---

### Testability

#### T=2: RHAISTRAT-1213 (AgentCard Discovery)

Nine acceptance criteria in Given/When/Then format, each binary-verifiable. Criteria cover the happy path (auto-create AgentCard CR with owner reference), failure modes (CRD not installed → 404 fallback to workload-based discovery), security verification (JWS signature → SignatureVerified condition, status.validSignature, label propagation), and cleanup (garbage collection via owner references). Every criterion can be validated by an automated test — no subjective assessment required.

**What to look for:**
- Each criterion has a concrete verification method (not just "works correctly")
- Thresholds are numeric where applicable (size reduction, latency, error rates)
- Edge cases are identified
- Tests are binary pass/fail, not subjective assessment
- Non-functional requirements have numeric thresholds (latency, throughput, error rates). "Good performance" or "scalable" are not testable. Missing NFRs for L/XL strategies is a gap.

#### T=1: RHAISTRAT-1161 (MLflow GA Integration)

Criteria exist and describe real user outcomes — "I can visualize metrics, artifacts and parameters from all the supported sources" — but lack concrete thresholds. Which metrics? What does "all supported sources" mean concretely? No edge cases (MLflow unavailable? artifact storage misconfigured?). The feature's support scope table is excellent documentation that enumerates 20+ sub-features, but none of that precision carries into the acceptance criteria. Good intent, insufficient specification.

**Why 1, not 2:** Good intent but insufficient specification — the test can't be written from the criteria alone.

**Why 1, not 0:** Criteria describe real user outcomes, not aspirational statements. The gap is precision, not relevance.

#### T=0: RHAISTRAT-1208 (llm-d on xKS)

The entire acceptance criteria for a multi-team, multi-cloud, multi-quarter feature is one sentence: "Customers can easily deploy a supported llm-d instance on CKS/AKS and leverage it for our well lit paths." "Easily" is subjective. "Supported" is undefined. The four "well lit paths" (KV Cache, P/D Disaggregation, Expert Parallelism, Scheduling) are listed in requirements but have zero verification criteria. A single vague sentence for an L-sized feature across six teams is not an acceptance criterion — it's a wish.

**What pushes T from 1 to 0:**
- Primary criterion is provably untestable as written
- No test matrix defined for key dimensions
- Primary use case absent from criteria

---

### Scope

#### S=2: RHAISTRAT-1167 (vLLM Support for MaaS)

Focused single deliverable: extend MaaS from llm-d-only to include vLLM. Four enumerated requirements (Create flow, Edit flow, OOTB configs, Existing deployments) — no "and related functionality." Out-of-scope is crisp: no auto-conversion of existing deployments, no customer ServingRuntime conversion. Single team boundary, bounded component set. The strategy knows exactly what it is and isn't.

**What to look for:**
- Deliverables are enumerated (a finite list, not "and related")
- Clear before/after state ("done" is unambiguous)
- Effort estimate matches the work described
- Single team, bounded component set
- No scope expansion risk ("stretch goals", "and more")
- Out-of-scope items are explicitly listed. A feature with no out-of-scope list for L/XL effort is a scope risk signal.

#### S=1: RHAISTRAT-1235 (MaaS Usage Dashboard)

Two separately-tracked Jira features combined into one document: the admin dashboard (RHAISTRAT-1235) and the metric exposure pipeline (RHAISTRAT-730). Each is individually coherent, but bundling creates confusion — acceptance criteria mix two scopes and effort is harder to validate. Tech-preview status provides a natural scope limit that prevents runaway scope. Not unbounded, but not cleanly singular either.

**Why 1, not 2:** Two separable features bundled in one document.

**Why 1, not 0:** Only two features (not 3+), and tech-preview status naturally bounds scope.

#### S=0: RHAISTRAT-1118 (MaaS Admin UI & API Key Management)

The document header itself lists two separate Jira features (RHOAISTRAT-638, RHAISTRAT-173). The body bundles 3+ independently shippable deliverables: Tier CRUD admin UI, API Key management for developers, and YAML/UI toggle for tier configuration. Each could ship alone and deliver value. MVP/Should Have/Nice to Have prioritization spans these separable concerns — confirming they were recognized as distinct but bundled anyway. The split test is unambiguous: three features in a trench coat.

**The split test:** Can each piece ship independently and deliver value? If yes, and there are 3+ such pieces, scope = 0.

**What pushes S from 1 to 0:**
- 3+ independently valuable features bundled
- Different teams own different features
- "End-to-end" or "comprehensive" scope descriptors without bounds
- All-or-nothing delivery risk

---

### Architecture

#### A=2: RHAISTRAT-1213 (AgentCard Discovery)

Standard Kubernetes operator pattern: labeled workloads → controller watches → HTTP fetch → CRD status caching. Three controllers with clear separation of concerns (AgentCardSync creates CRs, AgentCard fetches metadata, NetworkPolicy enforces access). Owner references for garbage collection. SPIRE integration correctly scoped as conditional. RBAC requirements explicitly listed. Every architectural claim follows documented platform patterns.

**What to look for:**
- Component list matches architecture docs
- Integration patterns use existing APIs/CRDs correctly
- No conflicts with other strategies or platform direction
- Cross-component coordination needs identified (or confirmed unnecessary)
- Deployment model is sound

#### A=1: RHAISTRAT-1120 (OIDC Integration for MaaS)

Core integration pattern is sound: external OIDC → Authorino validation → group claim extraction → MaaS entitlement. But a requirement directly contradicts a known constraint — Requirement 4 demands "provider-agnostic" authorization while internal review confirms "groups logic *cannot* be vendor-agnostic, but must instead be vendor-specific." Neither approach is wrong individually, but claiming both creates an unresolved architectural conflict. The pattern is right; a key assumption within it is wrong.

**Why 1, not 2:** One unresolved architectural conflict (vendor-agnostic vs vendor-specific).

**Why 1, not 0:** The core integration pattern is sound. The conflict is within a requirement, not in the fundamental architecture.

<!-- A=0 is from pipeline output (dashboard35 batch). No RHOAI 3.4 refinement doc scored A=0 — architecture errors are rare in practice; gaps (A=1) are far more common. -->
#### A=0: STRAT-1547 (External Model Registration)

> HTTPRoute cannot directly proxy to external endpoints — the strategy's core traffic routing assumption is incorrect. The MaaS gateway accepts HTTPRoutes that reference internal Services. An external endpoint like api.openai.com is not a Kubernetes Service.

Core architectural assumption is factually wrong. HTTPRoutes route to Kubernetes Services, not external URLs. Multiple downstream decisions depend on the wrong assumption.

**What pushes A from 1 to 0:**
- A core assumption about how a component works is factually wrong
- The error isn't a gap (something missing) — it's a misunderstanding (something wrong)
- Fixing it changes the architecture fundamentally (need ServiceEntry or proxy pod)
- Multiple downstream decisions depend on the wrong assumption

---

## Scoring Summary: Real Strategies

Use these to sanity-check your scoring. If your scores diverge significantly, re-examine your reasoning. All scores are from RHOAI 3.4 Feature Refinement documents.

| Strategy | F | T | S | A | Total | Verdict |
|----------|---|---|---|---|-------|---------|
| RHAISTRAT-1213 (AgentCard Discovery) | 2 | 2 | 2 | 2 | 8 | APPROVE |
| RHAISTRAT-1259 (Kagenti Cleanup) | 2 | 2 | 1 | 2 | 7 | APPROVE |
| RHAISTRAT-1161 (MLflow GA) | 2 | 1 | 2 | 2 | 7 | APPROVE |
| RHAISTRAT-1167 (vLLM for MaaS) | 2 | 1 | 2 | 2 | 7 | APPROVE |
| RHAISTRAT-1084 (MCP Catalog) | 1 | 1 | 2 | 2 | 6 | APPROVE |
| RHAISTRAT-1120 (OIDC for MaaS) | 1 | 1 | 2 | 1 | 5 | REVISE |
| RHAISTRAT-1201 (API Key Mgmt) | 1 | 1 | 1 | 1 | 4 | REVISE |
| RHAISTRAT-1208 (llm-d on xKS) | 1 | 0 | 1 | 1 | 3 | REVISE |
| RHAISTRAT-1118 (MaaS Admin UI) | 1 | 1 | 0 | 1 | 3 | SPLIT |
| RHAISTRAT-1204 (GUI AutoML) | 1 | 1 | 0 | 1 | 3 | SPLIT |
| RHAISTRAT-1172 (RHAII UI) | 0 | 0 | 0 | 1 | 1 | REJECT |

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

**Split vs. Reject:** A strategy with scope=0 but feasibility=0 gets REJECT, not SPLIT. Don't decompose a strategy that has fundamental problems — fix the problems first.

**Near-miss detection:** Strategies scoring 5/8 with no zeros are one point from approval. These are high-value revision targets — small improvements yield approval.

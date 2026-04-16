# Dashboard 3.5 Batch Execution Analysis

Date: 2026-04-16
Run ID: 20260416-075457
Pipeline: strat-pipeline (GitLab CI)
Claude Code: v2.1.109 (batch 01), v2.1.110 (batches 02-07)
Model: claude-opus-4-6

## Executive Summary

Dashboard 3.5 processed 69 RFEs across 7 batches, producing 73 strategies. All 7 CI jobs reported "success," but only 4 of 7 batches (01, 02, 06, 07) completed the full create-refine-review cycle with prose reviews. Batches 03, 04, and 05 were killed by SIGTERM (rc=143) during the review stage. The scorers completed for most strategies before the kill (11/12, 9/10, 9/10 respectively), but zero prose reviews were written and no review files were persisted. The pipeline wrapper (`stream-claude.py`) treats rc=143 as success, masking these failures.

Total estimated cost across all 7 batches: ~$124. The review stage accounts for 60-75% of per-batch cost and is the primary bottleneck. Prose reviewers introduced three classes of defect: overwriting immutable score fields, using invalid verdict values ("split"), and generating consolidated prose instead of per-file sections. The report generator (`generate-report.py`) undercounts strategies because it ignores RHAISTRAT-* named files.

**Critical fixes for next run:**
1. Fix rc=143 handling -- SIGTERM is not success
2. Increase CI job timeout or optimize review stage duration
3. Prevent prose reviewers from modifying score/recommendation frontmatter
4. Add "split" as a valid verdict value (or map it to "reject")
5. Fix report generator to count both STRAT-* and RHAISTRAT-* files

## Batch Results

| Batch | RFEs | Strategies | Path A | Path B | Create ($) | Refine ($) | Review ($) | Total ($) | Duration (s) | Review Complete? |
|-------|------|------------|--------|--------|------------|------------|------------|-----------|--------------|------------------|
| 1     | 10   | 11         | 5      | 6      | 2.82       | 3.01       | 16.05      | 21.88     | 2666         | Yes (full prose)  |
| 2     | 10   | 11         | 5      | 6      | 2.41       | 2.70       | 18.36      | 23.47     | 2956         | Yes (full prose)  |
| 3     | 10   | 12         | 5      | 7      | 2.57       | 2.53       | 9.41       | 14.51     | 1427         | No (rc=143 kill)  |
| 4     | 10   | 10         | 3      | 7      | 2.61       | 2.53       | 7.60       | 12.74     | 1463         | No (rc=143 kill)  |
| 5     | 10   | 10         | 2      | 8      | 2.70       | 2.58       | 8.39       | 13.67     | 1495         | No (rc=143 kill)  |
| 6     | 10   | 10         | 0      | 10     | 1.32       | 1.84       | 15.26      | 18.42     | 2749         | Yes (full prose)  |
| 7     | 9    | 9          | 0      | 9      | 2.15       | 1.96       | 15.16      | 19.27     | 3362         | Yes (full prose)  |
| **Total** | **69** | **73** | **20** | **53** | **16.58** | **17.15** | **90.23** | **123.96** | **16,118** | **4/7 complete** |

Notes:
- Batch 01 report generator said "Found 6 strategies, 6 reviews" but spot check showed 11 tasks, 11 reviews.
- Batch 02 report generator said "Found 5 strategies, 5 reviews" but spot check showed 11 tasks, 11 reviews.
- Batch 03 produced 12 strategies from 10 RFEs (RHAIRFE-1131 had 3 STRATs via Cloners links: RHAISTRAT-1235, RHAISTRAT-1314, plus one more).
- The report generator undercounts because it only globs `STRAT-*.md` and misses `RHAISTRAT-*.md` files.

## Pipeline Performance

### Per-Stage Timing

| Stage          | Avg Duration | Avg Cost | % of Total Cost | Notes |
|----------------|--------------|----------|-----------------|-------|
| strategy.create | ~12 min     | $2.37    | 13%             | Dominated by Write tool calls for large RHAISTRAT imports |
| strategy.refine | ~8 min      | $2.44    | 14%             | Consistent across batches; mostly Edit tool calls |
| strategy.review | ~25 min     | $12.89   | 73%             | Highly variable; 4 prose skill forks drive cost |

The review stage is 5x more expensive than create or refine because it launches:
1. 10-12 strat-scorer subagents in parallel (scoring phase)
2. 4 prose review skill forks in parallel (feasibility, testability, scope, architecture)

Each prose reviewer reads all strategy files and writes per-file review sections, resulting in massive context windows (55K-80K tokens per reviewer invocation).

### Token Usage Patterns (per stage, from OTEL)

| Batch | Stage    | Input   | Cache Read | Cache Create | Output  | Total     | Cost ($) |
|-------|----------|---------|------------|--------------|---------|-----------|----------|
| 01    | create   | 22      | 1,365,975  | 208,494      | 33,461  | 1,607,952 | 2.82     |
| 01    | refine   | 86,180  | 1,842,242  | 168,083      | 24,172  | 2,120,677 | 3.01     |
| 01    | review   | 206,885 | 7,043,187  | 1,376,003    | 115,809 | 8,741,884 | 16.05    |
| 02    | create   | 14      | 654,232    | 195,464      | 34,400  | 884,110   | 2.41     |
| 02    | refine   | -       | -          | -            | -       | -         | 2.70     |
| 02    | review   | 212,510 | 9,045,757  | 1,535,567    | 126,925 | 10,920,759| 18.36    |
| 03    | create   | -       | -          | -            | -       | -         | 2.57     |
| 03    | refine   | -       | -          | -            | -       | -         | 2.53     |
| 03    | review*  | 112,784 | 4,478,409  | 797,219      | 65,157  | 5,453,569 | 9.41     |
| 04    | create   | -       | -          | -            | -       | -         | 2.61     |
| 04    | refine   | -       | -          | -            | -       | -         | 2.53     |
| 04    | review*  | 87,513  | 3,461,102  | 650,377      | 54,745  | 4,253,737 | 7.60     |
| 05    | create   | -       | -          | -            | -       | -         | 2.70     |
| 05    | refine   | -       | -          | -            | -       | -         | 2.58     |
| 05    | review*  | 109,929 | 4,339,379  | 673,816      | 58,498  | 5,181,622 | 8.39     |
| 06    | create   | -       | -          | -            | -       | -         | 1.32     |
| 06    | refine   | -       | -          | -            | -       | -         | 1.84     |
| 06    | review   | -       | -          | -            | -       | -         | 15.26    |
| 07    | create   | -       | -          | -            | -       | -         | 2.15     |
| 07    | refine   | -       | -          | -            | -       | -         | 1.96     |
| 07    | review   | -       | -          | -            | -       | -         | 15.16    |

\* Killed mid-review (rc=143). No prose reviews written. Scorers mostly completed before kill.

Cache read rates are high (80-83% where measured), indicating prompt caching is effective. The create stage sees the lowest cache rate (cold start), while refine and review benefit from cached strategy files. Review stages consume 3-5x the total tokens of create or refine due to parallel scorer agents and prose reviewer forks.

### Bottleneck Analysis

1. **Review stage dominates cost and time.** At 73% of total cost, this is the primary optimization target. The four parallel prose reviewers each process all strategies in a single context window, which means review cost scales linearly with strategy count.

2. **Write tool calls are the slowest individual operations.** In the create stage, writing a single RHAISTRAT import file takes 10-90 seconds. Path A imports (which write large files with existing STRAT content) are slower than Path B stubs.

3. **Scorer agent parallelism is effective but creates a tail latency problem.** 11 scorer agents launch in parallel, but the orchestrator must wait for all to complete. The slowest scorer (typically 2-3 min) determines the phase duration.

4. **SIGTERM kills the longest-running batches.** Batches 03, 04, 05 were killed at ~1427-1495s. The kills happened ~3 min into the review stage, suggesting a per-stage or per-claude-invocation timeout rather than a per-job timeout. Full review cycles require 22-36 minutes.

5. **Runner concurrency limits caused serial execution.** Batches 01 and 02 ran on separate runners in parallel, but batches 03-07 queued behind each other on a single runner (batches 03-05 specifically all ran sequentially on runner `HwHQ9C1DY`). This extended total wall-clock time from the ideal ~2h to ~5.5h.

## Scoring and Verdict Distribution

### Aggregate Scoring

**Batches with full reviews (01, 02, 06, 07):**

| Batch | Strategies | APPROVE | REVISE | REJECT | Avg Score |
|-------|------------|---------|--------|--------|-----------|
| 01    | 11         | 2       | 8      | 1      | 4.27/8    |
| 02    | 11         | 5       | 5      | 1*     | 5.4/8     |
| 06    | 10         | 5       | 3      | 2      | 5.1/8     |
| 07    | 9          | 2       | 7      | 0      | 5.2/8     |

\* RHAISTRAT-1153 scored 3/8 with scope reviewer recommending "split"; mapped to REVISE.

**Batches killed mid-review (03, 04, 05) -- scorer data from logs (no review files persisted):**

| Batch | Strategies | Scored | Missing | Scores captured |
|-------|------------|--------|---------|-----------------|
| 03    | 12         | 11     | 1 (RHAISTRAT-1118) | 8/8 APPROVE, 7/8 APPROVE, 6/8 APPROVE x2, 5/8 REVISE, 4/8 REVISE x4, 3/8 REVISE, 2/8 REJECT |
| 04    | 10         | 9      | 1 (STRAT-1486) | 5/8 REVISE x4, 4/8 REVISE x2, 3/8 SPLIT x2, 2/8 REJECT |
| 05    | 10         | 9      | 1 (STRAT-1501) | 7/8 APPROVE x3, 6/8 APPROVE x2, 5/8 REVISE, 4/8 REVISE x2, 3/8 REVISE (T=0) |

The scoring data was captured in the CI logs before the SIGTERM, but because the review stage was killed before `parse_results.py` and `apply_scores.py` could run (or before they completed), no review files were generated. The scorer results in `/tmp/strat-assess/review/` were ephemeral and lost with the container.

### Per-Dimension Scoring Patterns (from batch 01 detailed data)

| Dimension      | Avg Score | Zero Rate | Notes |
|----------------|-----------|-----------|-------|
| Feasibility    | 0.91/2    | 9% (1/11) | STRAT-163 was the only zero |
| Testability    | 0.73/2    | 36% (4/11) | Weakest dimension; 4 strategies scored 0/2 |
| Scope          | 1.45/2    | 9% (1/11) | STRAT-163 bundled too many features |
| Architecture   | 1.18/2    | 0%        | No zeros; most consistent dimension |

Testability is consistently the weakest dimension across all batches. This is a pipeline-level pattern, not a rubric calibration issue -- strategies frequently lack concrete acceptance criteria even when the source RFE contains them. The create and refine stages do not reliably extract acceptance criteria from RFEs.

The "split" verdict appeared in batches 02, 04, 06, and 07 when the scope reviewer judged a strategy bundles multiple independent features. This is a useful signal but "split" is not a valid frontmatter value, causing the orchestrator to manually map it to "reject" or "revise" in every affected batch.

### Per-Strategy Scores (batches with full reviews)

**Batch 01** (11 strategies):

| Strategy | F | T | S | A | Total | Verdict |
|----------|---|---|---|---|-------|---------|
| RHAISTRAT-1115 | 1 | 1 | 2 | 2 | 6/8 | APPROVE |
| RHAISTRAT-1284 | 1 | 2 | 2 | 1 | 6/8 | APPROVE |
| RHAISTRAT-312  | 1 | 1 | 1 | 2 | 5/8 | REVISE |
| RHAISTRAT-313  | 1 | 1 | 2 | 1 | 5/8 | REVISE |
| STRAT-158      | 1 | 1 | 2 | 1 | 5/8 | REVISE |
| STRAT-390      | 1 | 1 | 2 | 1 | 5/8 | REVISE |
| STRAT-334      | 1 | 1 | 1 | 1 | 4/8 | REVISE |
| STRAT-342      | 1 | 0 | 2 | 1 | 4/8 | REVISE |
| RHAISTRAT-497  | 1 | 0 | 1 | 1 | 3/8 | REVISE |
| STRAT-261      | 1 | 0 | 1 | 1 | 3/8 | REVISE |
| STRAT-163      | 0 | 0 | 0 | 1 | 1/8 | REJECT |

**Batch 02** (11 strategies):

| Strategy | Score | Verdict | Notes |
|----------|-------|---------|-------|
| STRAT-893      | 7/8 | APPROVE | Cleanest strategy in batch |
| STRAT-727      | 7/8 | APPROVE | |
| STRAT-912      | 7/8 | APPROVE | |
| RHAISTRAT-1239 | 6/8 | APPROVE | |
| RHAISTRAT-1474 | 6/8 | APPROVE | |
| RHAISTRAT-1202 | 5/8 | REVISE  | Zero acceptance criteria (T=0) |
| RHAISTRAT-133  | 5/8 | REVISE  | Tracing architecturally undesigned |
| STRAT-728      | 5/8 | REVISE  | Security model contradiction |
| RHAISTRAT-1130 | 4/8 | REVISE  | Hard dependency on RHAISTRAT-1153 |
| STRAT-737      | 4/8 | REVISE  | Limitador feasibility unvalidated |
| RHAISTRAT-1153 | 3/8 | REVISE* | Scope reviewer recommended split |

**Batch 06** (10 strategies):

| Strategy | Score | Verdict | Notes |
|----------|-------|---------|-------|
| STRAT-1626 | 7/8 | APPROVE | |
| STRAT-1625 | 6/8 | APPROVE | |
| STRAT-1628 | 6/8 | APPROVE | |
| STRAT-1643 | 6/8 | APPROVE | |
| STRAT-1755 | 6/8 | APPROVE | |
| STRAT-1627 | 5/8 | REVISE  | Field naming ambiguity blocks implementation |
| STRAT-1695 | 5/8 | REVISE  | Hard dependency on STRAT-1693 |
| STRAT-1693 | 4/8 | REVISE  | Incorrect AC1 (RAGAS/MLflow not EvalHub providers) |
| STRAT-1756 | 2/8 | REJECT  | No AI-BOMs exist; data flow missing |
| STRAT-1757 | 1/8 | REJECT  | 5 features across 5 teams |

**Batch 07** (9 strategies):

| Strategy | Score | Verdict | Notes |
|----------|-------|---------|-------|
| STRAT-1899 | 6/8 | APPROVE | Prose reviewer overwrote to REVISE; fixed |
| STRAT-1972 | 6/8 | APPROVE | Prose reviewer overwrote to REVISE; fixed |
| STRAT-1912 | 5/8 | REVISE  | |
| STRAT-1923 | 5/8 | REVISE  | |
| STRAT-1924 | 5/8 | REVISE  | Scope reviewer recommended split |
| STRAT-1940 | 5/8 | REVISE  | |
| STRAT-1968 | 5/8 | REVISE  | Scope reviewer recommended split |
| STRAT-1970 | 5/8 | REVISE  | |
| STRAT-1971 | 5/8 | REVISE  | |

## Quality Issues from LLM

### Issue 1: Prose Reviewers Overwriting Immutable Fields

**Batches affected:** 02, 07
**Severity:** Critical
**Description:** In batch 02, the testability reviewer modified score frontmatter values after `apply_scores.py` had set them from the authoritative `scores.csv`. Three strategies (STRAT-893, STRAT-727, STRAT-912) had testability scores changed from 1 to 2, inflating totals from 7/8 to 8/8. The orchestrator detected and corrected this. In batch 07, prose reviewers overwrote the `recommendation` field on STRAT-1899 and STRAT-1972 from `approve` to `revise`, despite both scoring 6/8 (APPROVE). The orchestrator used `frontmatter.py set recommendation=approve needs_attention=false` to fix both.

**Root cause:** The prose reviewer skill instructions do not explicitly prohibit modifying frontmatter fields. The reviewer reads the review file (which contains frontmatter), decides the score should be different, and uses `frontmatter.py set` to "correct" it.

**Fix:** Add an explicit constraint to all 4 prose reviewer skill files: "NEVER modify any frontmatter field. Your role is to write prose sections only. The scores, recommendation, and verdict fields are set by the scoring pipeline and are immutable."

### Issue 2: Invalid Verdict Value "split"

**Batches affected:** 02, 04, 06, 07
**Severity:** Medium
**Description:** The scope reviewer generates "split" as a verdict recommendation when a strategy bundles multiple independent features. The frontmatter system only accepts `approve`, `revise`, `reject`. Each occurrence required manual correction.

**Fix:** Either (a) add "split" as a valid frontmatter value, or (b) add a mapping in the scope reviewer skill: "If you would recommend splitting, use verdict=reject and explain the split recommendation in the prose."

### Issue 3: Consolidated Prose Instead of Per-File Sections

**Batches affected:** 06, 07
**Severity:** Medium
**Description:** The scope and architecture reviewers sometimes generate a single consolidated report covering all strategies instead of writing individual per-file sections. The main review orchestrator then has to manually extract and distribute content to each file, which is error-prone and time-consuming.

**Root cause:** The reviewer skills operate on the full set of strategies. When the context is large enough, the LLM "optimizes" by producing a summary instead of N individual reviews.

**Fix:** Restructure prose reviewer skills to process one strategy at a time, similar to the scorer agent model. This would also reduce per-invocation context size and improve reliability.

### Issue 4: Report Generator Undercounts RHAISTRAT Files

**Batches affected:** 01, 02 (confirmed), likely all batches with Path A imports
**Severity:** Medium
**Description:** `generate-report.py` reports "Found N strategies, N reviews" where N only counts `STRAT-*.md` named files. `RHAISTRAT-*.md` files (from Path A imports) are excluded from the report. In batch 01, it reported "6 strategies, 6 reviews" but the spot check showed 11 tasks and 11 reviews. In batch 02, it reported "5 strategies, 5 reviews" but the spot check showed 11 tasks and 11 reviews.

**Fix:** Update `generate-report.py` to glob both `STRAT-*.md` and `RHAISTRAT-*.md` patterns.

## STRAT Import Path A Effectiveness

20 of 73 strategies (27%) used Path A (importing existing RHAISTRAT content from Jira). Path A adds complexity to the create stage:

1. **Additional Jira API calls:** Each Path A strategy requires fetching the RHAISTRAT issue content in addition to the RFE, roughly doubling create-stage API calls for those items.

2. **Larger Write operations:** Path A files contain the full existing STRAT description, which can be substantially larger than Path B stubs. Write times for Path A files averaged 30-90s vs 10-30s for Path B.

3. **Path A detection logic is fragile:** In batch 02, the LLM spent significant thinking time (~2 min) reasoning about Cloners link direction (inward vs outward). The link type "is cloned by" vs "clones" direction is not intuitive, and the LLM's reasoning was initially incorrect before self-correcting.

4. **Multi-STRAT RFEs handled correctly:** RHAIRFE-64 had 2 STRATs (RHAISTRAT-312 + RHAISTRAT-1115), RHAIRFE-904 had 2 STRATs (RHAISTRAT-1130 + RHAISTRAT-1153), and RHAIRFE-1131 had 3 STRATs. The pipeline correctly imported all of them as separate strategy files.

5. **Closed/duplicate STRATs correctly filtered:** RHAISTRAT-314 (DUPLICATE-CLOSED, linked to RHAIRFE-709) was correctly skipped; only the active RHAISTRAT-313 was imported.

6. **Path A strategies scored similarly to Path B.** There is no evidence that importing existing STRAT content produces higher-quality strategies. Both paths show similar scoring distributions. This suggests the refine stage effectively normalizes quality regardless of starting content.

**Path A usage by batch:**

| Batch | RFEs with strat_key | Additional via Cloners | Total Path A | Path B |
|-------|---------------------|----------------------|--------------|--------|
| 01    | 5                   | 1 (RHAISTRAT-312 via RHAIRFE-64) | 6 | 5 |
| 02    | 5                   | 1 (RHAISTRAT-1130 via RHAIRFE-904) | 6 | 5 |
| 03    | 5                   | 2 (RHAIRFE-1131 had 3 STRATs) | 5+ | 7 |
| 04    | 3                   | 0 | 3 | 7 |
| 05    | 2                   | 0 | 2 | 8 |
| 06    | 0                   | 0 | 0 | 10 |
| 07    | 0                   | 0 | 0 | 9 |

**Recommendation:** The current Path A detection logic (scanning Jira issue links for Cloners type) works but is slow and error-prone. Consider pre-computing the RFE-to-STRAT mapping in config.yaml using `strat_key` field for all entries (currently only some have it) rather than having the LLM discover it at runtime.

## Pipeline Issues

### Issue 1: rc=143 Treated as Success (Critical)

**Impact:** 3 of 7 batches (43%) reported "success" despite incomplete review cycles. Approximately $25 in compute spent on review stages that produced no usable output.

`stream-claude.py` contains logic that treats SIGTERM (rc=143) as a successful completion. This was likely designed to handle graceful Claude Code shutdown, but it masks genuine failures where the review stage is killed before completing.

Detailed kill analysis:
- **Batch 03** (12 strategies): 11 of 12 scorers completed, then SIGTERM. The 12th scorer was still running. No `parse_results.py` or `apply_scores.py` ran. 0 review files persisted.
- **Batch 04** (10 strategies): 9 of 10 scorers completed (STRAT-1486 missing), then SIGTERM. 0 review files persisted.
- **Batch 05** (10 strategies): 9 of 10 scorers completed (STRAT-1501 missing), then SIGTERM. 0 review files persisted.

In all three cases, the scorers ran to near-completion (~3 minutes of review stage) but the prose review phase (which takes 20-30 minutes) never started. The kills happened at the transition between scoring and prose review.

**Fix:** Either:
- Increase CI job timeout from ~25 min to 60 min to accommodate full review cycles
- Add a post-run validation step that checks for expected outputs (review files must exist for all strategy files)
- Change rc=143 handling to report "partial" rather than "success"

### Issue 2: CI Job Timeout Mismatch

The CI job timeout appears to be ~25 minutes for the review stage, but complete review cycles require 22-36 minutes:
- Batch 01: 2666s total (44 min), review stage ~22 min
- Batch 02: 2956s total (49 min), review stage ~26 min
- Batch 06: 2749s total (46 min), review stage ~29 min
- Batch 07: 3362s total (56 min), review stage ~36 min

Batches 03-05 were killed at 1427s, 1463s, 1495s (~24 min total), which corresponds to only ~3 min of review stage time (create+refine took ~20 min). The SIGTERM appears to be hitting the review stage early, possibly triggered by a per-stage timeout rather than a per-job timeout.

### Issue 3: No Retry or Checkpoint Mechanism

When a batch is killed mid-review, the entire review stage must be re-run from scratch. There is no checkpoint mechanism to resume from where the previous run left off. The scorer results are lost because they're stored in `/tmp/strat-assess/review/` which is ephemeral.

## Execution Timeline

All 7 pipelines were triggered at ~21:38 UTC on 2026-04-15:

```
21:21 ─ Batch 01 starts (runner s_a21fb15ccc7a)
21:38 ─ Batches 02-07 triggered
       ─ Batch 02 starts (runner s_4ea5aaf1eae5)
       ─ Batches 03-07 queued (single runner HwHQ9C1DY)
22:14 ─ Batch 01 finishes (44 min, FULL REVIEW)
00:05 ─ Batch 02 finishes (49 min, FULL REVIEW)
00:29 ─ Batch 03 finishes (24 min, rc=143 KILLED during review)
00:53 ─ Batch 04 finishes (24 min, rc=143 KILLED during review)
01:18 ─ Batch 05 finishes (25 min, rc=143 KILLED during review)
02:04 ─ Batch 06 finishes (46 min, FULL REVIEW)
03:00 ─ Batch 07 finishes (56 min, FULL REVIEW)
```

Total wall-clock time: 5h 39m (21:21 to 03:00 UTC).
If all batches ran in parallel on separate runners: ~56 min (batch 07's duration).

## Recommendations

### Priority 1: Fix the Timeout/Kill Problem

1. Increase CI job timeout to at least 60 minutes, or better yet, 90 minutes for safety margin.
2. Change `stream-claude.py` to distinguish between rc=143 with complete output vs rc=143 with incomplete output.
3. Add a post-pipeline validation step that verifies review file count matches strategy file count.

### Priority 2: Harden Prose Reviewers

1. Add explicit "NEVER modify frontmatter" constraints to all 4 prose reviewer skill definitions.
2. Either add "split" as a valid verdict enum value or document the mapping to "reject" in the skill instructions.
3. Consider restructuring prose reviewers to process one file at a time (like scorer agents) instead of all files at once. This would:
   - Prevent consolidated-report behavior
   - Reduce per-invocation context size
   - Enable partial progress on kill
   - Improve cost efficiency by reducing redundant context

### Priority 3: Fix Report Generator

Update `generate-report.py` to glob both `STRAT-*.md` and `RHAISTRAT-*.md` file patterns. This is a one-line fix that affects the accuracy of all batch reports.

### Priority 4: Optimize Review Stage Cost

The review stage is 73% of total cost ($90 of $124). Options:
- Switch prose reviewers from one-shot-all-files to per-file invocations (reduces context size)
- Use a smaller/cheaper model for scoring (scorers are formulaic -- they apply a rubric)
- Cache architecture context across stages (currently re-fetched for review)
- Run scoring and prose review in a single pass instead of sequentially

### Priority 5: Improve Path A Reliability

- Pre-compute RFE-to-STRAT mapping in config.yaml using `strat_key` field for all entries (currently only some have it)
- Remove runtime Cloners link discovery logic from the create stage
- This saves ~2 min of LLM "thinking" time per batch and eliminates link-direction reasoning errors

## What to Fix Before Next Run

| Priority | Fix | Effort | Impact |
|----------|-----|--------|--------|
| P0 | Increase CI job timeout to 90 min | Config change | Prevents 43% of batches from being killed |
| P0 | Add post-run validation (review count = strategy count) | Script (~20 lines) | Detects incomplete runs |
| P1 | Add "NEVER modify frontmatter" to prose reviewer skills | 4 file edits | Prevents score corruption |
| P1 | Add "split" to valid verdict values or map to reject | Schema + skill edit | Eliminates manual corrections |
| P1 | Fix generate-report.py RHAISTRAT glob | 1-line fix | Correct report counts |
| P2 | Change rc=143 to "partial" status when outputs incomplete | Script change | Accurate CI status |
| P2 | Pre-compute strat_key in all config.yaml entries | Config generation | Faster, more reliable Path A |
| P3 | Restructure prose reviewers to per-file invocation | Architecture change | Cost reduction + reliability |

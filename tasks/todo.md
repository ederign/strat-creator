# TODO — 2026-04-16

## Dashboard Executive Summary Panel
- [ ] Add aggregate totals panel at top of dashboard (total reviewed, approved %, revision %, rejected %, avg score)
- [ ] Add per-dimension health bars (feasibility/testability/scope/architecture averages)
- [ ] Add attention funnel (needs staff engineer input vs ready for implementation)
- [ ] Dedup logic: for each unique strategy ID, use the MOST RECENT run that contains it
- [ ] Keep per-run trend charts below for drill-down detail

## Rubric Calibration
- [ ] Review Dashboard 3.5 batch execution results (69 RFEs) for calibration data
- [ ] Add calibration examples from real pipeline output to each prose reviewer skill (feasibility, testability, scope, architecture)
- [ ] Anchor examples to the 0/1/2 scoring scale from the rubric
- [ ] Tune review prompts to reduce false positives (flagging non-issues) and false negatives (missing real problems)
- [ ] Validate calibration: compare prose reviewer output against scorer results across the batch run

## Batch Execution Analysis
- [ ] Review wiki/16-dashboard35-batch-execution-lessons.md (auto-generated overnight from batch logs)
- [ ] Identify pipeline improvements to implement before next large run

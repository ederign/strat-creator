#!/bin/bash
# Run the full strategy pipeline N times to measure scoring variance.
# Usage: bash scripts/variance-runner.sh [NUM_RUNS]
set -euo pipefail

STRAT_DIR="/Users/ederign/src/agentic-sdlc/strat-creator"
RESULTS_DIR="/Users/ederign/src/agentic-sdlc/wiki/variance-data"
RFE_IDS="RHAIRFE-184 RHAIRFE-238 RHAIRFE-262 RHAIRFE-284 RHAIRFE-428 RHAIRFE-522 RHAIRFE-648 RHAIRFE-709 RHAIRFE-710 RHAIRFE-727"
NUM_RUNS="${1:-10}"

cd "$STRAT_DIR"
mkdir -p "$RESULTS_DIR"

echo "=== Variance Experiment: $NUM_RUNS runs of batch-01 ==="
echo "Started: $(date)"
echo "Results: $RESULTS_DIR"
echo ""

# Backup existing artifacts
if [ -d "$RESULTS_DIR/original-artifacts-backup" ]; then
  echo "Backup already exists, skipping"
else
  mkdir -p "$RESULTS_DIR/original-artifacts-backup"
  cp -r artifacts/strat-tasks "$RESULTS_DIR/original-artifacts-backup/" 2>/dev/null || true
  cp -r artifacts/strat-reviews "$RESULTS_DIR/original-artifacts-backup/" 2>/dev/null || true
  cp -r artifacts/strat-originals "$RESULTS_DIR/original-artifacts-backup/" 2>/dev/null || true
  cp -r artifacts/strat-skipped "$RESULTS_DIR/original-artifacts-backup/" 2>/dev/null || true
  echo "Backed up existing artifacts"
fi

# Restore on exit
restore_artifacts() {
  echo ""
  echo "=== Restoring original artifacts ==="
  rm -rf artifacts/strat-tasks artifacts/strat-reviews artifacts/strat-originals artifacts/strat-skipped
  cp -r "$RESULTS_DIR/original-artifacts-backup/strat-tasks" artifacts/ 2>/dev/null || true
  cp -r "$RESULTS_DIR/original-artifacts-backup/strat-reviews" artifacts/ 2>/dev/null || true
  cp -r "$RESULTS_DIR/original-artifacts-backup/strat-originals" artifacts/ 2>/dev/null || true
  cp -r "$RESULTS_DIR/original-artifacts-backup/strat-skipped" artifacts/ 2>/dev/null || true
  echo "Restore complete"
}
trap restore_artifacts EXIT

completed=0
failed=0

for i in $(seq 1 "$NUM_RUNS"); do
  RUN_NUM=$(printf '%02d' "$i")
  RUN_DIR="$RESULTS_DIR/run-${RUN_NUM}"
  mkdir -p "$RUN_DIR"

  echo ""
  echo "======================================================"
  echo "  Run $i of $NUM_RUNS — $(date)"
  echo "======================================================"

  START=$(date +%s)

  # Clean artifacts for this run
  rm -rf artifacts/strat-tasks artifacts/strat-reviews artifacts/strat-originals artifacts/strat-skipped
  mkdir -p artifacts/strat-tasks artifacts/strat-reviews artifacts/strat-originals artifacts/strat-skipped
  rm -rf /tmp/strat-assess

  # Skip bootstrap for runs 2+ (context already fetched in run 1)
  if [ "$i" -gt 1 ]; then
    export STRAT_SKIP_BOOTSTRAP=1
    export RFE_SKIP_BOOTSTRAP=1
  else
    unset STRAT_SKIP_BOOTSTRAP 2>/dev/null || true
    unset RFE_SKIP_BOOTSTRAP 2>/dev/null || true
  fi

  # Stage 1: Create
  echo "--- [$RUN_NUM] Stage 1: strategy.create ---"
  CREATE_START=$(date +%s)
  CREATE_EXIT=0
  claude -p "/strategy.create ${RFE_IDS} --dry-run" \
    --dangerously-skip-permissions \
    --model claude-opus-4-6 \
    --output-format stream-json \
    --verbose \
    > "$RUN_DIR/create.log" 2>&1 || CREATE_EXIT=$?
  CREATE_END=$(date +%s)
  echo "  create finished in $((CREATE_END - CREATE_START))s (exit=$CREATE_EXIT)"

  if [ "$CREATE_EXIT" -ne 0 ]; then
    echo "  ERROR: create failed, skipping remaining stages"
    cat > "$RUN_DIR/meta.json" <<METAEOF
{"run": $i, "status": "create_failed", "create_exit": $CREATE_EXIT, "create_duration": $((CREATE_END - CREATE_START)), "start_epoch": $START, "end_epoch": $(date +%s)}
METAEOF
    failed=$((failed + 1))
    continue
  fi

  # Stage 2: Refine
  echo "--- [$RUN_NUM] Stage 2: strategy.refine ---"
  REFINE_START=$(date +%s)
  REFINE_EXIT=0
  claude -p "/strategy.refine --dry-run" \
    --dangerously-skip-permissions \
    --model claude-opus-4-6 \
    --output-format stream-json \
    --verbose \
    > "$RUN_DIR/refine.log" 2>&1 || REFINE_EXIT=$?
  REFINE_END=$(date +%s)
  echo "  refine finished in $((REFINE_END - REFINE_START))s (exit=$REFINE_EXIT)"

  if [ "$REFINE_EXIT" -ne 0 ]; then
    echo "  ERROR: refine failed, skipping review"
    cp -r artifacts/ "$RUN_DIR/artifacts/"
    cat > "$RUN_DIR/meta.json" <<METAEOF
{"run": $i, "status": "refine_failed", "create_exit": $CREATE_EXIT, "create_duration": $((CREATE_END - CREATE_START)), "refine_exit": $REFINE_EXIT, "refine_duration": $((REFINE_END - REFINE_START)), "start_epoch": $START, "end_epoch": $(date +%s)}
METAEOF
    failed=$((failed + 1))
    continue
  fi

  # Stage 3: Review
  echo "--- [$RUN_NUM] Stage 3: strategy.review ---"
  REVIEW_START=$(date +%s)
  REVIEW_EXIT=0
  claude -p "/strategy.review --dry-run" \
    --dangerously-skip-permissions \
    --model claude-opus-4-6 \
    --output-format stream-json \
    --verbose \
    > "$RUN_DIR/review.log" 2>&1 || REVIEW_EXIT=$?
  REVIEW_END=$(date +%s)
  echo "  review finished in $((REVIEW_END - REVIEW_START))s (exit=$REVIEW_EXIT)"

  END=$(date +%s)
  DURATION=$((END - START))

  # Copy artifacts
  cp -r artifacts/ "$RUN_DIR/artifacts/"

  # Count results
  TASK_COUNT=$(find "$RUN_DIR/artifacts/strat-tasks" -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
  REVIEW_COUNT=$(find "$RUN_DIR/artifacts/strat-reviews" -name '*-review.md' ! -name '*-comment.md' 2>/dev/null | wc -l | tr -d ' ')

  STATUS="complete"
  if [ "$REVIEW_EXIT" -ne 0 ]; then
    STATUS="review_failed"
    failed=$((failed + 1))
  else
    completed=$((completed + 1))
  fi

  cat > "$RUN_DIR/meta.json" <<METAEOF
{
  "run": $i,
  "status": "$STATUS",
  "create_exit": $CREATE_EXIT,
  "create_duration": $((CREATE_END - CREATE_START)),
  "refine_exit": $REFINE_EXIT,
  "refine_duration": $((REFINE_END - REFINE_START)),
  "review_exit": $REVIEW_EXIT,
  "review_duration": $((REVIEW_END - REVIEW_START)),
  "total_duration": $DURATION,
  "tasks": $TASK_COUNT,
  "reviews": $REVIEW_COUNT,
  "start_epoch": $START,
  "end_epoch": $END
}
METAEOF

  echo "  Run $i: $STATUS — ${DURATION}s total, $TASK_COUNT tasks, $REVIEW_COUNT reviews"
done

echo ""
echo "======================================================"
echo "  Experiment Complete — $(date)"
echo "  $completed/$NUM_RUNS succeeded, $failed failed"
echo "  Results: $RESULTS_DIR"
echo "======================================================"
echo ""
echo "Running analysis..."
python3 scripts/variance-analysis.py
echo ""
echo "Done. Report: /Users/ederign/src/agentic-sdlc/wiki/22-variance-experiment.md"

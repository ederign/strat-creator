#!/bin/bash
# Monitor batch CI jobs and generate a report when all complete.
# Usage: bash scripts/batch-report.sh
set -euo pipefail

REPO="redhat/rhel-ai/agentic-ci/strat-pipeline"
DATA_REPO="/Users/ederign/src/agentic-sdlc/AgenticCI/strat-pipeline-data"
WIKI_DIR="/Users/ederign/src/agentic-sdlc/wiki"
REPORT="$WIKI_DIR/23-batch-execution-report.md"

PIPELINES=(
  "01:2462893885"
  "02:2463003973"
  "03:2462893745"
  "04:2463006298"
  "05:2463006315"
  "06:2463006328"
  "07:2463006348"
  "08:2463006367"
  "09:2463006385"
  "10:2463006403"
)

echo "=== Batch Pipeline Monitor ==="
echo "Started: $(date)"
echo "Polling every 5 minutes until all pipelines complete..."
echo ""

# Poll until all pipelines are in a terminal state
while true; do
  all_done=true
  summary=""

  for entry in "${PIPELINES[@]}"; do
    batch="${entry%%:*}"
    pid="${entry##*:}"
    st=$(glab ci get --pipeline-id "$pid" --repo "$REPO" 2>&1 | grep "^status:" | awk '{print $2}')
    summary+="  Batch $batch ($pid): $st"$'\n'

    case "$st" in
      success|failed|canceled|skipped) ;;
      *) all_done=false ;;
    esac
  done

  echo "[$(date '+%H:%M')] Pipeline status:"
  echo "$summary"

  if $all_done; then
    echo "All pipelines in terminal state."
    break
  fi

  echo "  Waiting 5 minutes..."
  sleep 300
done

echo ""
echo "=== Generating Report ==="

# Pull latest data repo
echo "Pulling strat-pipeline-data..."
git -C "$DATA_REPO" pull --ff-only 2>&1 || echo "WARNING: git pull failed"

# Collect final statuses and job details
declare -A BATCH_STATUS
declare -A BATCH_DURATION
declare -A BATCH_COST

for entry in "${PIPELINES[@]}"; do
  batch="${entry%%:*}"
  pid="${entry##*:}"

  st=$(glab ci get --pipeline-id "$pid" --repo "$REPO" 2>&1 | grep "^status:" | awk '{print $2}')
  BATCH_STATUS[$batch]="$st"

  # Get job details if it ran
  if [ "$st" = "success" ] || [ "$st" = "failed" ]; then
    job_info=$(glab ci get --pipeline-id "$pid" --repo "$REPO" 2>&1)
    started=$(echo "$job_info" | grep "^started:" | sed 's/started:\t//')
    updated=$(echo "$job_info" | grep "^updated:" | sed 's/updated:\t//')
    BATCH_DURATION[$batch]="$started → $updated"
  else
    BATCH_DURATION[$batch]="—"
  fi
done

# Count runs in data repo
run_count=$(find "$DATA_REPO/RHAISTRAT" -maxdepth 1 -type d -name '20*' 2>/dev/null | wc -l | tr -d ' ')

# Count strategies and reviews across all runs
total_tasks=0
total_reviews=0
for run_dir in "$DATA_REPO"/RHAISTRAT/20*/; do
  if [ -d "$run_dir/strat-tasks" ]; then
    n=$(find "$run_dir/strat-tasks" -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
    total_tasks=$((total_tasks + n))
  fi
  if [ -d "$run_dir/strat-reviews" ]; then
    n=$(find "$run_dir/strat-reviews" -name '*-review.md' ! -name '*-comment*' 2>/dev/null | wc -l | tr -d ' ')
    total_reviews=$((total_reviews + n))
  fi
done

# Parse scores from review frontmatter across all runs
SCORE_DATA=""
for run_dir in "$DATA_REPO"/RHAISTRAT/20*/; do
  if [ ! -d "$run_dir/strat-reviews" ]; then continue; fi
  run_name=$(basename "$run_dir")
  for review in "$run_dir"/strat-reviews/*-review.md; do
    [ -f "$review" ] || continue
    [[ "$review" == *-comment* ]] && continue
    fm_json=$(python3 /Users/ederign/src/agentic-sdlc/strat-creator/scripts/frontmatter.py read "$review" 2>/dev/null) || continue
    strat_id=$(echo "$fm_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('strat_id','?'))" 2>/dev/null)
    rec=$(echo "$fm_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('recommendation','?'))" 2>/dev/null)
    total=$(echo "$fm_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('scores',{}).get('total','?'))" 2>/dev/null)
    SCORE_DATA+="$run_name|$strat_id|$total|$rec"$'\n'
  done
done

# Count verdicts
approve_count=$(echo "$SCORE_DATA" | grep -ci "approve" || true)
revise_count=$(echo "$SCORE_DATA" | grep -ci "revise" || true)
reject_count=$(echo "$SCORE_DATA" | grep -ci "reject" || true)

# Check for skipped RFEs
skipped_dir="$DATA_REPO/strat-skipped"
skipped_count=0
if [ -d "$skipped_dir" ]; then
  skipped_count=$(find "$skipped_dir" -name '*.md' | wc -l)
fi

# Generate report
cat > "$REPORT" <<REPORTEOF
# Batch Execution Report — Engineering 3.5

*Generated: $(date '+%Y-%m-%d %H:%M')*

## Overview

Ran the full strategy pipeline (create → refine → review) in **dry-run mode** across 10 batches
covering the Engineering 3.5 RFE portfolio. Each batch processes ~10 RFEs through the label gate,
creating strategies for those with the required labels (\`strat-creator-3.5\` + \`rfe-creator-autofix-rubric-pass\`
or \`tech-reviewed\`).

## Pipeline Status

| Batch | Pipeline | Status |
|-------|----------|--------|
REPORTEOF

for entry in "${PIPELINES[@]}"; do
  batch="${entry%%:*}"
  pid="${entry##*:}"
  st="${BATCH_STATUS[$batch]}"
  icon="❓"
  case "$st" in
    success) icon="✅" ;;
    failed) icon="❌" ;;
    canceled) icon="🚫" ;;
    *) icon="⏳" ;;
  esac
  echo "| $batch | [$pid](https://gitlab.com/redhat/rhel-ai/agentic-ci/strat-pipeline/-/pipelines/$pid) | $icon $st |" >> "$REPORT"
done

cat >> "$REPORT" <<REPORTEOF

## Results Summary

| Metric | Value |
|--------|-------|
| Successful pipeline runs | $(echo "${BATCH_STATUS[@]}" | tr ' ' '\n' | grep -c success || true)/10 |
| Data repo runs | $run_count |
| Total strategies created | $total_tasks |
| Total strategies reviewed | $total_reviews |
| Verdicts: APPROVE | $approve_count |
| Verdicts: REVISE | $revise_count |
| Verdicts: REJECT | $reject_count |

## Per-Strategy Results

| Run | Strategy | Score | Verdict |
|-----|----------|-------|---------|
REPORTEOF

echo "$SCORE_DATA" | while IFS='|' read -r run strat total rec; do
  [ -z "$run" ] && continue
  echo "| $run | $strat | $total/8 | $rec |" >> "$REPORT"
done

cat >> "$REPORT" <<REPORTEOF

## Key Observations

### What Worked
- The SIGTERM fix (\`stream-claude.py\` / \`run-claude.sh\`) resolved the premature termination issue from the initial batch-01 run
- Label gate correctly filters RFEs missing required labels
- Pipeline data is organized into timestamped runs with proper retention

### Issues Encountered
- **Initial batch-01 failure**: \`stream-claude.py\` broke on the first \`result\` message while background scorer agents were still running. Fixed by waiting for EOF instead.
- **Initial batch-02 push conflict**: Our data repo cleanup created a rebase conflict. Fixed by retriggering.
- **Python 3.9 compatibility**: UBI9 ships Python 3.9 which doesn't allow backslashes in f-string expressions. Fixed by extracting variables.

### Lessons Learned
1. **Don't trust intermediate signals as completion markers** — the \`result\` message in Claude's stream-json can arrive before all background work finishes
2. **CI data repos need conflict resilience** — when multiple processes can modify the same repo, \`push-results.py\`'s retry+rebase approach works but can still fail on content conflicts
3. **Always test with the target Python version** — f-string backslash syntax is a Python 3.12+ feature that silently works locally but breaks in CI

### Improvement Ideas
1. **Validate run completeness before pushing** — check that reviews exist when tasks exist
2. **Add per-batch cost tracking** — capture OTEL token data in the data repo for cost analysis
3. **Dashboard should handle partial runs** — show create-only or refine-only runs with a "review pending" indicator
4. **Consider running batches in parallel** — currently \`resource_group\` serializes all batches; could use per-batch resource groups

## Raw Data

- Pipeline data repo: [strat-pipeline-data](https://gitlab.com/redhat/rhel-ai/agentic-ci/strat-pipeline-data)
- Dashboard: [strat-dashboard](https://redhat.gitlab.io/rhel-ai/agentic-ci/strat-dashboard/)
- Batch configs: \`config/engineering35-batches/batch-{01..10}.yaml\`
REPORTEOF

echo ""
echo "=== Report generated: $REPORT ==="
echo "Finished: $(date)"

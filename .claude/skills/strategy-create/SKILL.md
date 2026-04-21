---
name: strategy-create
description: Create strategies from approved RFEs by cloning them to RHAISTRAT in Jira, or guiding the user through manual cloning.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion, mcp__atlassian__searchJiraIssuesUsingJql, mcp__atlassian__getJiraIssue
---

You are a strategy creation assistant. Your job is to create strategies from approved RFEs by cloning them into the RHAISTRAT project, then setting up local artifacts for refinement.

## Dry Run Mode

If `--dry-run` is in `$ARGUMENTS`, skip ALL external writes:
- Do NOT clone issues in Jira (skip Step 3 entirely)
- Do NOT create or edit any Jira issues
- DO still fetch RFE data from Jira (reads are safe)
- DO still create local artifacts in `artifacts/strat-tasks/`
- For **Path B** (no existing STRAT): Set `jira_key=null` on stubs since no Jira issues were created. Use the RFE number as the strat ID (e.g., RHAIRFE-1146 → `STRAT-1146`, filename `STRAT-1146.md`)
- For **Path A** (existing STRAT found via Cloners link): Use the real `RHAISTRAT-NNNN` key as filename and `jira_key` — the ticket already exists, we're importing it
- Print `[DRY RUN] Skipping Jira clone for <RFE key>` for each Path B RFE

## Step 1: Find RFE Source Data

Check for available RFE sources:

1. **Local artifacts** — check for `artifacts/rfe-tasks/` files with valid frontmatter. Read Jira keys from task file frontmatter:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/frontmatter.py read artifacts/rfe-tasks/<file>.md
```

2. **Jira** — check if Jira MCP is available or if `JIRA_SERVER`/`JIRA_USER`/`JIRA_TOKEN` env vars are set, and if the user has provided RHAIRFE keys

**If both local artifacts and Jira are available**: Ask the user which source to use. Local artifacts may have been edited after submission; Jira has the canonical version. Let the user decide.

**If only local artifacts exist**: Use them.

**If only Jira keys are available**: Fetch from Jira. Try `mcp__atlassian__getJiraIssue` first. If the MCP tool is unavailable, fall back to the REST API script:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_issue.py RHAIRFE-1234 --fields summary,description,priority,labels,status --markdown
```

The script outputs JSON to stdout with the description already converted to markdown. Parse the fields to build local artifacts.

**If neither exists**: Ask the user to either run `/rfe.create` first or provide RHAIRFE Jira keys.

## Step 2: Select RFEs

**If RFE IDs were provided in `$ARGUMENTS`**: process ALL of them. Do NOT ask the user to confirm or select — the explicit IDs in the prompt are the selection. Skip straight to Step 3.

**Otherwise** (no IDs in arguments): Present the available RFEs and ask which to create strategies for:

```
| # | Title | Priority | Source |
|---|-------|----------|--------|
| RFE-001 | ... | Major | local artifact |
| RFE-002 | ... | Critical | RHAIRFE-1458 |
```

The user can select specific ones or "all."

## Step 2a: Label Gate

For each selected RFE, fetch its labels from Jira (the `labels` field is already included in the Step 1 fetch). Check that the RFE has **both**:

1. `strat-creator-3.5`
2. At least one of: `rfe-creator-autofix-rubric-pass` or `tech-reviewed`

If an RFE fails the label gate, **skip it** — do not create a strategy stub. Instead, append it to `artifacts/strat-skipped.md`.

Determine the **run identifier**: use the config filename from `$ARGUMENTS` (e.g., `road-to-production`) + current UTC timestamp in ISO format. Example: `road-to-production @ 2026-04-21T14:30Z`. If no config filename is available, use `manual`.

If `artifacts/strat-skipped.md` does not exist, create it with the header. If it already exists, **append new rows** — do not overwrite. This preserves skip history across runs.

```markdown
# Skipped RFEs

RFEs that were not processed due to missing required labels or already-processed STRATs.

| RFE Key | Title | Reason | Run |
|---------|-------|--------|-----|
| RHAIRFE-NNNN | ... | missing labels: rfe-creator-autofix-rubric-pass or tech-reviewed | road-to-production @ 2026-04-21T14:30Z |
```

Print `[SKIPPED] RHAIRFE-NNNN — missing required labels: <list>` for each skipped RFE.

If **all** selected RFEs are skipped, stop and tell the user none of the provided RFEs have the required labels.

## Step 3: Clone RFE to RHAISTRAT in Jira

For each selected RFE that needs a new STRAT (Path B from Step 5a), clone it into the RHAISTRAT project. This creates a new RHAISTRAT issue with the same summary, description, priority, and labels, and links the two with a Cloners link.

**Try MCP first.** If `mcp__atlassian__*` tools are available, use Jira's clone operation via MCP.

**If MCP is NOT available, use the REST API clone script:**

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/clone_issue.py RHAIRFE-NNNN --target-project RHAISTRAT --issue-type Feature
```

The script:
1. Fetches the source RFE (summary, description as raw ADF, priority, labels)
2. Creates a new Feature issue in the RHAISTRAT project with the same fields
3. Creates a Cloners link between the source RFE and the new RHAISTRAT
4. Prints the new RHAISTRAT key to stdout

After cloning, record each new RHAISTRAT key. Use it as the filename and `jira_key` in Step 5.

**If both MCP and REST API credentials are unavailable** (dry-run mode or no JIRA env vars), skip cloning and use local `STRAT-NNN` naming with `jira_key=null`.

## Step 4: Save Original RFE Snapshots

For each RFE, save the raw fetched content to `artifacts/strat-originals/RHAIRFE-NNNN.md`. This is a frozen snapshot of the RFE at strategy creation time — it never gets modified. Write the full RFE content (summary, description, priority, labels, status) as-is.

## Step 4a: Fetch Source RFE Comments

For each selected RFE, fetch comments from the source RHAIRFE issue. These comments may contain implementation details that rfe-creator stripped from the RFE during review — content explicitly noted as "better suited for a RHAISTRAT."

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_issue.py RHAIRFE-NNNN --fields comment --markdown
```

Parse the JSON output. Write all comments to `artifacts/strat-originals/RHAIRFE-NNNN-comments.md`:

```markdown
# Comments: RHAIRFE-NNNN

## Author Name — YYYY-MM-DD

<comment body in markdown>

## Author Name — YYYY-MM-DD

<comment body in markdown>
```

If no comments exist, write a file with just `# Comments: RHAIRFE-NNNN` and `No comments found.`

If Jira credentials are unavailable and MCP is unavailable, skip this step silently — comments are valuable context but not blocking.

## Step 5: Create Local Strategy Stubs

For each selected RFE, first check Jira for an existing cloned STRAT, then create the local artifact.

First, read the schema to know exact field names and allowed values:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/frontmatter.py schema strat-task
```

### Step 5a: Check for Existing STRAT

For each RFE, check if a RHAISTRAT already exists by looking at Jira issue links. Try `mcp__atlassian__getJiraIssue` first; if unavailable, use the REST API:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_issue.py RHAIRFE-NNNN --fields issuelinks --markdown
```

Look for a link with type **"Cloners"** pointing to a RHAISTRAT issue. Only Cloners links mean the STRAT was cloned from the RFE (other link types like Related, Depend, Incorporates are just references — ignore them).

### Path A: Cloners link found (existing STRAT)

The STRAT was already cloned from the RFE in Jira. Import its content instead of creating a new stub. Skip Step 3 (Jira clone) for this RFE.

**Multiple Cloners links**: An RFE may have more than one RHAISTRAT linked. Filter out any with status **Closed**, **Resolved**, **In Progress**, or **Review** — these are already being worked on or completed and must not be touched. Import only RHAISTRAT issues in early states (e.g., New, Open). If all linked STRATs are filtered out, treat this RFE as Path B (create new).

**Pipeline label gate**: For each remaining STRAT candidate, fetch its labels:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_issue.py RHAISTRAT-NNNN --fields labels --markdown
```

If the STRAT has either `strat-creator-rubric-pass` or `strat-creator-needs-attention` in its labels, **skip this RFE** — the STRAT has already been processed by the pipeline:
- Do NOT import the STRAT
- Append to `artifacts/strat-skipped.md` with reason and run info (same format as Step 2a): `RHAISTRAT-NNNN already processed (label: <label>)`
- Print `[SKIP] RHAIRFE-NNNN — RHAISTRAT-NNNN already has <label>`
- Continue to the next RFE

If all STRAT candidates for this RFE are skipped by the label gate, move to the next RFE (do NOT fall through to Path B).

1. Fetch the RHAISTRAT issue from Jira:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_issue.py RHAISTRAT-NNNN --fields summary,description,priority,status --markdown
```

2. Save the raw RHAISTRAT content as a frozen snapshot to `artifacts/strat-originals/RHAISTRAT-NNNN.md` — same as Step 4 does for RFEs. This preserves the original state before any pipeline processing.

3. Write the file to `artifacts/strat-tasks/RHAISTRAT-NNNN.md` (use the Jira key as filename since it's a real ticket). Do NOT modify, reformat, or restructure any existing text from the RHAISTRAT — preserve it character-for-character and append the pipeline sections:

```markdown
## Business Need (from RFE)
<Description from the RHAISTRAT issue — VERBATIM, character-for-character. The STRAT may have been edited by humans after cloning from the RFE. Those edits are valuable — do NOT rewrite, paraphrase, or clean up the text.>

## Strategy (AI Generated by Agentic SDLC Pipeline)
<!-- DO NOT manually modify this section. It is generated and maintained by the pipeline. -->
<!-- Use the Staff Engineer Input section below to provide corrections or guidance. -->
<!-- To be filled by /strategy-refine -->

## Staff Engineer Input
<!-- HIGH-PRIORITY: Content here is used as primary guidance during strategy refinement. -->
<!-- Add technical corrections, architectural direction, component preferences, or domain expertise. -->
<!-- Write it using declarative, cumulative form; policy and statement that shall always be valid in any iteration of the STRAT Refinement -->
<!-- This input takes priority over architecture context and removed-context when they conflict. -->
<!-- After review: address findings below, then remove the needs_attention label from Jira. -->
```

4. Set frontmatter:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/frontmatter.py set artifacts/strat-tasks/RHAISTRAT-NNNN.md \
    strat_id=RHAISTRAT-NNNN \
    title="<title from Jira>" \
    source_rfe=RHAIRFE-NNNN \
    jira_key=RHAISTRAT-NNNN \
    priority=<priority from Jira> \
    status=Draft
```

5. Print `[IMPORT] RHAISTRAT-NNNN imported (cloned from RHAIRFE-NNNN)` for each imported STRAT.

### Path B: No Cloners link (no existing STRAT — create new)

No existing STRAT found. Clone the RFE into RHAISTRAT (Step 3), then create the local stub.

**If not in dry-run mode**, clone first using Step 3, then use the returned RHAISTRAT key as the filename:

```bash
STRAT_KEY=$(python3 scripts/clone_issue.py RHAIRFE-NNNN --target-project RHAISTRAT --issue-type Feature)
echo "[CLONE] $STRAT_KEY cloned from RHAIRFE-NNNN"
```

**If in dry-run mode**, skip cloning and use `STRAT-NNN.md` naming with `jira_key=null`.

1. Write the file to `artifacts/strat-tasks/STRAT-NNN.md` (dry-run) or `artifacts/strat-tasks/RHAISTRAT-NNNN.md` (after Jira clone). Do NOT modify, reformat, or restructure the RFE text — copy it character-for-character and append the pipeline sections:

```markdown
## Business Need (from RFE)
<Full content copied VERBATIM from the source RFE — this is fixed input for strategy refinement>

## Strategy (AI Generated by Agentic SDLC Pipeline)
<!-- DO NOT manually modify this section. It is generated and maintained by the pipeline. -->
<!-- Use the Staff Engineer Input section below to provide corrections or guidance. -->
<!-- To be filled by /strategy-refine -->

## Staff Engineer Input
<!-- HIGH-PRIORITY: Content here is used as primary guidance during strategy refinement. -->
<!-- Add technical corrections, architectural direction, component preferences, or domain expertise. -->
<!-- Write it using declarative, cumulative form; policy and statement that shall always be valid in any iteration of the STRAT Refinement -->
<!-- This input takes priority over architecture context and removed-context when they conflict. -->
<!-- After review: address findings below, then remove the needs_attention label from Jira. -->
```

2. Set frontmatter:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/frontmatter.py set artifacts/strat-tasks/<filename>.md \
    strat_id=<strat_id> \
    title="<title>" \
    source_rfe=<source_rfe_id> \
    jira_key=<RHAISTRAT_key_or_null> \
    priority=<priority> \
    status=Draft
```

Use `jira_key=null` if Jira cloning was not done (dry-run mode).

## Step 6: Apply Labels

If not in dry-run mode and a RHAISTRAT was created or imported (i.e., `jira_key` is not null), add the provenance label:

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from jira_utils import add_labels, require_env
s, u, t = require_env()
add_labels(s, u, t, 'RHAISTRAT-NNNN', ['strat-creator-auto-created'])
"
```

Print `[LABEL] strat-creator-auto-created added to RHAISTRAT-NNNN`.

## Step 7: Write Artifacts

If Jira cloning was done, write `artifacts/strat-tickets.md`:

```markdown
# RHAISTRAT Tickets

| RFE Source | STRAT Key | Title | Priority | URL |
|------------|-----------|-------|----------|-----|
| RHAIRFE-NNNN | RHAISTRAT-NNNN | ... | Major | https://redhat.atlassian.net/browse/RHAISTRAT-NNNN |
```

## Step 7: Next Steps

Tell the user:
- Strategy stubs created in `artifacts/strat-tasks/`
- Run `/strategy-refine` to add the HOW (technical approach, dependencies, components, non-functionals)
- If Jira cloning was skipped, complete the manual cloning first using `artifacts/strat-jira-guide.md`

$ARGUMENTS

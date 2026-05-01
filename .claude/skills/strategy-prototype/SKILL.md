---
name: strategy-prototype
description: Generate a clickable prototype from a strategy's RFE. Supports standalone HTML (Decision Kit) or codebase-grounded prototypes against a real product repo.
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent
---

You are generating a prototype to make a strategy's proposed experience tangible before engineering commits. This uses the prototype-creator tool to produce clickable prototypes from RFE user stories.

## Input

`$ARGUMENTS` must contain a RHAISTRAT key (e.g., `RHAISTRAT-1520`). If no key is provided, ask the user for one.

Optional flags in `$ARGUMENTS`:
- `--workspace=<git URL or local path>` — a product codebase to ground the prototype in (GitHub or GitLab). When omitted, generates standalone HTML.
- `--fidelity=low|medium|high` — prototype detail level (default: `medium`)
- `--mode=auto|decide` — `decide` stops at each design decision for human input; `auto` lets the AI choose (default: `decide`)

## Step 1: Read Strategy and RFE Context

Read the strategy file — check `local/strat-tasks/` first, then `artifacts/strat-tasks/`. If neither exists, tell the user to run `/strategy-pull` or `/strategy-create` first and stop.

Read the frontmatter to get `source_rfe`:

```bash
python3 scripts/frontmatter.py read <strategy-file-path>
```

Read the RFE original from `local/strat-originals/` or `artifacts/strat-originals/` (matching the source_rfe key). This provides the user stories and acceptance criteria that drive prototype generation.

## Step 2: UI Detection

Scan the strategy document and RFE original for UI-related indicators. Look for keywords and phrases including but not limited to: dashboard, user interface, UI, GUI, graphical, visualization, display, page, screen, form, modal, dialog, navigation, menu, sidebar, panel, wizard, table view, card view, layout, notification, alert, button, front-end, frontend, web interface, web console, monitoring view, configuration page, settings, workflow editor, drag and drop.

**If UI indicators are found:** Tell the user this strategy has UI components and is a good candidate for prototyping. Continue to Step 3.

**If NO UI indicators are found:** Warn the user: "This strategy doesn't appear to have UI components. You can still generate a prototype — Decision Kit can produce visual aids for any strategy, including architecture diagrams and workflow visualizations. Continue?" If the user declines, stop.

## Step 3: Bootstrap Prototype Creator

```bash
bash scripts/bootstrap-prototype-creator.sh
```

If this fails, tell the user to check network access (the script clones from GitHub) and stop.

## Step 4: Offer Prototype Options

Present the user with two options:

**(a) Standalone HTML prototype** — No codebase needed. Uses Decision Kit and PatternFly components to generate self-contained HTML screens. Good for visualizing the experience quickly, even for strategies without an existing product codebase.

**(b) Codebase-grounded prototype** — Provide a git URL (GitHub or GitLab) or local path to a real product repo. Prototype-creator analyzes the existing stack (framework, components, routing) and generates prototype files that match the product's technology and patterns.

If `--workspace` was already provided in `$ARGUMENTS`, skip this prompt and use option (b) with the provided URL.

If the user picks (b) and hasn't provided a workspace, ask for the git URL or local path.

## Step 5: Prepare Output Directory

```bash
mkdir -p local/prototypes/<RHAISTRAT-KEY>
```

## Step 6: Generate Prototype

Read the prototype-create skill instructions:

```bash
cat .context/prototype-creator/.claude/skills/prototype-create/SKILL.md
```

Spawn a background agent (using the Agent tool, `run_in_background: true`) with the following prompt. Substitute all placeholders:

```
You are generating a prototype. Follow the prototype-create instructions below, with these overrides:

INSTRUCTIONS:
<paste the content of .context/prototype-creator/.claude/skills/prototype-create/SKILL.md>

OVERRIDES:
- RFE source: Read the RFE content directly from {RFE_FILE_PATH} — do NOT fetch from Jira.
- Strategy context: Read {STRATEGY_FILE_PATH} for the full strategy (the HOW) to inform prototype decisions.
- Fidelity: {FIDELITY}
- Mode: {MODE}
- Workspace: {WORKSPACE_OR_NONE}
- Output directory: local/prototypes/{RHAISTRAT_KEY}/
- Decisions directory: local/prototypes/{RHAISTRAT_KEY}/.decisions/
- Skip all Jira writes — this is a local prototype generation.
- Design system context is at .context/prototype-creator/.context/design-system/ if available.
- Decision-kit context is at .context/prototype-creator/.context/decision-kit/ if available.
```

Wait for the agent to complete.

## Step 7: Summarize Results

After the agent completes, list the generated files:

```bash
find local/prototypes/<RHAISTRAT-KEY>/ -type f | head -30
```

Tell the user:

1. **What was generated** — list the key files (HTML screens, metadata, decision artifacts)
2. **How to view it** — for standalone HTML, they can open the index file directly in a browser. For workspace mode, point them to the changeset.
3. **Decision artifacts** — if `--mode=decide` was used, mention that design decisions are recorded in `local/prototypes/<KEY>/.decisions/` and can be reviewed or replayed.
4. **Next steps** — "Continue with `/strategy-refine` and `/strategy-review` to iterate on the strategy. The prototype is saved in `local/prototypes/` for reference during review."

$ARGUMENTS

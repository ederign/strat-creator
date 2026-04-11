# Strat Creator

Skills for creating, refining, and reviewing strategy documents from approved RFEs.

## Artifact Conventions

All skills read from and write to the `artifacts/` directory.

```
artifacts/
  strat-tasks/              # Strategy files with YAML frontmatter
    STRAT-001.md
    RHAISTRAT-400.md
  strat-reviews/            # Per-strategy review files with YAML frontmatter
    STRAT-001-review.md
    RHAISTRAT-400-review.md
  strat-originals/          # Original RFE snapshots at time of strategy creation
    RHAIRFE-1595.md
  strat-tickets.md          # RHAISTRAT ticket mapping after cloning
```

### Frontmatter

All task and review files use YAML frontmatter for structured metadata. Skills must use `scripts/frontmatter.py` to read schemas, set fields, and read validated data — never write YAML by hand.

```bash
# Get schema for a file type
python3 scripts/frontmatter.py schema strat-task
python3 scripts/frontmatter.py schema strat-review

# Set/update frontmatter on a file
python3 scripts/frontmatter.py set <path> field=value field=value ...

# Read validated frontmatter as JSON
python3 scripts/frontmatter.py read <path>
```

### State Persistence

Long-running skills use `scripts/state.py` to persist state to `tmp/` files so it survives context compression.

```bash
python3 scripts/state.py init <file> key=value ...
python3 scripts/state.py set <file> key=value ...
python3 scripts/state.py set-default <file> key=value ...
python3 scripts/state.py read <file>
python3 scripts/state.py write-ids <file> ID ...
python3 scripts/state.py read-ids <file>
python3 scripts/state.py timestamp
python3 scripts/state.py clean
```

### File Naming

- **Cloned from Jira**: Use Jira key as filename (e.g., `RHAISTRAT-400.md`)
- **Local pre-submission**: Use `STRAT-NNN.md` naming
- **On submit**: `STRAT-NNN.md` files are renamed to `RHAISTRAT-NNNN.md`

## Jira Integration

### Read Operations

Read operations support two modes:

1. **Atlassian MCP server** (preferred when available)
2. **REST API fallback** via `python3 scripts/fetch_issue.py` using `JIRA_SERVER`/`JIRA_USER`/`JIRA_TOKEN` env vars

### Write Operations

Not yet implemented for strat-creator. Strategy submission to Jira will be added as a future skill.

## Jira Field Mappings

### RHAISTRAT Project
- **Project**: `RHAISTRAT`
- **Issue Type**: `Feature`
- **Clone link type**: `Cloners` (outward: "clones", inward: "is cloned by")
- **Related link type**: `Related`

### RHAIRFE Project (source — read only)
- **Project**: `RHAIRFE`
- **Issue Type**: `Feature Request`

## Architecture Context

Strategy skills fetch architecture context from opendatahub-io/architecture-context into `.context/architecture-context/`. Used during refinement and review to ground feedback in real platform architecture.

```bash
bash scripts/fetch-architecture-context.sh
```

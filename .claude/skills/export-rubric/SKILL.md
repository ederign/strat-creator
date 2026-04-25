---
name: export-rubric
description: Export the assess-strat scoring rubric to artifacts/strat-rubric.md in the current working directory.
user-invocable: true
allowed-tools: Read, Write, Bash
---

## Usage
```
/export-rubric
```

## Instructions

### Steps

1. Run `python3 ${CLAUDE_SKILL_DIR}/scripts/export_rubric.py` from the current working directory.
2. Confirm the file was written and print its path.

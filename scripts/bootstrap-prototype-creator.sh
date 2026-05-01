#!/bin/bash
# Ensures the prototype-creator tool is available locally.
# Safe to run multiple times — clones on first run, pulls updates after.

if [ -n "${PROTOTYPE_SKIP_BOOTSTRAP:-}" ]; then
  echo "PROTOTYPE_SKIP_BOOTSTRAP set - skipping prototype-creator bootstrapping"
  exit 0
fi

CONTEXT_DIR=".context/prototype-creator"
CREATE_SKILL="$CONTEXT_DIR/.claude/skills/prototype-create/SKILL.md"

if [ ! -d "$CONTEXT_DIR" ]; then
  git clone https://github.com/andybraren/prototype-creator "$CONTEXT_DIR" 2>&1
else
  git -C "$CONTEXT_DIR" pull --ff-only 2>&1 || echo "WARN: prototype-creator pull failed, using cached version" >&2
fi

if [ ! -f "$CREATE_SKILL" ]; then
  echo "ERROR: prototype-create skill not found at $CREATE_SKILL after bootstrap" >&2
  exit 1
fi

# Bootstrap prototype-creator's own dependencies (decision-kit, design system context)
if [ -f "$CONTEXT_DIR/scripts/bootstrap-decision-kit.sh" ]; then
  bash "$CONTEXT_DIR/scripts/bootstrap-decision-kit.sh" 2>&1 || echo "WARN: decision-kit bootstrap failed" >&2
fi

if [ -f "$CONTEXT_DIR/scripts/fetch-design-system-context.sh" ]; then
  bash "$CONTEXT_DIR/scripts/fetch-design-system-context.sh" 2>&1 || echo "WARN: design system context fetch failed" >&2
fi

echo "prototype-creator bootstrapped at $CONTEXT_DIR"

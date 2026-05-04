#!/bin/bash
# Ensures the assess-strat plugin is available locally.
# Safe to run multiple times — clones on first run, pulls updates after.
#
# Usage:
#   bash scripts/bootstrap-assess-strat.sh                  # clone from remote (default)
#   bash scripts/bootstrap-assess-strat.sh /path/to/local   # use local checkout via symlink

if [ -n "${STRAT_SKIP_BOOTSTRAP:-}" ]; then
  echo "STRAT_SKIP_BOOTSTRAP set - skipping dependency bootstrapping step"
  exit 0
fi

CONTEXT_DIR=".context/assess-strat"
RUBRIC_FILE="$CONTEXT_DIR/scripts/agent_prompt.md"

if [ -n "$1" ]; then
  LOCAL_PATH="$1"
  if [ ! -d "$LOCAL_PATH" ]; then
    echo "Local assess-strat path does not exist: $LOCAL_PATH"
    exit 1
  fi
  rm -rf "$CONTEXT_DIR"
  mkdir -p "$(dirname "$CONTEXT_DIR")"
  ln -sf "$(cd "$LOCAL_PATH" && pwd)" "$CONTEXT_DIR"
  echo "assess-strat linked to local path: $LOCAL_PATH"
elif [ ! -d "$CONTEXT_DIR" ]; then
  git clone https://github.com/ederign/assess-strat "$CONTEXT_DIR" 2>&1
else
  git -C "$CONTEXT_DIR" pull --ff-only 2>&1 || echo "WARN: assess-strat pull failed, using cached version" >&2
fi

# Validate that the rubric file exists after cloning
if [ ! -f "$RUBRIC_FILE" ]; then
  echo "ERROR: Rubric file not found at $RUBRIC_FILE after bootstrap" >&2
  exit 1
fi

# Copy all skills from the plugin
for skill_dir in "$CONTEXT_DIR"/skills/*/; do
  skill_name=$(basename "$skill_dir")
  target=".claude/skills/$skill_name"
  mkdir -p "$target"
  cp "$skill_dir/SKILL.md" "$target/SKILL.md"
done

# Patch PLUGIN_ROOT in copied skill — the upstream SKILL.md resolves it
# relative to its own location, which breaks when copied to .claude/skills/.
# Replace the resolution paragraph with a hardcoded path.
ASSESS_SKILL=".claude/skills/assess-strat/SKILL.md"
if [ -f "$ASSESS_SKILL" ]; then
  sed -i.bak "s|When this skill is invoked, resolve the absolute path of the plugin root directory. This SKILL.md is at \`<plugin_root>/skills/assess-strat/SKILL.md\` — the plugin root is two levels up. Determine this path once at the start and use it for all script and file references. Store it as \`{PLUGIN_ROOT}\` for substitution into commands and agent prompts.|The plugin root is \`.context/assess-strat\`. Use this as \`{PLUGIN_ROOT}\` for all script and file references.|" "$ASSESS_SKILL"
  rm -f "$ASSESS_SKILL.bak"
fi

# Install agent definitions
if [ -d "$CONTEXT_DIR/agents" ]; then
  mkdir -p .claude/agents
  cp "$CONTEXT_DIR"/agents/*.md .claude/agents/
fi

# Export rubric to artifacts
python3 "$CONTEXT_DIR/scripts/export_rubric.py" 2>/dev/null || true

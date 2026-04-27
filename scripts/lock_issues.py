#!/usr/bin/env python3
"""Issue-level locking via Jira labels for concurrent pipeline jobs.

Applies/removes `strat-creator-processing` to prevent two pipeline jobs
from processing the same RFE simultaneously.

Commands:
    lock RHAIRFE-1234 [...]
        Fetch labels, validate guards, apply strat-creator-processing.
        Single key: exit 1 if blocked. Multiple keys: skip blocked,
        print locked subset to stdout.

    unlock RHAIRFE-1234 [...]
        Remove strat-creator-processing.

    lock-strat RHAISTRAT-1500
        Resolve STRAT→RFE via Cloners link, validate STRAT guards
        (must have strat-creator-auto-created, must NOT have
        strat-creator-needs-attention or strat-creator-human-sign-off),
        then lock the RFE. Fails if no Cloners link to RHAIRFE exists.

    unlock-strat RHAISTRAT-1500
        Resolve STRAT→RFE via Cloners link, remove lock from RFE.

Exit codes:
    0 — success
    1 — blocked (single key) or no keys locked (batch)
    2 — error (missing env vars, API failure, invalid STRAT)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from jira_utils import (
    add_labels,
    get_issue,
    remove_labels,
    require_env,
)

PROCESSING_LABEL = "strat-creator-processing"

BLOCKING_LABELS = frozenset({
    "strat-creator-processing",
    "strat-creator-needs-attention",
    "strat-creator-human-sign-off",
})

STRAT_REQUIRED_LABEL = "strat-creator-auto-created"

STRAT_BLOCKING_LABELS = frozenset({
    "strat-creator-needs-attention",
    "strat-creator-human-sign-off",
})


def _get_labels(server, user, token, key):
    """Fetch the labels for a Jira issue."""
    data = get_issue(server, user, token, key, fields=["labels"])
    return set(data.get("fields", {}).get("labels", []))


def _resolve_strat_to_rfe(server, user, token, strat_key):
    """Resolve a RHAISTRAT key to its linked RHAIRFE via Cloners links.

    Returns the first RHAIRFE key found, or None.
    """
    data = get_issue(server, user, token, strat_key,
                     fields=["issuelinks"])
    links = data.get("fields", {}).get("issuelinks", [])
    for link in links:
        if link.get("type", {}).get("name") != "Cloners":
            continue
        for direction in ("outwardIssue", "inwardIssue"):
            issue = link.get(direction, {})
            key = issue.get("key", "")
            if key.startswith("RHAIRFE-"):
                return key
    return None


def lock(server, user, token, keys):
    """Lock RFE(s) by applying strat-creator-processing label.

    For a single key: fails (returns 1) if any blocking label is present.
    For multiple keys: skips blocked ones, prints locked subset to stdout.
    Returns (exit_code, locked_keys).
    """
    locked = []
    batch_mode = len(keys) > 1

    for key in keys:
        labels = _get_labels(server, user, token, key)
        blocked_by = labels & BLOCKING_LABELS
        if blocked_by:
            msg = (f"BLOCKED {key} — has label(s): "
                   f"{', '.join(sorted(blocked_by))}")
            if batch_mode:
                print(msg, file=sys.stderr)
                continue
            else:
                print(msg, file=sys.stderr)
                return 1, []

        add_labels(server, user, token, key, [PROCESSING_LABEL])
        locked.append(key)
        print(f"LOCKED {key}", file=sys.stderr)

    # Print locked keys to stdout for capture by CI script
    print(" ".join(locked))

    if not locked:
        print("No keys locked", file=sys.stderr)
        return 1, []

    return 0, locked


def unlock(server, user, token, keys):
    """Unlock RFE(s) by removing strat-creator-processing label."""
    for key in keys:
        remove_labels(server, user, token, key, [PROCESSING_LABEL])
        print(f"UNLOCKED {key}", file=sys.stderr)
    return 0


def lock_strat(server, user, token, strat_key):
    """Lock via STRAT key: resolve to RFE, validate STRAT guards, lock RFE."""
    # Validate STRAT labels
    strat_labels = _get_labels(server, user, token, strat_key)
    if STRAT_REQUIRED_LABEL not in strat_labels:
        print(f"ERROR {strat_key} — missing required label: "
              f"{STRAT_REQUIRED_LABEL}. Not created by our pipeline.",
              file=sys.stderr)
        return 2

    strat_blocked = strat_labels & STRAT_BLOCKING_LABELS
    if strat_blocked:
        print(f"BLOCKED {strat_key} — has label(s): "
              f"{', '.join(sorted(strat_blocked))}",
              file=sys.stderr)
        return 1

    # Resolve STRAT → RFE
    rfe_key = _resolve_strat_to_rfe(server, user, token, strat_key)
    if not rfe_key:
        print(f"ERROR {strat_key} — no Cloners link to RHAIRFE found. "
              f"Not created by our pipeline.", file=sys.stderr)
        return 2

    # Lock the RFE
    exit_code, _ = lock(server, user, token, [rfe_key])
    return exit_code


def unlock_strat(server, user, token, strat_key):
    """Unlock via STRAT key: resolve to RFE, remove lock from RFE."""
    rfe_key = _resolve_strat_to_rfe(server, user, token, strat_key)
    if not rfe_key:
        print(f"ERROR {strat_key} — no Cloners link to RHAIRFE found.",
              file=sys.stderr)
        return 2
    return unlock(server, user, token, [rfe_key])


def main():
    if len(sys.argv) < 3:
        print("Usage: lock_issues.py <command> <key> [key ...]",
              file=sys.stderr)
        print("Commands: lock, unlock, lock-strat, unlock-strat",
              file=sys.stderr)
        return 2

    command = sys.argv[1]
    keys = sys.argv[2:]

    server, user, token = require_env()
    if not all([server, user, token]):
        print("Error: JIRA_SERVER, JIRA_USER, JIRA_TOKEN required.",
              file=sys.stderr)
        return 2

    if command == "lock":
        exit_code, _ = lock(server, user, token, keys)
        return exit_code
    elif command == "unlock":
        return unlock(server, user, token, keys)
    elif command == "lock-strat":
        if len(keys) != 1:
            print("lock-strat takes exactly one STRAT key", file=sys.stderr)
            return 2
        return lock_strat(server, user, token, keys[0])
    elif command == "unlock-strat":
        if len(keys) != 1:
            print("unlock-strat takes exactly one STRAT key", file=sys.stderr)
            return 2
        return unlock_strat(server, user, token, keys[0])
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

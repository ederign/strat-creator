"""Integration tests for clone_issue.py against jira-emulator."""
import json
import os
import subprocess
import sys

import pytest


SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "clone_issue.py")


def _env(jira):
    return {
        **os.environ,
        "JIRA_SERVER": jira.url,
        "JIRA_USER": "admin",
        "JIRA_TOKEN": "admin",
    }


def _run(jira, args, env_override=None):
    env = env_override if env_override is not None else _env(jira)
    return subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True, text=True, env=env,
    )


class TestCloneIssue:

    def test_clones_issue_with_summary_priority_and_link(self, jira):
        jira.create("RHAIRFE-1000", "GPU sharing for notebooks",
                     "Enable time-sliced GPU sharing.")

        result = _run(jira, ["RHAIRFE-1000", "--target-project", "RHAISTRAT"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

        new_key = result.stdout.strip()
        assert new_key.startswith("RHAISTRAT-"), f"unexpected key: {new_key}"

        clone = jira.get(new_key)
        assert clone["fields"]["summary"] == "GPU sharing for notebooks"

        source = jira.get("RHAIRFE-1000")
        source_priority = source["fields"].get("priority")
        clone_priority = clone["fields"].get("priority")
        if isinstance(source_priority, dict) and isinstance(clone_priority, dict):
            assert clone_priority["name"] == source_priority["name"]

        links = clone["fields"].get("issuelinks", [])
        cloner_links = [
            lk for lk in links
            if lk.get("type", {}).get("name") == "Cloners"
        ]
        assert len(cloner_links) >= 1
        linked_keys = []
        for lk in cloner_links:
            for direction in ("inwardIssue", "outwardIssue"):
                issue = lk.get(direction)
                if issue:
                    linked_keys.append(issue["key"])
        assert "RHAIRFE-1000" in linked_keys

    def test_labels_are_copied_to_clone(self, jira):
        jira.create("RHAIRFE-1001", "Model serving autoscaler",
                     "Autoscale model serving pods.",
                     labels=["strat-creator-3.5", "tech-reviewed"])

        result = _run(jira, ["RHAIRFE-1001", "--target-project", "RHAISTRAT"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

        new_key = result.stdout.strip()
        clone = jira.get(new_key)
        clone_labels = clone["fields"].get("labels", [])
        assert "strat-creator-3.5" in clone_labels
        assert "tech-reviewed" in clone_labels

    def test_missing_env_vars_exits_with_code_2(self, jira):
        env = {k: v for k, v in os.environ.items()
               if k not in ("JIRA_SERVER", "JIRA_USER", "JIRA_TOKEN")}

        result = _run(jira, ["RHAIRFE-1000", "--target-project", "RHAISTRAT"],
                       env_override=env)
        assert result.returncode == 2

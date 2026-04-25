"""Integration tests for fetch_issue.py against jira-emulator."""
import json
import os
import subprocess
import sys

import pytest


SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "fetch_issue.py")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _env(jira):
    return {
        **os.environ,
        "JIRA_SERVER": jira.url,
        "JIRA_USER": "admin",
        "JIRA_TOKEN": "admin",
    }


def _run(jira, args, env_override=None, cwd=None):
    env = env_override if env_override is not None else _env(jira)
    return subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True, text=True, env=env, cwd=cwd,
    )


class TestFetchIssue:

    def test_fetches_issue_as_json(self, jira):
        jira.create("RHAIRFE-2000", "Pipeline autoscaling",
                     "Scale data pipelines based on queue depth.")

        result = _run(jira, ["RHAIRFE-2000"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

        output = json.loads(result.stdout)
        assert output["key"] == "RHAIRFE-2000"
        assert output["fields"]["summary"] == "Pipeline autoscaling"

    def test_markdown_mode_converts_description(self, jira):
        jira.create("RHAIRFE-2001", "Feature with description",
                     "This is the **description** content.")

        result = _run(jira, ["RHAIRFE-2001", "--markdown"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

        output = json.loads(result.stdout)
        desc = output["fields"].get("description", "")
        assert isinstance(desc, str)
        assert "description" in desc.lower()

    def test_fields_filter_limits_output(self, jira):
        jira.create("RHAIRFE-2002", "Filtered fields test",
                     "Full description here.",
                     labels=["alpha", "beta"])

        result = _run(jira, ["RHAIRFE-2002", "--fields", "summary,labels"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

        output = json.loads(result.stdout)
        assert "summary" in output["fields"]
        assert "labels" in output["fields"]
        assert "description" not in output["fields"]
        assert "priority" not in output["fields"]
        assert "status" not in output["fields"]

    def test_missing_credentials_exits_with_error(self, jira):
        env = {k: v for k, v in os.environ.items()
               if k not in ("JIRA_SERVER", "JIRA_USER", "JIRA_TOKEN")}

        result = _run(jira, ["RHAIRFE-2000"], env_override=env)
        assert result.returncode != 0

    def test_fetch_all_writes_artifact_files(self, jira, art_dir):
        jira.create("RHAIRFE-2003", "Fetch-all target",
                     "Description for fetch-all test.")

        artifacts = str(art_dir / "artifacts")
        result = _run(jira, ["RHAIRFE-2003", "--fetch-all", artifacts],
                       cwd=PROJECT_ROOT)
        assert result.returncode == 0, f"stderr: {result.stderr}"

        task_file = os.path.join(artifacts, "rfe-tasks", "RHAIRFE-2003.md")
        assert os.path.isfile(task_file)

        orig_file = os.path.join(artifacts, "rfe-originals", "RHAIRFE-2003.md")
        assert os.path.isfile(orig_file)

        comments_file = os.path.join(
            artifacts, "rfe-tasks", "RHAIRFE-2003-comments.md")
        assert os.path.isfile(comments_file)

    def test_fetch_all_missing_credentials_exits_2(self, jira, art_dir):
        env = {k: v for k, v in os.environ.items()
               if k not in ("JIRA_SERVER", "JIRA_USER", "JIRA_TOKEN")}

        artifacts = str(art_dir / "artifacts")
        result = _run(jira, ["RHAIRFE-9999", "--fetch-all", artifacts],
                       env_override=env)
        assert result.returncode == 2

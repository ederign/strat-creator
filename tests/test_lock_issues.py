"""Integration tests for lock_issues.py against jira-emulator."""
import json
import os
import subprocess
import sys

import pytest


SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "scripts", "lock_issues.py")


def _env(jira):
    return {
        **os.environ,
        "JIRA_SERVER": jira.url,
        "JIRA_USER": "admin",
        "JIRA_TOKEN": "admin",
    }


def _run(jira, args):
    return subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True, text=True, env=_env(jira),
    )


def _get_labels(jira, key):
    data = jira.get(key)
    return set(data.get("fields", {}).get("labels", []))


def _create_cloners_link(jira, strat_key, rfe_key):
    jira.request("POST", "/rest/api/3/issueLink", {
        "type": {"name": "Cloners"},
        "inwardIssue": {"key": strat_key},
        "outwardIssue": {"key": rfe_key},
    })


class TestLock:

    def test_lock_single_rfe(self, jira):
        jira.create("RHAIRFE-5000", "Test RFE", "Description.")

        result = _run(jira, ["lock", "RHAIRFE-5000"])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "LOCKED RHAIRFE-5000" in result.stderr

        labels = _get_labels(jira, "RHAIRFE-5000")
        assert "strat-creator-processing" in labels

    def test_lock_already_locked_single_fails(self, jira):
        jira.create("RHAIRFE-5001", "Already locked",
                     "Description.",
                     labels=["strat-creator-processing"])

        result = _run(jira, ["lock", "RHAIRFE-5001"])
        assert result.returncode == 1
        assert "BLOCKED" in result.stderr
        assert "strat-creator-processing" in result.stderr

    def test_lock_needs_attention_single_fails(self, jira):
        jira.create("RHAIRFE-5002", "Needs attention RFE", "Description.")
        jira.create("RHAISTRAT-5002", "Strategy", "Description.",
                     labels=["strat-creator-needs-attention"])
        # The lock checks the RFE's own labels, not the STRAT's.
        # For single-rfe, the RFE itself needs the blocking label.
        # Let's test with the blocking label on the RFE directly.
        jira.create("RHAIRFE-5003", "RFE with blocking label",
                     "Description.",
                     labels=["strat-creator-needs-attention"])

        result = _run(jira, ["lock", "RHAIRFE-5003"])
        assert result.returncode == 1
        assert "BLOCKED" in result.stderr

    def test_lock_human_signoff_single_fails(self, jira):
        jira.create("RHAIRFE-5004", "Signed off RFE",
                     "Description.",
                     labels=["strat-creator-human-sign-off"])

        result = _run(jira, ["lock", "RHAIRFE-5004"])
        assert result.returncode == 1
        assert "BLOCKED" in result.stderr

    def test_lock_batch_skips_blocked(self, jira):
        jira.create("RHAIRFE-5010", "Good RFE A", "Description.")
        jira.create("RHAIRFE-5011", "Locked RFE B",
                     "Description.",
                     labels=["strat-creator-processing"])
        jira.create("RHAIRFE-5012", "Good RFE C", "Description.")

        result = _run(jira, ["lock",
                              "RHAIRFE-5010", "RHAIRFE-5011", "RHAIRFE-5012"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

        # stdout contains the locked subset
        locked = result.stdout.strip().split()
        assert "RHAIRFE-5010" in locked
        assert "RHAIRFE-5011" not in locked
        assert "RHAIRFE-5012" in locked

        # stderr has the BLOCKED message
        assert "BLOCKED RHAIRFE-5011" in result.stderr

    def test_lock_batch_all_blocked(self, jira):
        jira.create("RHAIRFE-5020", "Blocked A",
                     "Description.",
                     labels=["strat-creator-processing"])
        jira.create("RHAIRFE-5021", "Blocked B",
                     "Description.",
                     labels=["strat-creator-needs-attention"])

        result = _run(jira, ["lock", "RHAIRFE-5020", "RHAIRFE-5021"])
        assert result.returncode == 1
        assert "No keys locked" in result.stderr


class TestUnlock:

    def test_unlock_removes_processing_label(self, jira):
        jira.create("RHAIRFE-5100", "Locked RFE",
                     "Description.",
                     labels=["strat-creator-processing", "strat-creator-3.5"])

        result = _run(jira, ["unlock", "RHAIRFE-5100"])
        assert result.returncode == 0
        assert "UNLOCKED RHAIRFE-5100" in result.stderr

        labels = _get_labels(jira, "RHAIRFE-5100")
        assert "strat-creator-processing" not in labels
        assert "strat-creator-3.5" in labels

    def test_unlock_multiple(self, jira):
        jira.create("RHAIRFE-5101", "Locked A",
                     "Description.",
                     labels=["strat-creator-processing"])
        jira.create("RHAIRFE-5102", "Locked B",
                     "Description.",
                     labels=["strat-creator-processing"])

        result = _run(jira, ["unlock", "RHAIRFE-5101", "RHAIRFE-5102"])
        assert result.returncode == 0

        assert "strat-creator-processing" not in _get_labels(
            jira, "RHAIRFE-5101")
        assert "strat-creator-processing" not in _get_labels(
            jira, "RHAIRFE-5102")


class TestLockStrat:

    def test_lock_strat_success(self, jira):
        jira.create("RHAIRFE-5200", "Source RFE", "Description.")
        jira.create("RHAISTRAT-5200", "Strategy",
                     "Description.",
                     labels=["strat-creator-auto-created",
                             "strat-creator-rubric-pass"])
        _create_cloners_link(jira, "RHAISTRAT-5200", "RHAIRFE-5200")

        result = _run(jira, ["lock-strat", "RHAISTRAT-5200"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

        labels = _get_labels(jira, "RHAIRFE-5200")
        assert "strat-creator-processing" in labels

    def test_lock_strat_missing_auto_created_fails(self, jira):
        jira.create("RHAIRFE-5201", "Source RFE", "Description.")
        jira.create("RHAISTRAT-5201", "Not our strategy",
                     "Description.",
                     labels=["strat-creator-rubric-pass"])
        _create_cloners_link(jira, "RHAISTRAT-5201", "RHAIRFE-5201")

        result = _run(jira, ["lock-strat", "RHAISTRAT-5201"])
        assert result.returncode == 2
        assert "strat-creator-auto-created" in result.stderr

    def test_lock_strat_needs_attention_fails(self, jira):
        jira.create("RHAIRFE-5202", "Source RFE", "Description.")
        jira.create("RHAISTRAT-5202", "Needs attention",
                     "Description.",
                     labels=["strat-creator-auto-created",
                             "strat-creator-needs-attention"])
        _create_cloners_link(jira, "RHAISTRAT-5202", "RHAIRFE-5202")

        result = _run(jira, ["lock-strat", "RHAISTRAT-5202"])
        assert result.returncode == 1
        assert "BLOCKED" in result.stderr
        assert "strat-creator-needs-attention" in result.stderr

    def test_lock_strat_human_signoff_fails(self, jira):
        jira.create("RHAIRFE-5203", "Source RFE", "Description.")
        jira.create("RHAISTRAT-5203", "Signed off",
                     "Description.",
                     labels=["strat-creator-auto-created",
                             "strat-creator-human-sign-off"])
        _create_cloners_link(jira, "RHAISTRAT-5203", "RHAIRFE-5203")

        result = _run(jira, ["lock-strat", "RHAISTRAT-5203"])
        assert result.returncode == 1
        assert "BLOCKED" in result.stderr

    def test_lock_strat_no_cloners_link_fails(self, jira):
        jira.create("RHAISTRAT-5204", "Orphan strategy",
                     "Description.",
                     labels=["strat-creator-auto-created"])

        result = _run(jira, ["lock-strat", "RHAISTRAT-5204"])
        assert result.returncode == 2
        assert "no Cloners link" in result.stderr

    def test_lock_strat_rfe_already_locked_fails(self, jira):
        jira.create("RHAIRFE-5205", "Locked RFE",
                     "Description.",
                     labels=["strat-creator-processing"])
        jira.create("RHAISTRAT-5205", "Strategy",
                     "Description.",
                     labels=["strat-creator-auto-created",
                             "strat-creator-rubric-pass"])
        _create_cloners_link(jira, "RHAISTRAT-5205", "RHAIRFE-5205")

        result = _run(jira, ["lock-strat", "RHAISTRAT-5205"])
        assert result.returncode == 1
        assert "BLOCKED" in result.stderr


class TestUnlockStrat:

    def test_unlock_strat_success(self, jira):
        jira.create("RHAIRFE-5300", "Locked RFE",
                     "Description.",
                     labels=["strat-creator-processing"])
        jira.create("RHAISTRAT-5300", "Strategy",
                     "Description.",
                     labels=["strat-creator-auto-created"])
        _create_cloners_link(jira, "RHAISTRAT-5300", "RHAIRFE-5300")

        result = _run(jira, ["unlock-strat", "RHAISTRAT-5300"])
        assert result.returncode == 0
        assert "UNLOCKED" in result.stderr

        labels = _get_labels(jira, "RHAIRFE-5300")
        assert "strat-creator-processing" not in labels

    def test_unlock_strat_no_cloners_link_fails(self, jira):
        jira.create("RHAISTRAT-5301", "Orphan",
                     "Description.",
                     labels=["strat-creator-auto-created"])

        result = _run(jira, ["unlock-strat", "RHAISTRAT-5301"])
        assert result.returncode == 2
        assert "no Cloners link" in result.stderr


class TestLockUnlockRoundtrip:

    def test_lock_then_unlock(self, jira):
        jira.create("RHAIRFE-5400", "Roundtrip RFE", "Description.")

        lock_result = _run(jira, ["lock", "RHAIRFE-5400"])
        assert lock_result.returncode == 0
        assert "strat-creator-processing" in _get_labels(
            jira, "RHAIRFE-5400")

        unlock_result = _run(jira, ["unlock", "RHAIRFE-5400"])
        assert unlock_result.returncode == 0
        assert "strat-creator-processing" not in _get_labels(
            jira, "RHAIRFE-5400")

        # Can lock again after unlock
        relock_result = _run(jira, ["lock", "RHAIRFE-5400"])
        assert relock_result.returncode == 0


class TestEdgeCases:

    def test_missing_env_vars(self, jira):
        env = {k: v for k, v in os.environ.items()
               if k not in ("JIRA_SERVER", "JIRA_USER", "JIRA_TOKEN")}
        result = subprocess.run(
            [sys.executable, SCRIPT, "lock", "RHAIRFE-9999"],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 2

    def test_no_args(self, jira):
        result = _run(jira, [])
        assert result.returncode == 2

    def test_unknown_command(self, jira):
        result = _run(jira, ["frobnicate", "RHAIRFE-9999"])
        assert result.returncode == 2

    def test_lock_strat_multiple_keys_rejected(self, jira):
        result = _run(jira, ["lock-strat", "RHAISTRAT-1", "RHAISTRAT-2"])
        assert result.returncode == 2
        assert "exactly one" in result.stderr

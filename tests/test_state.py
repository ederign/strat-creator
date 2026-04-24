import os
import re
import subprocess
import sys

import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "state.py")


def run_state(tmp_path, *args, check=True):
    """Run state.py as a subprocess inside tmp_path."""
    result = subprocess.run(
        [sys.executable, SCRIPT, *args],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"state.py {' '.join(args)} failed (rc={result.returncode}):\n"
            f"  stdout: {result.stdout}\n"
            f"  stderr: {result.stderr}"
        )
    return result


# ─── init ─────────────────────────────────────────────────────────────────────


class TestInit:

    def test_creates_file_with_key_value(self, tmp_path):
        run_state(tmp_path, "init", "tmp/config", "batch=01", "status=running")
        content = (tmp_path / "tmp" / "config").read_text()
        assert "batch: 01\n" in content
        assert "status: running\n" in content

    def test_creates_tmp_directory(self, tmp_path):
        run_state(tmp_path, "init", "tmp/state.cfg", "key=val")
        assert (tmp_path / "tmp").is_dir()

    def test_init_no_pairs(self, tmp_path):
        run_state(tmp_path, "init", "tmp/empty")
        assert (tmp_path / "tmp" / "empty").exists()
        assert (tmp_path / "tmp" / "empty").read_text() == ""

    def test_init_overwrites_existing(self, tmp_path):
        run_state(tmp_path, "init", "tmp/cfg", "a=1")
        run_state(tmp_path, "init", "tmp/cfg", "b=2")
        content = (tmp_path / "tmp" / "cfg").read_text()
        assert "a:" not in content
        assert "b: 2\n" in content


# ─── set ──────────────────────────────────────────────────────────────────────


class TestSet:

    def test_updates_existing_key(self, tmp_path):
        run_state(tmp_path, "init", "tmp/cfg", "count=0")
        run_state(tmp_path, "set", "tmp/cfg", "count=5")
        content = (tmp_path / "tmp" / "cfg").read_text()
        assert "count: 5\n" in content
        assert "count: 0" not in content

    def test_adds_new_key(self, tmp_path):
        run_state(tmp_path, "init", "tmp/cfg", "a=1")
        run_state(tmp_path, "set", "tmp/cfg", "b=2")
        content = (tmp_path / "tmp" / "cfg").read_text()
        assert "a: 1\n" in content
        assert "b: 2\n" in content

    def test_updates_and_adds_together(self, tmp_path):
        run_state(tmp_path, "init", "tmp/cfg", "x=old")
        run_state(tmp_path, "set", "tmp/cfg", "x=new", "y=fresh")
        content = (tmp_path / "tmp" / "cfg").read_text()
        assert "x: new\n" in content
        assert "y: fresh\n" in content
        assert "old" not in content

    def test_creates_file_if_missing(self, tmp_path):
        os.makedirs(tmp_path / "tmp")
        run_state(tmp_path, "set", "tmp/cfg", "k=v")
        assert (tmp_path / "tmp" / "cfg").exists()
        assert "k: v\n" in (tmp_path / "tmp" / "cfg").read_text()


# ─── set-default ──────────────────────────────────────────────────────────────


class TestSetDefault:

    def test_sets_when_not_present(self, tmp_path):
        run_state(tmp_path, "init", "tmp/cfg", "a=1")
        run_state(tmp_path, "set-default", "tmp/cfg", "b=2")
        content = (tmp_path / "tmp" / "cfg").read_text()
        assert "b: 2\n" in content

    def test_does_not_overwrite_existing(self, tmp_path):
        run_state(tmp_path, "init", "tmp/cfg", "cycle=3")
        run_state(tmp_path, "set-default", "tmp/cfg", "cycle=0")
        content = (tmp_path / "tmp" / "cfg").read_text()
        assert "cycle: 3\n" in content
        assert "cycle: 0" not in content

    def test_idempotent_for_counters(self, tmp_path):
        run_state(tmp_path, "init", "tmp/cfg", "count=7")
        run_state(tmp_path, "set-default", "tmp/cfg", "count=0")
        run_state(tmp_path, "set-default", "tmp/cfg", "count=0")
        content = (tmp_path / "tmp" / "cfg").read_text()
        assert content.count("count:") == 1
        assert "count: 7\n" in content

    def test_mixed_existing_and_new(self, tmp_path):
        run_state(tmp_path, "init", "tmp/cfg", "old=keep")
        run_state(tmp_path, "set-default", "tmp/cfg", "old=nope", "new=yes")
        content = (tmp_path / "tmp" / "cfg").read_text()
        assert "old: keep\n" in content
        assert "new: yes\n" in content


# ─── read ─────────────────────────────────────────────────────────────────────


class TestRead:

    def test_prints_file_contents(self, tmp_path):
        run_state(tmp_path, "init", "tmp/cfg", "mode=test", "level=3")
        result = run_state(tmp_path, "read", "tmp/cfg")
        assert "mode: test" in result.stdout
        assert "level: 3" in result.stdout

    def test_missing_file_exits_nonzero(self, tmp_path):
        result = run_state(tmp_path, "read", "tmp/nonexistent", check=False)
        assert result.returncode != 0
        assert "not found" in result.stderr


# ─── write-ids / read-ids ────────────────────────────────────────────────────


class TestWriteReadIds:

    def test_round_trip(self, tmp_path):
        run_state(tmp_path, "write-ids", "tmp/ids", "STRAT-001", "STRAT-002")
        result = run_state(tmp_path, "read-ids", "tmp/ids")
        assert result.stdout.strip() == "STRAT-001 STRAT-002"

    def test_deduplication(self, tmp_path):
        run_state(tmp_path, "write-ids", "tmp/ids",
                  "STRAT-001", "STRAT-002", "STRAT-001")
        result = run_state(tmp_path, "read-ids", "tmp/ids")
        ids = result.stdout.strip().split()
        assert ids == ["STRAT-001", "STRAT-002"]

    def test_order_preservation(self, tmp_path):
        run_state(tmp_path, "write-ids", "tmp/ids",
                  "C", "A", "B", "A")
        result = run_state(tmp_path, "read-ids", "tmp/ids")
        assert result.stdout.strip() == "C A B"

    def test_empty_id_list(self, tmp_path):
        run_state(tmp_path, "write-ids", "tmp/ids")
        result = run_state(tmp_path, "read-ids", "tmp/ids")
        assert result.stdout.strip() == ""

    def test_read_ids_missing_file(self, tmp_path):
        result = run_state(tmp_path, "read-ids", "tmp/missing", check=False)
        assert result.returncode != 0
        assert "not found" in result.stderr


# ─── timestamp ────────────────────────────────────────────────────────────────


class TestTimestamp:

    def test_iso_8601_format(self, tmp_path):
        result = run_state(tmp_path, "timestamp")
        ts = result.stdout.strip()
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts), \
            f"Timestamp '{ts}' is not ISO 8601 UTC"

    def test_ends_with_z(self, tmp_path):
        result = run_state(tmp_path, "timestamp")
        assert result.stdout.strip().endswith("Z")


# ─── clean ────────────────────────────────────────────────────────────────────


class TestClean:

    def test_removes_and_recreates_tmp(self, tmp_path):
        run_state(tmp_path, "init", "tmp/cfg", "a=1")
        assert (tmp_path / "tmp" / "cfg").exists()
        run_state(tmp_path, "clean")
        assert (tmp_path / "tmp").is_dir()
        assert not (tmp_path / "tmp" / "cfg").exists()

    def test_clean_when_no_tmp(self, tmp_path):
        run_state(tmp_path, "clean")
        assert (tmp_path / "tmp").is_dir()


# ─── Error handling ───────────────────────────────────────────────────────────


class TestErrors:

    def test_invalid_pair_exits_nonzero(self, tmp_path):
        result = run_state(tmp_path, "init", "tmp/cfg", "noequalssign",
                           check=False)
        assert result.returncode != 0
        assert "Invalid" in result.stderr

    def test_unknown_command(self, tmp_path):
        result = run_state(tmp_path, "bogus", check=False)
        assert result.returncode != 0

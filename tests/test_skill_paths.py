"""Integration tests — script path resolution via CLAUDE_SKILL_DIR."""
import os
import re
import subprocess
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKILLS_DIR = os.path.join(PROJECT_ROOT, ".claude", "skills")
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")

SCRIPT_REF_PATTERN = re.compile(
    r'(?:python3|bash)\s+\$\{CLAUDE_SKILL_DIR\}/scripts/(\S+)')
SYSPATH_PATTERN = re.compile(
    r"sys\.path\.insert\(0,\s*'\$\{CLAUDE_SKILL_DIR\}/scripts'\)")
IMPORT_PATTERN = re.compile(
    r'from\s+(\w+)\s+import\s+(.+)')


def _skills_with_script_refs():
    """Skills whose SKILL.md references ${CLAUDE_SKILL_DIR}/scripts/."""
    results = []
    for name in sorted(os.listdir(SKILLS_DIR)):
        skill_path = os.path.join(SKILLS_DIR, name)
        skill_md = os.path.join(skill_path, "SKILL.md")
        if os.path.isdir(skill_path) and os.path.isfile(skill_md):
            with open(skill_md) as f:
                content = f.read()
            if "${CLAUDE_SKILL_DIR}/scripts/" in content:
                results.append((name, skill_path, content))
    return results


def _skills_with_inline_imports():
    """Skills using sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')."""
    results = []
    for name, path, content in _skills_with_script_refs():
        lines = content.split("\n")
        imports = []
        for i, line in enumerate(lines):
            if SYSPATH_PATTERN.search(line):
                for j in range(i, min(i + 3, len(lines))):
                    m = IMPORT_PATTERN.search(lines[j])
                    if m:
                        imports.append((m.group(1), m.group(2).strip()))
        if imports:
            results.append((name, path, imports))
    return results


ALL_SKILLS = _skills_with_script_refs()
INLINE_IMPORT_SKILLS = _skills_with_inline_imports()


# ─── Script Resolution ───────────────────────────────────────────────────────


class TestScriptResolution:

    @pytest.mark.parametrize("skill_name,skill_path,content", ALL_SKILLS,
                             ids=[s[0] for s in ALL_SKILLS])
    def test_scripts_reachable_via_skill_dir(self, skill_name, skill_path,
                                              content):
        scripts = set(SCRIPT_REF_PATTERN.findall(content))
        scripts_dir = os.path.join(skill_path, "scripts")
        for script in scripts:
            resolved = os.path.join(scripts_dir, script)
            assert os.path.isfile(resolved), (
                f"Cannot reach {script} via "
                f"${{CLAUDE_SKILL_DIR}}/scripts/ for {skill_name}: "
                f"{resolved} does not exist")


# ─── Inline Import Resolution ────────────────────────────────────────────────


class TestInlineImports:

    @pytest.mark.parametrize("skill_name,skill_path,imports",
                             INLINE_IMPORT_SKILLS,
                             ids=[s[0] for s in INLINE_IMPORT_SKILLS])
    def test_inline_imports_succeed(self, skill_name, skill_path, imports):
        scripts_dir = os.path.join(skill_path, "scripts")
        for module_name, import_names in imports:
            names = [n.strip().rstrip(",") for n in import_names.split(",")]
            import_stmt = ", ".join(names)
            code = (
                f"import sys; "
                f"sys.path.insert(0, {scripts_dir!r}); "
                f"from {module_name} import {import_stmt}; "
                f"print('OK')"
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True,
                cwd=PROJECT_ROOT,
            )
            assert result.returncode == 0 and "OK" in result.stdout, (
                f"Inline import failed for {skill_name}: "
                f"from {module_name} import {import_stmt}\n"
                f"stderr: {result.stderr}")


# ─── Lightweight E2E ─────────────────────────────────────────────────────────


class TestScriptInvocation:

    @pytest.mark.parametrize("skill_name,skill_path,content",
                             [s for s in ALL_SKILLS
                              if "frontmatter.py" in s[2]],
                             ids=[s[0] for s in ALL_SKILLS
                                  if "frontmatter.py" in s[2]])
    def test_frontmatter_schema_via_skill_dir(self, skill_name, skill_path,
                                               content):
        script = os.path.join(skill_path, "scripts", "frontmatter.py")
        result = subprocess.run(
            [sys.executable, script, "schema", "strat-task"],
            capture_output=True, text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"frontmatter.py schema failed via {skill_name}: {result.stderr}")
        assert "strat_id" in result.stdout

    @pytest.mark.parametrize("skill_name,skill_path,content",
                             [s for s in ALL_SKILLS
                              if "state.py" in s[2]],
                             ids=[s[0] for s in ALL_SKILLS
                                  if "state.py" in s[2]])
    def test_state_timestamp_via_skill_dir(self, skill_name, skill_path,
                                            content):
        script = os.path.join(skill_path, "scripts", "state.py")
        result = subprocess.run(
            [sys.executable, script, "timestamp"],
            capture_output=True, text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"state.py timestamp failed via {skill_name}: {result.stderr}")
        assert re.match(r"\d{4}-\d{2}-\d{2}T", result.stdout.strip())

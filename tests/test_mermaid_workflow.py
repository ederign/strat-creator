"""Tests for mermaid pipeline workflow diagram in generate-report.py.

Validates that the mermaid diagram correctly represents the strategy
pipeline flow: nodes exist, edges connect correctly, subgraphs close,
and style directives reference real nodes.
"""
import os
import re

import pytest

REPORT_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "scripts", "generate-report.py")


def _extract_mermaid():
    """Extract the mermaid graph from generate-report.py source."""
    with open(REPORT_SCRIPT, encoding="utf-8") as f:
        content = f.read()
    match = re.search(
        r'<pre class="mermaid">\s*\n(.*?)</pre>',
        content, re.DOTALL)
    assert match, "No mermaid diagram found in generate-report.py"
    return match.group(1)


@pytest.fixture(scope="module")
def mermaid():
    return _extract_mermaid()


@pytest.fixture(scope="module")
def mermaid_lines(mermaid):
    return [line.strip() for line in mermaid.split("\n") if line.strip()]


@pytest.fixture(scope="module")
def defined_nodes(mermaid):
    """Extract all node IDs defined in the mermaid graph."""
    nodes = set()
    # node[text] or node["text"] definitions
    for m in re.finditer(r'\b([A-Za-z]\w*)\s*[\[\({"]', mermaid):
        nodes.add(m.group(1))
    # node{{text}} diamond definitions
    for m in re.finditer(r'\b([A-Za-z]\w*)\s*\{', mermaid):
        nodes.add(m.group(1))
    # Exclude keywords
    nodes -= {"graph", "subgraph", "end", "style", "fill", "color",
              "stroke", "LR", "TB", "TD"}
    return nodes


@pytest.fixture(scope="module")
def style_nodes(mermaid):
    """Extract all node IDs referenced in style directives."""
    return set(re.findall(r'^\s*style\s+(\w+)\s', mermaid, re.MULTILINE))


# ─── Phase 1: RFE Assessment ─────────────────────────────────────────────────

class TestPhase1Nodes:
    def test_rfe_create_exists(self, mermaid):
        assert "rfe.create" in mermaid

    def test_rfe_review_exists(self, mermaid):
        assert "rfe.review" in mermaid

    def test_rfe_auto_fix_exists(self, mermaid):
        assert "rfe.auto-fix" in mermaid

    def test_rfe_submit_exists(self, mermaid):
        assert "rfe.submit" in mermaid

    def test_phase1_flow(self, mermaid):
        assert "A[rfe.create] --> B[rfe.review]" in mermaid
        assert "B --> C[rfe.auto-fix]" in mermaid
        assert "C --> D[rfe.submit]" in mermaid

    def test_phase1_subgraph(self, mermaid):
        assert 'subgraph P1["Phase 1: RFE Assessment"]' in mermaid


# ─── Phase 2: Strategy Pipeline ──────────────────────────────────────────────

class TestPhase2Nodes:
    def test_strategy_create_exists(self, mermaid):
        assert "strategy-create" in mermaid

    def test_strategy_refine_exists(self, mermaid):
        assert "strategy-refine" in mermaid

    def test_strategy_review_exists(self, mermaid):
        assert "strategy-review" in mermaid

    def test_phase2_subgraph(self, mermaid):
        assert 'subgraph P2["Phase 2: Strategy Refinement"]' in mermaid


class TestGateNodes:
    def test_label_gate_exists(self, mermaid):
        assert "Pipeline label gate" in mermaid

    def test_strat_creator_label_in_gate(self, mermaid):
        assert "strat-creator-3.5" in mermaid

    def test_rubric_pass_label_in_gate(self, mermaid):
        assert "rfe-creator-autofix-rubric-pass" in mermaid

    def test_tech_reviewed_label_in_gate(self, mermaid):
        assert "tech-reviewed" in mermaid

    def test_gate_pass_fail_branches(self, mermaid):
        # Both gates have Pass/Fail branches
        assert 'GATE -->|"Fail"|' in mermaid
        assert 'GATE -->|"Pass"|' in mermaid


class TestCreateSubgraph:
    def test_fetch_rfe(self, mermaid):
        assert "Fetch RFE" in mermaid

    def test_check_existing_strats(self, mermaid):
        assert "Check existing" in mermaid
        assert "Cloners" in mermaid

    def test_clone_or_import(self, mermaid):
        assert "Clone or import" in mermaid

    def test_save_originals(self, mermaid):
        assert "Save originals" in mermaid

    def test_create_stubs(self, mermaid):
        assert "Create strategy" in mermaid

    def test_auto_created_label(self, mermaid):
        assert "strat-creator-auto-created" in mermaid

    def test_skipped_rfes_path(self, mermaid):
        assert "Skipped RFEs" in mermaid
        assert "strat-skipped.md" in mermaid


class TestRefineSubgraph:
    def test_arch_context(self, mermaid):
        assert "Fetch arch" in mermaid

    def test_how_context(self, mermaid):
        assert "HOW context" in mermaid
        assert "removed-context" in mermaid
        assert "Staff Eng Input" in mermaid
        assert "Arch overlays" in mermaid

    def test_technical_approach(self, mermaid):
        assert "Technical approach" in mermaid

    def test_dependencies_nfrs(self, mermaid):
        assert "Dependencies" in mermaid
        assert "NFRs" in mermaid

    def test_push_strategy(self, mermaid):
        assert "Push strategy" in mermaid

    def test_auto_refined_label(self, mermaid):
        assert "strat-creator-auto-refined" in mermaid

    def test_refine_gate(self, mermaid):
        assert 'FG -->|"Fail"| FSKIP' in mermaid
        assert 'FG -->|"Pass"| F0' in mermaid


class TestReviewSubgraph:
    def test_review_dimensions(self, mermaid):
        assert "R1[feasibility]" in mermaid
        assert "R2[testability]" in mermaid
        assert "R3[scope]" in mermaid
        assert "R4[architecture]" in mermaid

    def test_scorer_agents(self, mermaid):
        assert "assess-strat" in mermaid
        assert "scorer agents" in mermaid
        assert "F/T/S/A 0-2" in mermaid

    def test_deterministic_verdicts(self, mermaid):
        assert "parse_results.py" in mermaid
        assert "apply_scores.py" in mermaid
        assert "deterministic verdicts" in mermaid

    def test_review_output(self, mermaid):
        assert "Write review" in mermaid
        assert "scores" in mermaid

    def test_jira_integration(self, mermaid):
        assert "Attach review to Jira" in mermaid

    def test_verdict_threshold(self, mermaid):
        # ≥6/8 threshold
        assert "6/8" in mermaid
        assert "no zeros" in mermaid

    def test_approve_path(self, mermaid):
        assert "APPROVE" in mermaid
        assert "strat-creator-rubric-pass" in mermaid

    def test_revise_reject_path(self, mermaid):
        assert "REVISE" in mermaid
        assert "REJECT" in mermaid
        assert "strat-creator-needs-attention" in mermaid


class TestHumanReviewLoop:
    def test_human_review_node(self, mermaid):
        assert "Human Review" in mermaid
        assert "Staff Eng or Architect" in mermaid

    def test_path_a_update_context(self, mermaid):
        assert "Update" in mermaid
        assert "architecture context" in mermaid

    def test_path_b_staff_engineer_input(self, mermaid):
        assert "Staff Engineer Input" in mermaid

    def test_remove_label(self, mermaid):
        assert "Remove label" in mermaid
        assert "needs-attention" in mermaid

    def test_retrigger_refine(self, mermaid):
        assert "Re-trigger pipeline" in mermaid
        # Loop back: RL → SF (strategy-refine)
        assert "RL -->|" in mermaid
        assert "SF" in mermaid


# ─── Phase 3: Feature Dev ────────────────────────────────────────────────────

class TestPhase3:
    def test_phase3_subgraph(self, mermaid):
        assert 'subgraph P3["Phase 3: Feature Dev"]' in mermaid

    def test_feature_ready(self, mermaid):
        assert "feature.ready" in mermaid

    def test_optional_human_review(self, mermaid):
        assert "Optional: human" in mermaid


# ─── Cross-phase edges ───────────────────────────────────────────────────────

class TestCrossPhaseEdges:
    def test_phase1_to_phase2(self, mermaid):
        assert "D -->|" in mermaid
        assert "E0" in mermaid

    def test_create_to_refine(self, mermaid):
        assert "E6 --> SF" in mermaid

    def test_refine_to_review(self, mermaid):
        assert "F4 --> SRV" in mermaid

    def test_approve_to_phase3(self, mermaid):
        assert "PA --> FR" in mermaid


# ─── Structural validation ───────────────────────────────────────────────────

class TestStructuralIntegrity:
    def test_subgraphs_properly_closed(self, mermaid_lines):
        opens = sum(1 for l in mermaid_lines if l.startswith("subgraph"))
        closes = sum(1 for l in mermaid_lines if l == "end")
        assert opens == closes, (
            f"{opens} subgraph opens but {closes} end closes")

    def test_no_duplicate_node_ids(self, mermaid):
        # Find all node definitions: ID[, ID(, ID{, ID"
        defs = re.findall(
            r'(?:^|\s)([A-Z][A-Z0-9]*)\s*[\[\({"]', mermaid)
        # Filter out keywords and style refs
        keywords = {"LR", "TB", "TD"}
        defs = [d for d in defs if d not in keywords]
        seen = set()
        duplicates = set()
        for d in defs:
            if d in seen:
                duplicates.add(d)
            seen.add(d)
        assert not duplicates, f"Duplicate node IDs: {duplicates}"

    def test_style_directives_reference_defined_nodes(self, mermaid):
        """Every style directive must reference a node that exists."""
        styled = set(
            re.findall(r'^\s*style\s+(\w+)\s', mermaid, re.MULTILINE))
        # Find all defined node IDs (uppercase start, defined with [ { or ()
        defined = set()
        for m in re.finditer(
                r'(?:^|\s)([A-Za-z]\w*)\s*[\[\({"]', mermaid):
            defined.add(m.group(1))
        for m in re.finditer(
                r'(?:^|\s)([A-Za-z]\w*)\s*\{\{', mermaid):
            defined.add(m.group(1))
        # Also check edge references like "X --> Y"
        for m in re.finditer(r'(\w+)\s*--', mermaid):
            defined.add(m.group(1))
        for m in re.finditer(r'-->\s*(\w+)', mermaid):
            defined.add(m.group(1))
        for m in re.finditer(r'-\.->\s*(\w+)', mermaid):
            defined.add(m.group(1))
        for m in re.finditer(r'-->\|[^|]*\|\s*(\w+)', mermaid):
            defined.add(m.group(1))

        orphan_styles = styled - defined
        assert not orphan_styles, (
            f"Style directives reference undefined nodes: {orphan_styles}")

    def test_graph_type_is_lr(self, mermaid_lines):
        assert mermaid_lines[0] == "graph LR"

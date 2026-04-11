#!/usr/bin/env python3
"""Generate a multi-run executive dashboard from strategy pipeline data.

Scans all timestamped run directories in a RHAISTRAT/ data directory,
extracts aggregate stats from each run, and produces a self-contained
HTML dashboard with trend charts (Chart.js) and per-run drill-down.

Usage:
    python3 scripts/generate-dashboard.py \
        --data-dir /path/to/RHAISTRAT \
        --config config/test-rfes.yaml \
        --output /tmp/dashboard/index.html
"""

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Add scripts/ to path for artifact_utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from artifact_utils import read_frontmatter


# ─── Helper functions (shared with generate-report.py) ────────────────────────

def is_approve(v):
    return v in ("approve", "approved")

def is_revise(v):
    return v in ("revise", "needs revision", "needs_revision")

def is_reject(v):
    return v in ("reject", "rejected", "infeasible")

def pct(n, total):
    return round(100 * n / total) if total > 0 else 0

def health_color(rate):
    if rate >= 70:
        return "#3fb950"
    elif rate >= 40:
        return "#d29922"
    return "#f85149"

def verdict_class(verdict):
    if verdict in ("approve", "approved"):
        return "verdict-approve"
    elif verdict in ("revise", "needs revision", "needs_revision"):
        return "verdict-revise"
    elif verdict in ("reject", "rejected", "infeasible"):
        return "verdict-reject"
    return "verdict-unknown"

def verdict_label(verdict):
    if verdict in ("approve", "approved"):
        return "Approve"
    elif verdict in ("revise", "needs revision", "needs_revision"):
        return "Revise"
    elif verdict in ("reject", "rejected", "infeasible"):
        return "Reject"
    elif verdict in ("split",):
        return "Split"
    return verdict or "—"

def escape_html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def inline_format(text):
    text = escape_html(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text

def md_to_html(md_text):
    lines = md_text.split("\n")
    html_lines = []
    in_list = False
    in_code = False
    code_block = []

    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                html_lines.append("<pre><code>" + escape_html("\n".join(code_block)) + "</code></pre>")
                code_block = []
                in_code = False
            else:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                in_code = True
            continue
        if in_code:
            code_block.append(line)
            continue
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("")
            continue
        heading_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading_match:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            level = len(heading_match.group(1))
            text = inline_format(heading_match.group(2))
            html_lines.append(f"<h{level}>{text}</h{level}>")
            continue
        list_match = re.match(r'^[\s]*[-*]\s+(.*)', line)
        if list_match:
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{inline_format(list_match.group(1))}</li>")
            continue
        num_match = re.match(r'^[\s]*\d+\.\s+(.*)', line)
        if num_match:
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{inline_format(num_match.group(1))}</li>")
            continue
        if in_list:
            html_lines.append("</ul>")
            in_list = False
        html_lines.append(f"<p>{inline_format(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")
    if in_code:
        html_lines.append("<pre><code>" + escape_html("\n".join(code_block)) + "</code></pre>")
    return "\n".join(html_lines)


# ─── Data extraction ──────────────────────────────────────────────────────────

def load_yaml_config(path):
    import yaml
    with open(path) as f:
        data = yaml.safe_load(f)
    result = {}
    for rfe in data.get("test_rfes", []):
        result[rfe["id"]] = rfe
    return result


def load_run_artifacts(run_dir):
    """Load tasks and reviews from a single run directory."""
    tasks = {}
    reviews = {}

    for path in sorted(glob.glob(os.path.join(run_dir, "strat-tasks", "STRAT-*.md"))):
        try:
            meta, body = read_frontmatter(path)
            strat_id = meta.get("strat_id", Path(path).stem)
            tasks[strat_id] = {"meta": meta, "body": body}
        except Exception as e:
            print(f"  Warning: {path}: {e}", file=sys.stderr)

    for path in sorted(glob.glob(os.path.join(run_dir, "strat-reviews", "STRAT-*-review.md"))):
        try:
            meta, body = read_frontmatter(path)
            strat_id = meta.get("strat_id", Path(path).stem.replace("-review", ""))
            reviews[strat_id] = {"meta": meta, "body": body}
        except Exception as e:
            print(f"  Warning: {path}: {e}", file=sys.stderr)

    return tasks, reviews


def extract_run_stats(run_dir, config):
    """Extract aggregate stats and per-strategy detail from a run."""
    tasks, reviews = load_run_artifacts(run_dir)
    if not tasks:
        return None

    strategies = []
    for strat_id in sorted(tasks.keys()):
        task = tasks[strat_id]
        review = reviews.get(strat_id, {})
        meta = task["meta"]
        rev_meta = review.get("meta", {})
        reviewers = rev_meta.get("reviewers", {})
        source_rfe = meta.get("source_rfe", "")
        cfg = config.get(source_rfe, {})

        strategies.append({
            "strat_id": strat_id,
            "title": meta.get("title", ""),
            "source_rfe": source_rfe,
            "priority": meta.get("priority", "—"),
            "size": cfg.get("size", "—"),
            "baseline": cfg.get("baseline", False),
            "cross_component": cfg.get("cross_component", False),
            "recommendation": rev_meta.get("recommendation", "—"),
            "feasibility": reviewers.get("feasibility", "—"),
            "testability": reviewers.get("testability", "—"),
            "scope": reviewers.get("scope", "—"),
            "architecture": reviewers.get("architecture", "—"),
            "strategy_html": md_to_html(task.get("body", "")),
            "review_html": md_to_html(review.get("body", "")),
        })

    reviewed = [s for s in strategies if s["recommendation"] not in ("—", "")]
    total = len(strategies)
    total_reviewed = len(reviewed)
    approved = sum(1 for s in reviewed if is_approve(s["recommendation"]))
    revise = sum(1 for s in reviewed if is_revise(s["recommendation"]))

    dimensions = ["feasibility", "testability", "scope", "architecture"]
    dim_stats = {}
    for dim in dimensions:
        vals = [s[dim] for s in reviewed if s[dim] not in ("—", "")]
        dim_total = len(vals)
        dim_approve = sum(1 for v in vals if is_approve(v))
        dim_stats[dim] = {
            "total": dim_total,
            "approve": dim_approve,
            "revise": sum(1 for v in vals if is_revise(v)),
            "reject": sum(1 for v in vals if is_reject(v)),
            "rate": pct(dim_approve, dim_total),
        }

    weakest_dim = min(dimensions, key=lambda d: dim_stats[d]["rate"])
    strongest_dim = max(dimensions, key=lambda d: dim_stats[d]["rate"])

    return {
        "total": total,
        "reviewed": total_reviewed,
        "approved": approved,
        "revise": revise,
        "approval_rate": pct(approved, total_reviewed),
        "revision_rate": pct(revise, total_reviewed),
        "dimensions": dim_stats,
        "weakest_dim": weakest_dim,
        "weakest_rate": dim_stats[weakest_dim]["rate"],
        "strongest_dim": strongest_dim,
        "strongest_rate": dim_stats[strongest_dim]["rate"],
        "strategies": strategies,
    }


def scan_all_runs(data_dir, config, max_runs=30):
    """Discover all timestamped run directories and extract stats."""
    runs = []
    current_target = None

    current_link = os.path.join(data_dir, "current")
    if os.path.islink(current_link):
        current_target = os.readlink(current_link)

    for entry in sorted(os.listdir(data_dir)):
        entry_path = os.path.join(data_dir, entry)
        if not os.path.isdir(entry_path) or os.path.islink(entry_path):
            continue
        # Must match YYYYMMDD-HHMMSS
        try:
            ts = datetime.strptime(entry, "%Y%m%d-%H%M%S")
        except ValueError:
            continue

        print(f"  Scanning run {entry}...")
        stats = extract_run_stats(entry_path, config)
        if stats is None:
            print(f"    Skipped (no artifacts)")
            continue

        stats["run_id"] = entry
        stats["timestamp"] = ts.isoformat()
        stats["label"] = ts.strftime("%b %d, %Y %H:%M")
        stats["is_current"] = (entry == current_target)
        runs.append(stats)

    # Sort chronologically (oldest first) and cap
    runs.sort(key=lambda r: r["run_id"])
    if len(runs) > max_runs:
        runs = runs[-max_runs:]

    return runs


def compute_deltas(runs):
    """Add delta fields comparing each run to its predecessor."""
    for i, run in enumerate(runs):
        if i == 0:
            run["delta_approval"] = None
            run["delta_revision"] = None
        else:
            prev = runs[i - 1]
            run["delta_approval"] = run["approval_rate"] - prev["approval_rate"]
            run["delta_revision"] = run["revision_rate"] - prev["revision_rate"]


# ─── HTML generation ──────────────────────────────────────────────────────────

def generate_dashboard(runs, output_path):
    """Generate the full dashboard HTML."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    current = runs[-1] if runs else None

    # Prepare JSON data (strip strategy HTML bodies for overview; keep for detail)
    runs_json = json.dumps(runs, indent=None)

    # Delta arrows
    if current and current.get("delta_approval") is not None:
        da = current["delta_approval"]
        if da > 0:
            delta_arrow = f'<span style="color:#3fb950">+{da}%</span>'
        elif da < 0:
            delta_arrow = f'<span style="color:#f85149">{da}%</span>'
        else:
            delta_arrow = '<span style="color:#8b949e">0%</span>'
    else:
        delta_arrow = '<span style="color:#6e7681">first run</span>'

    # Hero
    if current:
        rate = current["approval_rate"]
        hero_color = health_color(rate)
        hero_text = f'{current["approved"]} of {current["reviewed"]} strategies approved ({rate}%)'
    else:
        hero_color = "#8b949e"
        hero_text = "No runs found"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Strategy Pipeline Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 24px; }}

.header {{ margin-bottom: 24px; }}
.header h1 {{ font-size: 28px; color: #f0f6fc; margin-bottom: 4px; }}
.header .subtitle {{ color: #8b949e; font-size: 13px; }}

/* Nav */
.nav-tabs {{ display: flex; gap: 0; margin-bottom: 24px; border-bottom: 2px solid #21262d; }}
.nav-tab {{ padding: 12px 24px; cursor: pointer; color: #8b949e; font-size: 15px; font-weight: 600; border-bottom: 2px solid transparent; margin-bottom: -2px; transition: all 0.2s; }}
.nav-tab:hover {{ color: #c9d1d9; background: #161b22; }}
.nav-tab.active {{ color: #f0f6fc; border-bottom-color: #f78166; }}
.nav-page {{ display: none; }}
.nav-page.active {{ display: block; }}

/* Hero */
.hero {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 32px; margin-bottom: 24px; text-align: center; }}
.hero-statement {{ font-size: 28px; font-weight: 700; margin-bottom: 4px; }}
.hero-delta {{ font-size: 16px; margin-bottom: 4px; }}
.hero-sub {{ color: #8b949e; font-size: 13px; }}

/* KPI cards */
.kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }}
.kpi {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px 24px; text-align: center; }}
.kpi-value {{ font-size: 36px; font-weight: 700; line-height: 1.1; }}
.kpi-label {{ font-size: 12px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 6px; }}
.kpi-detail {{ font-size: 12px; color: #6e7681; margin-top: 4px; }}

/* Charts */
.charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }}
.chart-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; }}
.chart-card h3 {{ color: #f0f6fc; font-size: 14px; margin-bottom: 12px; }}
.chart-card.full-width {{ grid-column: 1 / -1; }}

/* Run list */
.run-list {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 24px; }}
.run-list h3 {{ color: #f0f6fc; font-size: 16px; margin-bottom: 16px; }}
.run-item {{ display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 8px; cursor: pointer; border-bottom: 1px solid #21262d; transition: background 0.15s; }}
.run-item:hover {{ background: #1c2128; }}
.run-item:last-child {{ border-bottom: none; }}
.run-item .run-date {{ font-size: 14px; color: #c9d1d9; font-weight: 500; flex: 1; }}
.run-item .run-badge {{ font-size: 12px; font-weight: 600; padding: 2px 10px; border-radius: 12px; }}
.run-item .run-count {{ font-size: 12px; color: #8b949e; }}
.run-item .run-current {{ font-size: 10px; color: #58a6ff; text-transform: uppercase; font-weight: 600; }}

/* Detail page */
.run-selector {{ margin-bottom: 24px; }}
.run-selector select {{ background: #161b22; border: 1px solid #30363d; color: #c9d1d9; padding: 8px 16px; border-radius: 8px; font-size: 14px; cursor: pointer; }}
.run-selector select:focus {{ outline: none; border-color: #58a6ff; }}

/* Dimension bars */
.dim-section {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 24px; margin-bottom: 24px; }}
.dim-section h3 {{ color: #f0f6fc; font-size: 16px; margin-bottom: 16px; }}
.dim-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }}
.dim-label {{ width: 110px; font-size: 13px; color: #8b949e; text-align: right; flex-shrink: 0; }}
.dim-bar-container {{ flex: 1; }}
.dim-bar-track {{ display: flex; height: 24px; border-radius: 6px; overflow: hidden; background: #21262d; }}
.dim-bar-seg {{ transition: width 0.3s ease; }}
.dim-rate {{ width: 48px; font-size: 14px; font-weight: 700; text-align: right; flex-shrink: 0; }}

/* Verdict grid */
.grid-section {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 24px; margin-bottom: 24px; }}
.grid-section h3 {{ color: #f0f6fc; font-size: 16px; margin-bottom: 8px; }}
.grid-header {{ display: flex; align-items: center; gap: 4px; padding: 0 0 8px; border-bottom: 1px solid #21262d; margin-bottom: 8px; }}
.grid-header-id {{ width: 90px; font-size: 11px; color: #6e7681; text-transform: uppercase; }}
.grid-header-dim {{ width: 40px; text-align: center; font-size: 10px; color: #6e7681; text-transform: uppercase; }}
.grid-header-verdict {{ width: 72px; text-align: right; font-size: 11px; color: #6e7681; text-transform: uppercase; }}
.grid-row {{ display: flex; align-items: center; gap: 4px; padding: 4px 0; }}
.grid-id {{ width: 90px; font-size: 13px; color: #c9d1d9; font-weight: 500; }}
.grid-cell {{ width: 40px; height: 24px; border-radius: 4px; border: 2px solid; }}
.grid-verdict {{ width: 72px; text-align: right; font-size: 12px; font-weight: 600; }}

/* Two column */
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }}

/* Table */
table {{ width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; margin-bottom: 24px; }}
thead {{ background: #21262d; }}
th {{ text-align: left; padding: 12px 16px; font-size: 12px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; border-bottom: 1px solid #30363d; }}
td {{ padding: 12px 16px; border-bottom: 1px solid #21262d; font-size: 14px; }}
tr:hover {{ background: #1c2128; }}
tr.clickable {{ cursor: pointer; }}

/* Verdicts */
.verdict-approve {{ color: #3fb950; font-weight: 600; }}
.verdict-revise {{ color: #d29922; font-weight: 600; }}
.verdict-reject {{ color: #f85149; font-weight: 600; }}
.verdict-unknown {{ color: #8b949e; }}

/* Badges */
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
.badge-baseline {{ background: #1f3a5f; color: #58a6ff; }}
.badge-cross {{ background: #3d2e00; color: #d29922; }}
.badge-size {{ background: #21262d; color: #8b949e; border: 1px solid #30363d; }}

/* Detail panels */
.detail-panel {{ display: none; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; margin: 8px 16px 16px; padding: 24px; }}
.detail-panel.open {{ display: block; }}
.detail-panel h2 {{ color: #f0f6fc; font-size: 20px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #21262d; }}
.detail-panel h3 {{ color: #c9d1d9; font-size: 16px; margin: 16px 0 8px; }}
.detail-panel p {{ line-height: 1.6; margin-bottom: 8px; }}
.detail-panel ul {{ padding-left: 24px; margin-bottom: 8px; }}
.detail-panel li {{ line-height: 1.6; margin-bottom: 4px; }}
.detail-panel code {{ background: #21262d; padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
.detail-panel pre {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 16px; overflow-x: auto; margin: 8px 0; }}
.detail-panel pre code {{ background: none; padding: 0; }}
.detail-tabs {{ display: flex; gap: 0; margin-bottom: 16px; border-bottom: 1px solid #30363d; }}
.detail-tab {{ padding: 8px 16px; cursor: pointer; color: #8b949e; font-size: 14px; border-bottom: 2px solid transparent; }}
.detail-tab:hover {{ color: #c9d1d9; }}
.detail-tab.active {{ color: #f0f6fc; border-bottom-color: #f78166; }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}
.expand-icon {{ color: #8b949e; transition: transform 0.2s; display: inline-block; margin-right: 8px; }}
.expand-icon.open {{ transform: rotate(90deg); }}

.zoom-btn {{ background: #21262d; border: 1px solid #30363d; color: #c9d1d9; width: 32px; height: 32px; border-radius: 6px; cursor: pointer; font-size: 16px; display: flex; align-items: center; justify-content: center; }}
.zoom-btn:hover {{ background: #30363d; color: #f0f6fc; }}
.footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #21262d; color: #484f58; font-size: 12px; }}

@media (max-width: 900px) {{
    .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .charts-grid {{ grid-template-columns: 1fr; }}
    .two-col {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>

<div class="header">
    <h1>Strategy Pipeline Dashboard</h1>
    <div class="subtitle">Generated {timestamp} | {len(runs)} run(s) tracked</div>
</div>

<div style="background:#1c1f26;border:1px solid #30363d;border-left:4px solid #58a6ff;border-radius:8px;padding:20px 24px;margin-bottom:24px;line-height:1.7">
    <div style="font-size:15px;font-weight:600;color:#58a6ff;margin-bottom:8px">Infrastructure Validation Phase</div>
    <div style="font-size:13px;color:#8b949e">
        This dashboard reflects <strong style="color:#c9d1d9">early pipeline scaffolding</strong>, not production-grade strategy assessments.
        We are validating the end-to-end pipeline infrastructure: Jira ingestion, strategy creation, multi-reviewer orchestration, artifact storage, and automated reporting.
        The four review dimensions (feasibility, testability, scope, architecture) are running with <strong style="color:#c9d1d9">baseline prompts</strong> that have not yet been calibrated against a scoring rubric or tuned with real-world examples.
        <br><br>
        <strong style="color:#c9d1d9">What to expect next:</strong> calibrated rubrics with scored examples, evidence-based review gates (every finding must cite specific strategy text), additional review dimensions (security, API readiness), and revision cycles with convergence guardrails. Approval rates will shift materially as reviewer skills are fine-tuned.
        <br><br>
        <span style="color:#6e7681">The goal of this phase is to prove the machinery works and begin collecting data. The goal of the next phase is to make the output trustworthy.</span>
    </div>
</div>

<div class="nav-tabs">
    <div class="nav-tab active" onclick="switchPage('overview')">Overview</div>
    <div class="nav-tab" onclick="switchPage('run-detail')">Run Detail</div>
    <div class="nav-tab" onclick="switchPage('pipeline')">Pipeline</div>
</div>

<!-- ═══ OVERVIEW PAGE ═══ -->
<div class="nav-page active" id="page-overview">

<div class="hero">
    <div class="hero-statement" style="color:{hero_color}">{escape_html(hero_text)}</div>
    <div class="hero-delta">vs previous run: {delta_arrow}</div>
    <div class="hero-sub">{len(runs)} pipeline run(s) | Latest: {current["label"] if current else "none"}</div>
</div>

<div class="kpi-grid" style="grid-template-columns: repeat(5, 1fr);">
    <div class="kpi">
        <div class="kpi-value" style="color:#58a6ff">{len(runs)}</div>
        <div class="kpi-label">Pipeline Runs</div>
        <div class="kpi-detail">Latest: {current["label"] if current else "—"}</div>
    </div>
    <div class="kpi">
        <div class="kpi-value" style="color:#f0f6fc">{current["reviewed"] if current else 0}</div>
        <div class="kpi-label">Strategies Reviewed</div>
        <div class="kpi-detail">{current["total"] if current else 0} total</div>
    </div>
    <div class="kpi">
        <div class="kpi-value" style="color:{health_color(current["approval_rate"]) if current else '#8b949e'}">{current["approval_rate"] if current else 0}%</div>
        <div class="kpi-label">Approval Rate</div>
        <div class="kpi-detail">{current["approved"] if current else 0} approved</div>
    </div>
    <div class="kpi">
        <div class="kpi-value" style="color:{health_color(100 - current["revision_rate"]) if current else '#8b949e'}">{current["revision_rate"] if current else 0}%</div>
        <div class="kpi-label">Revision Rate</div>
        <div class="kpi-detail">{current["revise"] if current else 0} need rework</div>
    </div>
    <div class="kpi">
        <div class="kpi-value" style="color:{health_color(current["weakest_rate"]) if current else '#8b949e'}">{current["weakest_rate"] if current else 0}%</div>
        <div class="kpi-label">Weakest: {current["weakest_dim"].title() if current else "—"}</div>
        <div class="kpi-detail">Strongest: {current["strongest_dim"].title() if current else "—"} ({current["strongest_rate"] if current else 0}%)</div>
    </div>
</div>

<div class="charts-grid">
    <div class="chart-card">
        <h3>Approval Rate Over Time</h3>
        <canvas id="chart-approval"></canvas>
    </div>
    <div class="chart-card">
        <h3>Strategies Per Run</h3>
        <canvas id="chart-volume"></canvas>
    </div>
    <div class="chart-card full-width">
        <h3>Review Dimensions Over Time</h3>
        <p style="color:#6e7681;font-size:12px;margin-bottom:8px">Approval rate per reviewer dimension across runs. Identifies which dimension is the bottleneck and whether it's improving.</p>
        <canvas id="chart-dimensions"></canvas>
    </div>
</div>

<div class="run-list">
    <h3>All Runs</h3>
    <div id="run-list-container"></div>
</div>

</div><!-- end overview -->

<!-- ═══ RUN DETAIL PAGE ═══ -->
<div class="nav-page" id="page-run-detail">
    <div class="run-selector">
        <select id="run-select" onchange="renderRunDetail(this.value)">
        </select>
    </div>
    <div id="run-detail-content"></div>
</div>

<!-- ═══ PIPELINE PAGE ═══ -->
<div class="nav-page" id="page-pipeline">
<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:24px;position:relative;height:calc(100vh - 180px);display:flex;flex-direction:column">
    <h2 style="color:#f0f6fc;font-size:16px;margin-bottom:16px;flex-shrink:0">RHAI Agentic SDLC Pipeline</h2>
    <div style="position:absolute;top:16px;right:16px;display:flex;gap:4px;z-index:10">
        <button class="zoom-btn" onclick="zoomDiagram(1.2)" title="Zoom in">+</button>
        <button class="zoom-btn" onclick="zoomDiagram(0.8)" title="Zoom out">&minus;</button>
        <button class="zoom-btn" onclick="resetDiagram()" title="Reset">&#8634;</button>
    </div>
    <div id="diagram-container" style="overflow:hidden;position:relative;flex:1">
    <div id="diagram-inner" style="transform-origin:0 0;transition:transform 0.1s ease;height:100%;display:flex;align-items:center;justify-content:center">
    <pre class="mermaid">
graph LR
    subgraph P1["Phase 1: RFE Assessment"]
        A[rfe.create] --> B[rfe.review]
        B --> C[rfe.auto-fix]
        C --> D[rfe.submit]
    end

    D -->|"Automatic or\\nPM Jira label\\nas pipeline trigger"| E

    subgraph P2["Phase 2: Strategy Refinement"]
        E[strategy.create]

        subgraph SR["strategy.refine"]
            F1[Fetch arch context] --> F2[Technical approach]
            F2 --> F3[Dependencies &\\ncomponents]
            F3 --> F4[Effort estimate\\n& risks]
        end

        E --> F1
        F4 --> G{{{{refined}}}}

        subgraph SV["strategy.review (4 parallel)"]
            R1[feasibility]
            R2[testability]
            R3[scope]
            R4[architecture]
            R5[other subtasks]
        end

        G --> R1 & R2 & R3 & R4 & R5
        R1 & R2 & R3 & R4 & R5 --> CON[Consolidate\\nreviews]
        CON --> Q{{{{approve?}}}}
        Q -->|approved| I[strategy.submit]
        I --> KO["Kick off Phase 3"]
        Q -->|revise| P["Human review"]
        P --> H[strategy.revise]
        H -->|max 2 cycles| F1
    end

    KO -->|"PM adds\\nstrat-prioritized label"| FR

    subgraph P3["Phase 3: Feature Dev"]
        FR[feature.ready] --> J[Feature Ready]
        J --> K[Prioritize]
        K --> L[AI-Assisted Dev]
        L --> M[PR Review]
    end

    style A fill:#2d6a2d,color:#fff
    style B fill:#2d6a2d,color:#fff
    style C fill:#2d6a2d,color:#fff
    style D fill:#2d6a2d,color:#fff
    style E fill:#c77d1a,color:#fff
    style F1 fill:#c77d1a,color:#fff
    style F2 fill:#c77d1a,color:#fff
    style F3 fill:#c77d1a,color:#fff
    style F4 fill:#c77d1a,color:#fff
    style R1 fill:#c77d1a,color:#fff
    style R2 fill:#c77d1a,color:#fff
    style R3 fill:#c77d1a,color:#fff
    style R4 fill:#c77d1a,color:#fff
    style R5 fill:#21262d,color:#8b949e,stroke:#30363d,stroke-dasharray: 5 5
    style CON fill:#c77d1a,color:#fff
    style G fill:#1f3a5f,color:#58a6ff,stroke:#58a6ff
    style Q fill:#1f3a5f,color:#58a6ff,stroke:#58a6ff
    style P fill:#3d1f00,color:#f0883e,stroke:#f0883e
    style H fill:#555,color:#fff
    style I fill:#555,color:#fff
    style KO fill:#1f6feb,color:#fff,stroke:#58a6ff
    style FR fill:#555,color:#fff
    style J fill:#555,color:#fff
    style K fill:#555,color:#fff
    style L fill:#555,color:#fff
    style M fill:#555,color:#fff
    </pre>
    </div>
    </div>
</div>
</div><!-- end pipeline -->

<div class="footer">
    strat-creator pipeline | RHAI Agentic SDLC
</div>

<script>
const RUNS = {runs_json};

// ─── Page switching ──────────────────────────────────────────────────────────
function switchPage(page) {{
    document.querySelectorAll('.nav-page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.getElementById('page-' + page).classList.add('active');
    event.target.classList.add('active');
}}

function showRunDetail(idx) {{
    document.getElementById('run-select').value = idx;
    renderRunDetail(idx);
    // Switch to detail tab
    document.querySelectorAll('.nav-page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.getElementById('page-run-detail').classList.add('active');
    document.querySelectorAll('.nav-tab')[1].classList.add('active');
}}

// ─── Build run list ──────────────────────────────────────────────────────────
function buildRunList() {{
    const container = document.getElementById('run-list-container');
    let html = '';
    for (let i = RUNS.length - 1; i >= 0; i--) {{
        const r = RUNS[i];
        const rate = r.approval_rate;
        const color = rate >= 70 ? '#3fb950' : rate >= 40 ? '#d29922' : '#f85149';
        const bg = rate >= 70 ? '#23302a' : rate >= 40 ? '#2d2400' : '#2d1418';
        html += `<div class="run-item" onclick="showRunDetail(${{i}})">
            <div class="run-date">${{r.label}}</div>
            ${{r.is_current ? '<div class="run-current">current</div>' : ''}}
            <div class="run-count">${{r.reviewed}} strategies</div>
            <div class="run-badge" style="background:${{bg}};color:${{color}}">${{rate}}% approved</div>
        </div>`;
    }}
    container.innerHTML = html;
}}

// ─── Populate run selector ───────────────────────────────────────────────────
function buildRunSelector() {{
    const sel = document.getElementById('run-select');
    for (let i = RUNS.length - 1; i >= 0; i--) {{
        const r = RUNS[i];
        const opt = document.createElement('option');
        opt.value = i;
        opt.textContent = `${{r.label}} — ${{r.approval_rate}}% approved (${{r.reviewed}} strategies)${{r.is_current ? ' [current]' : ''}}`;
        sel.appendChild(opt);
    }}
    if (RUNS.length > 0) {{
        sel.value = RUNS.length - 1;
        renderRunDetail(RUNS.length - 1);
    }}
}}

// ─── Render run detail ───────────────────────────────────────────────────────
function healthColor(rate) {{
    if (rate >= 70) return '#3fb950';
    if (rate >= 40) return '#d29922';
    return '#f85149';
}}

function verdictClass(v) {{
    if (['approve','approved'].includes(v)) return 'verdict-approve';
    if (['revise','needs revision','needs_revision'].includes(v)) return 'verdict-revise';
    if (['reject','rejected','infeasible'].includes(v)) return 'verdict-reject';
    return 'verdict-unknown';
}}

function verdictLabel(v) {{
    if (['approve','approved'].includes(v)) return 'Approve';
    if (['revise','needs revision','needs_revision'].includes(v)) return 'Revise';
    if (['reject','rejected','infeasible'].includes(v)) return 'Reject';
    if (v === 'split') return 'Split';
    return v || '—';
}}

function cellStyle(v) {{
    if (['approve','approved'].includes(v)) return 'background:#23302a;border-color:#3fb950';
    if (['revise','needs revision','needs_revision'].includes(v)) return 'background:#2d2400;border-color:#d29922';
    if (['reject','rejected','infeasible'].includes(v)) return 'background:#2d1418;border-color:#f85149';
    return 'background:#161b22;border-color:#30363d';
}}

function renderRunDetail(idx) {{
    const r = RUNS[idx];
    const dims = ['feasibility','testability','scope','architecture'];
    const el = document.getElementById('run-detail-content');

    // Hero
    let html = `<div class="hero">
        <div class="hero-statement" style="color:${{healthColor(r.approval_rate)}}">${{r.approved}} of ${{r.reviewed}} strategies approved (${{r.approval_rate}}%)</div>
        <div class="hero-sub">${{r.label}} | ${{r.total}} strategies processed</div>
    </div>`;

    // KPI cards
    html += `<div class="kpi-grid">
        <div class="kpi"><div class="kpi-value" style="color:#f0f6fc">${{r.reviewed}}</div><div class="kpi-label">Reviewed</div></div>
        <div class="kpi"><div class="kpi-value" style="color:${{healthColor(r.approval_rate)}}">${{r.approval_rate}}%</div><div class="kpi-label">Approval Rate</div></div>
        <div class="kpi"><div class="kpi-value" style="color:${{healthColor(100-r.revision_rate)}}">${{r.revision_rate}}%</div><div class="kpi-label">Revision Rate</div></div>
        <div class="kpi"><div class="kpi-value" style="color:${{healthColor(r.weakest_rate)}}">${{r.weakest_rate}}%</div><div class="kpi-label">Weakest: ${{r.weakest_dim.charAt(0).toUpperCase()+r.weakest_dim.slice(1)}}</div></div>
    </div>`;

    // Two-col: dimension bars + verdict grid
    // Dimension bars
    let dimHtml = '<div class="dim-section"><h3>Review Dimensions</h3>';
    dims.forEach(dim => {{
        const ds = r.dimensions[dim];
        const rate = ds.rate;
        const aw = ds.total > 0 ? Math.round(100*ds.approve/ds.total) : 0;
        const rw = ds.total > 0 ? Math.round(100*ds.revise/ds.total) : 0;
        const rejw = ds.total > 0 ? Math.round(100*ds.reject/ds.total) : 0;
        dimHtml += `<div class="dim-row">
            <div class="dim-label">${{dim.charAt(0).toUpperCase()+dim.slice(1)}}</div>
            <div class="dim-bar-container"><div class="dim-bar-track">
                <div class="dim-bar-seg" style="width:${{aw}}%;background:#3fb950" title="${{ds.approve}} approved"></div>
                <div class="dim-bar-seg" style="width:${{rw}}%;background:#d29922" title="${{ds.revise}} revise"></div>
                <div class="dim-bar-seg" style="width:${{rejw}}%;background:#f85149" title="${{ds.reject}} rejected"></div>
            </div></div>
            <div class="dim-rate" style="color:${{healthColor(rate)}}">${{rate}}%</div>
        </div>`;
    }});
    dimHtml += `<div style="display:flex;gap:16px;margin-top:12px;font-size:11px;color:#6e7681">
        <span><span style="display:inline-block;width:10px;height:10px;background:#3fb950;border-radius:2px;margin-right:4px"></span>Approve</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#d29922;border-radius:2px;margin-right:4px"></span>Revise</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#f85149;border-radius:2px;margin-right:4px"></span>Reject</span>
    </div></div>`;

    // Verdict grid
    let gridHtml = `<div class="grid-section"><h3>Per-Strategy Verdicts</h3>
        <div class="grid-header">
            <div class="grid-header-id">Strategy</div>
            <div class="grid-header-dim">Feas</div>
            <div class="grid-header-dim">Test</div>
            <div class="grid-header-dim">Scope</div>
            <div class="grid-header-dim">Arch</div>
            <div class="grid-header-verdict">Result</div>
        </div>`;
    r.strategies.forEach(s => {{
        const sid = s.strat_id.replace('STRAT-','');
        let cells = '';
        dims.forEach(d => {{
            cells += `<div class="grid-cell" style="${{cellStyle(s[d])}}" title="${{d}}: ${{s[d]}}"></div>`;
        }});
        gridHtml += `<div class="grid-row">
            <div class="grid-id">STRAT-${{sid}}</div>
            ${{cells}}
            <div class="grid-verdict ${{verdictClass(s.recommendation)}}">${{verdictLabel(s.recommendation)}}</div>
        </div>`;
    }});
    gridHtml += '</div>';

    html += `<div class="two-col">${{dimHtml}}${{gridHtml}}</div>`;

    // Summary table
    html += `<table><thead><tr>
        <th></th><th>Strat ID</th><th>Title</th><th>Source RFE</th><th>Size</th>
        <th>Feasibility</th><th>Testability</th><th>Scope</th><th>Architecture</th><th>Result</th>
    </tr></thead><tbody>`;
    r.strategies.forEach((s, i) => {{
        let badges = '';
        if (s.baseline) badges += ' <span class="badge badge-baseline">baseline</span>';
        if (s.cross_component) badges += ' <span class="badge badge-cross">cross-component</span>';
        html += `<tr class="clickable" onclick="toggleRunDetail(${{idx}},${{i}})">
            <td><span class="expand-icon" id="ricon-${{idx}}-${{i}}">&#9654;</span></td>
            <td><strong>${{s.strat_id}}</strong></td>
            <td>${{s.title}}${{badges}}</td>
            <td>${{s.source_rfe}}</td>
            <td><span class="badge badge-size">${{s.size}}</span></td>
            <td class="${{verdictClass(s.feasibility)}}">${{verdictLabel(s.feasibility)}}</td>
            <td class="${{verdictClass(s.testability)}}">${{verdictLabel(s.testability)}}</td>
            <td class="${{verdictClass(s.scope)}}">${{verdictLabel(s.scope)}}</td>
            <td class="${{verdictClass(s.architecture)}}">${{verdictLabel(s.architecture)}}</td>
            <td class="${{verdictClass(s.recommendation)}}">${{verdictLabel(s.recommendation)}}</td>
        </tr>
        <tr><td colspan="10" style="padding:0">
            <div class="detail-panel" id="rpanel-${{idx}}-${{i}}">
                <h2>${{s.strat_id}}: ${{s.title}}</h2>
                <div class="detail-tabs">
                    <div class="detail-tab active" onclick="switchRunTab(${{idx}},${{i}},'review')">Review</div>
                    <div class="detail-tab" onclick="switchRunTab(${{idx}},${{i}},'strategy')">Strategy</div>
                </div>
                <div class="tab-content active" id="rtab-${{idx}}-${{i}}-review">${{s.review_html}}</div>
                <div class="tab-content" id="rtab-${{idx}}-${{i}}-strategy">${{s.strategy_html}}</div>
            </div>
        </td></tr>`;
    }});
    html += '</tbody></table>';

    el.innerHTML = html;
}}

function toggleRunDetail(runIdx, stratIdx) {{
    const panel = document.getElementById(`rpanel-${{runIdx}}-${{stratIdx}}`);
    const icon = document.getElementById(`ricon-${{runIdx}}-${{stratIdx}}`);
    panel.classList.toggle('open');
    icon.classList.toggle('open');
}}

function switchRunTab(runIdx, stratIdx, tab) {{
    const panel = document.getElementById(`rpanel-${{runIdx}}-${{stratIdx}}`);
    panel.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
    panel.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(`rtab-${{runIdx}}-${{stratIdx}}-${{tab}}`).classList.add('active');
    event.target.classList.add('active');
}}

// ─── Chart.js initialization ─────────────────────────────────────────────────
Chart.defaults.color = '#8b949e';
Chart.defaults.borderColor = '#21262d';

function initCharts() {{
    const labels = RUNS.map(r => r.label);

    // Approval rate trend
    new Chart(document.getElementById('chart-approval'), {{
        type: 'line',
        data: {{
            labels,
            datasets: [{{
                label: 'Approval Rate %',
                data: RUNS.map(r => r.approval_rate),
                borderColor: '#3fb950',
                backgroundColor: 'rgba(63,185,80,0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 6,
                pointHoverRadius: 8,
                pointBackgroundColor: '#3fb950',
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{ display: false }},
            }},
            scales: {{
                y: {{
                    min: 0, max: 100,
                    ticks: {{ callback: v => v + '%' }},
                    grid: {{ color: '#161b22' }},
                }},
                x: {{
                    grid: {{ display: false }},
                }},
            }},
        }},
    }});

    // Strategies per run
    new Chart(document.getElementById('chart-volume'), {{
        type: 'bar',
        data: {{
            labels,
            datasets: [{{
                label: 'Approved',
                data: RUNS.map(r => r.approved),
                backgroundColor: '#3fb950',
                borderRadius: 4,
            }}, {{
                label: 'Revise',
                data: RUNS.map(r => r.revise),
                backgroundColor: '#d29922',
                borderRadius: 4,
            }}, {{
                label: 'Other',
                data: RUNS.map(r => r.reviewed - r.approved - r.revise),
                backgroundColor: '#484f58',
                borderRadius: 4,
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{ position: 'bottom', labels: {{ boxWidth: 12 }} }},
            }},
            scales: {{
                x: {{ stacked: true, grid: {{ display: false }} }},
                y: {{ stacked: true, grid: {{ color: '#161b22' }}, ticks: {{ stepSize: 1 }} }},
            }},
        }},
    }});

    // Dimension trends
    const dimColors = {{
        feasibility: '#58a6ff',
        testability: '#d29922',
        scope: '#3fb950',
        architecture: '#f78166',
    }};
    new Chart(document.getElementById('chart-dimensions'), {{
        type: 'line',
        data: {{
            labels,
            datasets: ['feasibility','testability','scope','architecture'].map(dim => ({{
                label: dim.charAt(0).toUpperCase() + dim.slice(1),
                data: RUNS.map(r => r.dimensions[dim].rate),
                borderColor: dimColors[dim],
                backgroundColor: 'transparent',
                tension: 0.3,
                pointRadius: 5,
                pointHoverRadius: 7,
                pointBackgroundColor: dimColors[dim],
            }}))
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{ position: 'bottom', labels: {{ boxWidth: 12 }} }},
            }},
            scales: {{
                y: {{
                    min: 0, max: 100,
                    ticks: {{ callback: v => v + '%' }},
                    grid: {{ color: '#161b22' }},
                }},
                x: {{ grid: {{ display: false }} }},
            }},
        }},
    }});
}}

// ─── Diagram zoom/pan ────────────────────────────────────────────────────────
let diagramScale = 1, diagramX = 0, diagramY = 0;
let isDragging = false, startX, startY;

function zoomDiagram(factor) {{
    diagramScale *= factor;
    diagramScale = Math.max(0.3, Math.min(3, diagramScale));
    updateDiagramTransform();
}}
function resetDiagram() {{
    diagramScale = 1; diagramX = 0; diagramY = 0;
    updateDiagramTransform();
}}
function updateDiagramTransform() {{
    const inner = document.getElementById('diagram-inner');
    if (inner) inner.style.transform = `translate(${{diagramX}}px, ${{diagramY}}px) scale(${{diagramScale}})`;
}}

const dContainer = document.getElementById('diagram-container');
if (dContainer) {{
    dContainer.addEventListener('wheel', (e) => {{ e.preventDefault(); zoomDiagram(e.deltaY < 0 ? 1.1 : 0.9); }}, {{ passive: false }});
    dContainer.addEventListener('mousedown', (e) => {{ isDragging = true; startX = e.clientX - diagramX; startY = e.clientY - diagramY; }});
    document.addEventListener('mousemove', (e) => {{
        if (!isDragging) return;
        diagramX = e.clientX - startX; diagramY = e.clientY - startY;
        const inner = document.getElementById('diagram-inner');
        inner.style.transition = 'none'; updateDiagramTransform(); inner.style.transition = 'transform 0.1s ease';
    }});
    document.addEventListener('mouseup', () => {{ isDragging = false; }});
}}

// ─── Init ────────────────────────────────────────────────────────────────────
buildRunList();
buildRunSelector();
initCharts();
</script>

<script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{ startOnLoad: false, theme: 'dark', flowchart: {{ useMaxWidth: false, htmlLabels: true, curve: 'basis' }} }});
    let mermaidRendered = false;
    const origSwitchPage = window.switchPage || switchPage;
    // Patch switchPage to render mermaid on first Pipeline tab click
    const _origSwitch = switchPage;
    window._renderMermaid = async function() {{
        if (mermaidRendered) return;
        mermaidRendered = true;
        await mermaid.run();
        const svg = document.querySelector('.mermaid svg');
        const ctr = document.getElementById('diagram-container');
        if (svg && ctr) {{
            const svgRect = svg.getBoundingClientRect();
            const ctrRect = ctr.getBoundingClientRect();
            const scaleX = ctrRect.width / svgRect.width;
            const scaleY = ctrRect.height / svgRect.height;
            diagramScale = Math.min(scaleX, scaleY, 2) * 0.9;
            diagramX = (ctrRect.width - svgRect.width * diagramScale) / 2;
            diagramY = (ctrRect.height - svgRect.height * diagramScale) / 2;
            updateDiagramTransform();
        }}
    }};
    // Observe when pipeline page becomes visible
    const obs = new MutationObserver(() => {{
        const pp = document.getElementById('page-pipeline');
        if (pp && pp.classList.contains('active') && !mermaidRendered) window._renderMermaid();
    }});
    obs.observe(document.getElementById('page-pipeline'), {{ attributes: true, attributeFilter: ['class'] }});
</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Dashboard generated: {output_path}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate multi-run strategy dashboard")
    parser.add_argument("--data-dir", required=True,
                        help="Path to RHAISTRAT/ directory containing timestamped runs")
    parser.add_argument("--config", "-c", default="config/test-rfes.yaml",
                        help="Test RFEs config file (default: config/test-rfes.yaml)")
    parser.add_argument("--output", "-o", default="/tmp/dashboard/index.html",
                        help="Output HTML file path")
    parser.add_argument("--max-runs", type=int, default=30,
                        help="Maximum number of runs to include (default: 30)")
    args = parser.parse_args()

    # Load config
    config = {}
    if os.path.exists(args.config):
        try:
            config = load_yaml_config(args.config)
        except Exception as e:
            print(f"Warning: failed to read config: {e}", file=sys.stderr)

    # Scan all runs
    print(f"Scanning {args.data_dir} for runs...")
    runs = scan_all_runs(args.data_dir, config, max_runs=args.max_runs)

    if not runs:
        print("Error: no valid runs found", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(runs)} run(s)")
    compute_deltas(runs)
    generate_dashboard(runs, args.output)


if __name__ == "__main__":
    main()

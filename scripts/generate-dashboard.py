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
from artifact_utils import read_frontmatter, compute_strat_labels, label_category


# ─── Helper functions (shared with generate-report.py) ────────────────────────

def is_approve(v):
    return v in ("approve", "approved")

def is_revise(v):
    return v in ("revise", "needs revision", "needs_revision")

def is_reject(v):
    return v in ("reject", "rejected", "infeasible")

def is_split(v):
    return v == "split"

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
    elif verdict == "split":
        return "verdict-split"
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
    in_table = False
    code_block = []
    table_rows = []

    def flush_table():
        nonlocal in_table, table_rows
        if not table_rows:
            return
        html_lines.append('<table>')
        for idx, row_cells in enumerate(table_rows):
            tag = "th" if idx == 0 else "td"
            html_lines.append("<tr>")
            for cell in row_cells:
                html_lines.append(f"<{tag}>{inline_format(cell.strip())}</{tag}>")
            html_lines.append("</tr>")
        html_lines.append("</table>")
        table_rows = []
        in_table = False

    for line in lines:
        if line.strip().startswith("```"):
            if in_table:
                flush_table()
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
        # Markdown table rows
        if stripped.startswith("|") and stripped.endswith("|"):
            if re.match(r'^\|[\s\-:|]+\|$', stripped):
                continue
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            in_table = True
            cells = [c for c in stripped.split("|")[1:-1]]
            table_rows.append(cells)
            continue
        if in_table:
            flush_table()
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

    if in_table:
        flush_table()
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

    for pattern in ["STRAT-*.md", "RHAISTRAT-*.md"]:
        for path in sorted(glob.glob(os.path.join(run_dir, "strat-tasks", pattern))):
            try:
                meta, body = read_frontmatter(path)
                strat_id = meta.get("strat_id", Path(path).stem)
                tasks[strat_id] = {"meta": meta, "body": body}
            except Exception as e:
                print(f"  Warning: {path}: {e}", file=sys.stderr)

    for pattern in ["STRAT-*-review.md", "RHAISTRAT-*-review.md"]:
        for path in sorted(glob.glob(os.path.join(run_dir, "strat-reviews", pattern))):
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

        scores = rev_meta.get("scores", {})
        strategies.append({
            "strat_id": strat_id,
            "title": meta.get("title", ""),
            "source_rfe": source_rfe,
            "priority": meta.get("priority", "—"),
            "size": cfg.get("size", "—"),
            "baseline": cfg.get("baseline", False),
            "cross_component": False,
            "recommendation": rev_meta.get("recommendation", "—"),
            "needs_attention": rev_meta.get("needs_attention", False),
            "feasibility": reviewers.get("feasibility", "—"),
            "testability": reviewers.get("testability", "—"),
            "scope": reviewers.get("scope", "—"),
            "architecture": reviewers.get("architecture", "—"),
            "scores": {
                "feasibility": scores.get("feasibility"),
                "testability": scores.get("testability"),
                "scope": scores.get("scope"),
                "architecture": scores.get("architecture"),
                "total": scores.get("total"),
            } if scores else None,
            "strategy_html": md_to_html(task.get("body", "")),
            "review_html": md_to_html(review.get("body", "")),
            "labels": compute_strat_labels(
                meta.get("status", ""),
                rev_meta.get("recommendation", ""),
                reviewers,
            ),
        })

    reviewed = [s for s in strategies if s["recommendation"] not in ("—", "")]
    total = len(strategies)
    total_reviewed = len(reviewed)

    # Skip runs where review stage didn't complete (no reviewed strategies)
    if total_reviewed == 0:
        return None

    approved = sum(1 for s in reviewed if is_approve(s["recommendation"]))
    revise = sum(1 for s in reviewed if is_revise(s["recommendation"]))

    dimensions = ["feasibility", "testability", "scope", "architecture"]
    dim_stats = {}
    for dim in dimensions:
        scored_vals = [s["scores"][dim] for s in strategies
                       if s.get("scores") and s["scores"].get(dim) is not None]
        dim_total = len(scored_vals)
        dim_pass = sum(1 for v in scored_vals if v == 2)
        dim_partial = sum(1 for v in scored_vals if v == 1)
        dim_fail = sum(1 for v in scored_vals if v == 0)
        dim_sum = sum(scored_vals)
        dim_max = dim_total * 2
        dim_stats[dim] = {
            "total": dim_total,
            "pass": dim_pass,
            "partial": dim_partial,
            "fail": dim_fail,
            "rate": pct(dim_sum, dim_max),
        }

    weakest_dim = min(dimensions, key=lambda d: dim_stats[d]["rate"])
    strongest_dim = max(dimensions, key=lambda d: dim_stats[d]["rate"])

    # First-pass quality score: % of all dimension scores that are 2/2
    total_checks = sum(dim_stats[d]["total"] for d in dimensions)
    total_passes = sum(dim_stats[d]["pass"] for d in dimensions)
    quality_score = pct(total_passes, total_checks)

    # Numeric score aggregates (when scores are available)
    scored = [s for s in strategies if s.get("scores") and s["scores"].get("total") is not None]
    has_scores = len(scored) > 0
    avg_total_score = round(sum(s["scores"]["total"] for s in scored) / len(scored), 1) if scored else None
    dim_avg_scores = {}
    for dim in dimensions:
        vals = [s["scores"][dim] for s in scored if s["scores"].get(dim) is not None]
        dim_avg_scores[dim] = round(sum(vals) / len(vals), 2) if vals else None

    # Verdict distribution (4-way)
    split_count = sum(1 for s in reviewed if s["recommendation"] == "split")
    reject_count = sum(1 for s in reviewed if is_reject(s["recommendation"]))
    needs_attention = sum(1 for s in reviewed if s.get("needs_attention", False))

    return {
        "total": total,
        "reviewed": total_reviewed,
        "approved": approved,
        "revise": revise,
        "split": split_count,
        "reject": reject_count,
        "needs_attention": needs_attention,
        "approval_rate": pct(approved, total_reviewed),
        "revision_rate": pct(revise, total_reviewed),
        "quality_score": quality_score,
        "has_scores": has_scores,
        "avg_total_score": avg_total_score,
        "dim_avg_scores": dim_avg_scores,
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
    cumulative = 0
    for i, run in enumerate(runs):
        cumulative += run["reviewed"]
        run["cumulative_reviewed"] = cumulative
        if i == 0:
            run["delta_approval"] = None
            run["delta_revision"] = None
        else:
            prev = runs[i - 1]
            run["delta_approval"] = run["approval_rate"] - prev["approval_rate"]
            run["delta_revision"] = run["revision_rate"] - prev["revision_rate"]


def compute_executive_summary(runs):
    """Dedup strategies across all runs, keeping the most recent version of each.

    For each unique strategy ID, picks the latest run that contains it.
    Returns aggregate KPIs and the deduped strategy list.
    """
    # Runs are sorted oldest-first; iterate newest-first for dedup
    seen = {}
    for run in reversed(runs):
        for s in run["strategies"]:
            strat_id = s["strat_id"]
            if strat_id not in seen:
                seen[strat_id] = {
                    **s,
                    "run_id": run["run_id"],
                    "run_label": run["label"],
                }

    strategies = sorted(seen.values(), key=lambda s: s["strat_id"])

    total = len(strategies)
    reviewed = [s for s in strategies if s["recommendation"] not in ("—", "")]
    total_reviewed = len(reviewed)
    approved = sum(1 for s in reviewed if is_approve(s["recommendation"]))
    revise = sum(1 for s in reviewed if is_revise(s["recommendation"]))
    reject = sum(1 for s in reviewed if is_reject(s["recommendation"]))
    split_count = sum(1 for s in reviewed if is_split(s["recommendation"]))
    needs_attention = sum(1 for s in reviewed if s.get("needs_attention", False))

    dimensions = ["feasibility", "testability", "scope", "architecture"]
    dim_stats = {}
    for dim in dimensions:
        scored_vals = [s["scores"][dim] for s in strategies
                       if s.get("scores") and s["scores"].get(dim) is not None]
        dim_total = len(scored_vals)
        dim_pass = sum(1 for v in scored_vals if v == 2)
        dim_partial = sum(1 for v in scored_vals if v == 1)
        dim_fail = sum(1 for v in scored_vals if v == 0)
        dim_sum = sum(scored_vals)
        dim_max = dim_total * 2
        dim_stats[dim] = {
            "total": dim_total,
            "pass": dim_pass,
            "partial": dim_partial,
            "fail": dim_fail,
            "rate": pct(dim_sum, dim_max),
        }

    scored = [s for s in strategies
              if s.get("scores") and s["scores"].get("total") is not None]
    avg_total_score = (round(sum(s["scores"]["total"] for s in scored) / len(scored), 1)
                       if scored else None)

    weakest_dim = min(dimensions, key=lambda d: dim_stats[d]["rate"]) if strategies else "—"
    strongest_dim = max(dimensions, key=lambda d: dim_stats[d]["rate"]) if strategies else "—"

    return {
        "total": total,
        "reviewed": total_reviewed,
        "approved": approved,
        "revise": revise,
        "reject": reject,
        "split": split_count,
        "needs_attention": needs_attention,
        "approval_rate": pct(approved, total_reviewed),
        "revision_rate": pct(revise, total_reviewed),
        "reject_rate": pct(reject, total_reviewed),
        "avg_total_score": avg_total_score,
        "dimensions": dim_stats,
        "weakest_dim": weakest_dim,
        "strongest_dim": strongest_dim,
        "strategies": strategies,
        "total_runs": len(runs),
    }


# ─── HTML generation ──────────────────────────────────────────────────────────

def _delta_html(current, prev, field, is_pct=True):
    """Render a delta comparison vs previous run. Green if +, red if -."""
    if not current or not prev:
        return '<span style="color:#6e7681">first run</span>' if current else ''
    delta = current[field] - prev[field]
    if delta == 0:
        suffix = '%' if is_pct else ''
        return f'<span style="color:#6e7681">0{suffix} vs prev</span>'
    color = '#3fb950' if delta > 0 else '#f85149'
    sign = '+' if delta > 0 else ''
    suffix = '%' if is_pct else ''
    return f'<span style="color:{color}">{sign}{delta}{suffix} vs prev</span>'


def generate_dashboard(runs, exec_summary, output_path):
    """Generate the full dashboard HTML."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    current = runs[-1] if runs else None
    prev = runs[-2] if len(runs) >= 2 else None

    # Prepare JSON data (strip strategy HTML bodies for overview; keep for detail)
    runs_json = json.dumps(runs, indent=None)
    exec_json = json.dumps(exec_summary, indent=None)

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
<title>AgenticCI — Strat Refinement & Review Dashboard</title>
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
.grid-cell {{ width: 40px; height: 24px; border-radius: 4px; border: 2px solid; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 600; }}
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
.verdict-split {{ color: #f78166; font-weight: 600; }}
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

/* Pipeline labels */
.label-bar {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }}
.label-badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
.label-provenance {{ background: #1c2333; color: #8b949e; }}
.label-stage {{ background: #0d419d; color: #58a6ff; }}
.label-gate {{ background: #23302a; color: #3fb950; }}
.label-gate-pending {{ background: #2d2400; color: #d29922; }}
.label-escalation {{ background: #2d1418; color: #f85149; }}
.label-legend {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-top: 24px; }}
.label-legend h3 {{ color: #f0f6fc; font-size: 14px; margin-bottom: 12px; }}
.label-legend table {{ margin-bottom: 0; }}
.label-legend td, .label-legend th {{ font-size: 12px; padding: 6px 12px; }}

@media (max-width: 900px) {{
    .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .charts-grid {{ grid-template-columns: 1fr; }}
    .two-col {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>

<div class="header">
    <h1>AgenticCI — AI First — Strat Refinement & Review Dashboard</h1>
    <div class="subtitle">Generated {timestamp} | {len(runs)} run(s) tracked</div>
</div>

<div style="background:#1c1f26;border:1px solid #30363d;border-left:4px solid #58a6ff;border-radius:8px;padding:20px 24px;margin-bottom:24px;line-height:1.7">
    <div style="font-size:15px;font-weight:600;color:#58a6ff;margin-bottom:8px">Scored Review Pipeline</div>
    <div style="font-size:13px;color:#8b949e">
        Strategies are scored on <strong style="color:#c9d1d9">four dimensions</strong> (Feasibility, Testability, Scope, Architecture) using a <strong style="color:#c9d1d9">calibrated rubric</strong> with 12 examples from real pipeline output.
        Each dimension is scored 0–2. Total: 8 points. Verdicts are <strong style="color:#c9d1d9">deterministic</strong> — computed from scores by code, not LLM judgment.
        <br>
        <strong style="color:#c9d1d9">Verdict rules:</strong> APPROVE (≥6, no zeros) auto-passes. REVISE, SPLIT, and REJECT get <code style="background:#21262d;padding:2px 6px;border-radius:3px">needs-attention</code> for human review.
        All runs are <strong style="color:#c9d1d9">dry runs</strong> — no data is written to Jira.
        <br>
        <strong style="color:#c9d1d9">What to expect next:</strong> evidence-based review gates (every finding must cite specific strategy text), additional review dimensions (security, API readiness), and Jira write-back.
        <br>
        <span style="color:#6e7681">The binary gate is intentional: only APPROVE passes automatically. Everything else requires human review.</span>
    </div>
</div>

<div class="nav-tabs">
    <div class="nav-tab active" onclick="switchPage('executive')">Executive Summary</div>
    <div class="nav-tab" onclick="switchPage('overview')">Per-Run Trends</div>
    <div class="nav-tab" onclick="switchPage('run-detail')">Run Detail</div>
    <div class="nav-tab" onclick="switchPage('pipeline')">Pipeline</div>
</div>

<!-- ═══ EXECUTIVE SUMMARY PAGE ═══ -->
<div class="nav-page active" id="page-executive">
<div id="exec-content"></div>
</div>

<!-- ═══ OVERVIEW PAGE ═══ -->
<div class="nav-page" id="page-overview">

<div class="hero">
    <div class="hero-statement" style="color:{hero_color}">{escape_html(hero_text)}</div>
    <div class="hero-delta">vs previous run: {delta_arrow}</div>
    <div class="hero-sub">{len(runs)} pipeline run(s) | Latest: {current["label"] if current else "none"}</div>
</div>

<div class="kpi-grid" style="grid-template-columns: repeat(6, 1fr);">
    <div class="kpi">
        <div class="kpi-value" style="color:#58a6ff">{len(runs)}</div>
        <div class="kpi-label">Pipeline Runs</div>
        <div class="kpi-detail">{current["cumulative_reviewed"] if current else 0} strategies total</div>
    </div>
    <div class="kpi">
        <div class="kpi-value" style="color:#f0f6fc">{current["reviewed"] if current else 0}</div>
        <div class="kpi-label">Strategies Reviewed</div>
        <div class="kpi-detail">{_delta_html(current, prev, "reviewed", is_pct=False)}</div>
    </div>
    <div class="kpi">
        <div class="kpi-value" style="color:{health_color(current["approval_rate"]) if current else '#8b949e'}">{current["approval_rate"] if current else 0}%</div>
        <div class="kpi-label">Approval Rate</div>
        <div class="kpi-detail">{_delta_html(current, prev, "approval_rate")}</div>
    </div>
    <div class="kpi">
        <div class="kpi-value" style="color:{health_color(int(current["avg_total_score"] / 8 * 100) if current and current.get("avg_total_score") else 0) if current else '#8b949e'}">{current["avg_total_score"] if current and current.get("avg_total_score") is not None else "—"}<span style="font-size:16px;color:#6e7681">/8</span></div>
        <div class="kpi-label">Avg Score</div>
        <div class="kpi-detail">{"Rubric: F+T+S+A (0-2 each)" if current and current.get("has_scores") else "Scoring not yet enabled"}</div>
    </div>
    <div class="kpi">
        <div class="kpi-value" style="color:#f85149">{current["needs_attention"] if current else 0}</div>
        <div class="kpi-label">Needs Attention</div>
        <div class="kpi-detail">{"Human review required" if current and current.get("needs_attention", 0) > 0 else "All clear"}</div>
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
    <div class="chart-card">
        <h3>Review Dimensions Over Time</h3>
        <p style="color:#6e7681;font-size:12px;margin-bottom:8px">Per-dimension approval rate. Shows which dimension is the bottleneck.</p>
        <canvas id="chart-dimensions"></canvas>
    </div>
    <div class="chart-card">
        <h3>First-Pass Quality Score</h3>
        <p style="color:#6e7681;font-size:12px;margin-bottom:8px">% of all dimension checks (feasibility, testability, scope, architecture) that pass per run.</p>
        <canvas id="chart-quality"></canvas>
    </div>
    <div class="chart-card">
        <h3>Average Score Trend</h3>
        <p style="color:#6e7681;font-size:12px;margin-bottom:8px">Mean total score per run (0-8). Threshold for approval: 6/8.</p>
        <canvas id="chart-avg-score"></canvas>
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
<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:24px;position:relative">
    <h2 style="color:#f0f6fc;font-size:16px;margin-bottom:16px;flex-shrink:0">RHAI Agentic SDLC Pipeline</h2>
    <div style="position:absolute;top:16px;right:16px;display:flex;gap:4px;z-index:10">
        <button class="zoom-btn" onclick="zoomDiagram(1.2)" title="Zoom in">+</button>
        <button class="zoom-btn" onclick="zoomDiagram(0.8)" title="Zoom out">&minus;</button>
        <button class="zoom-btn" onclick="resetDiagram()" title="Reset">&#8634;</button>
    </div>
    <div id="diagram-container" style="overflow:auto;position:relative">
    <div id="diagram-inner" style="transform-origin:0 0;transition:transform 0.1s ease;display:flex;align-items:center;justify-content:center;padding:24px 0;font-size:16px">
    <pre class="mermaid">
graph LR
    subgraph P1["Phase 1: RFE Assessment"]
        A[rfe.create] --> B[rfe.review]
        B --> C[rfe.auto-fix]
        C --> D[rfe.submit]
    end

    D -->|"Automatically\\njob trigger"| E

    subgraph P2["Phase 2: Strategy Refinement"]
        E[strategy.create]

        subgraph SR["strategy.refine"]
            F1[Fetch arch context] --> F2[Technical approach]
            F2 --> F3[Dependencies &\\ncomponents]
            F3 --> F4[Effort estimate\\n& risks]
        end

        E -->|"+strat-creator-auto-created\\n+strat-creator-draft"| F1
        F4 -->|"+strat-creator-auto-refined\\ndraft &#8594; strat-creator-refined"| G{{{{refined}}}}

        subgraph SV["strategy.review"]
            R1[feasibility]
            R2[testability]
            R3[scope]
            R4[architecture]
            SC1["assess-strat\\nscorer agent\\nF/T/S/A 0-2"]
            SCRIPTS["parse_results.py &#8594; apply_scores.py\\n(deterministic verdicts)"]
            CON[Write review file\\nscores + prose]
            R1 & R2 & R3 & R4 --> SC1
            SC1 --> SCRIPTS
            SCRIPTS --> CON
        end

        G --> R1 & R2 & R3 & R4
        CON --> Q{{{{&#8805;6/8\\nno zeros?}}}}
        Q -->|"APPROVE\\n+approved +review-pass"| I[strategy.submit]
        I --> KO["Kick off Phase 3"]
        Q -->|"REVISE / SPLIT / REJECT\\n+needs-attention"| P["Human review"]
        P -->|"Human fixes &\\nremoves needs-attention"| G
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
    style SC1 fill:#c77d1a,color:#fff
    style SCRIPTS fill:#6e40c9,color:#fff
    style R1 fill:#c77d1a,color:#fff
    style R2 fill:#c77d1a,color:#fff
    style R3 fill:#c77d1a,color:#fff
    style R4 fill:#c77d1a,color:#fff
    style CON fill:#c77d1a,color:#fff
    style G fill:#1f3a5f,color:#58a6ff,stroke:#58a6ff
    style Q fill:#1f3a5f,color:#58a6ff,stroke:#58a6ff
    style P fill:#3d1f00,color:#f0883e,stroke:#f0883e
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

    <div class="label-legend">
    <h3>Pipeline Labels (strat-creator-*)</h3>
    <table>
    <thead><tr><th>Label</th><th>Category</th><th>Applied When</th></tr></thead>
    <tbody>
    <tr><td><span class="label-badge label-provenance">strat-creator-auto-created</span></td><td>Provenance</td><td>strategy.create generates the RHAISTRAT ticket</td></tr>
    <tr><td><span class="label-badge label-provenance">strat-creator-auto-refined</span></td><td>Provenance</td><td>strategy.refine enriches with technical approach</td></tr>
    <tr><td><span class="label-badge label-provenance">strat-creator-auto-revised</span></td><td>Provenance</td><td>strategy.revise modifies content after review feedback</td></tr>
    <tr><td><span class="label-badge label-stage">strat-creator-draft</span></td><td>Stage</td><td>Strategy stub exists, awaiting refinement</td></tr>
    <tr><td><span class="label-badge label-stage">strat-creator-refined</span></td><td>Stage</td><td>Full technical approach, dependencies, NFRs added</td></tr>
    <tr><td><span class="label-badge label-stage">strat-creator-reviewed</span></td><td>Stage</td><td>Scored and reviewed by 4 independent reviewers</td></tr>
    <tr><td><span class="label-badge label-stage">strat-creator-approved</span></td><td>Stage</td><td>Score &#8805;6/8 with no zeros — auto-approved</td></tr>
    <tr><td><span class="label-badge label-gate">strat-creator-review-pass</span></td><td>Gate</td><td>Approved; excluded from re-processing in future runs</td></tr>
    <tr><td><span class="label-badge label-escalation">strat-creator-needs-attention</span></td><td>Escalation</td><td>REVISE / SPLIT / REJECT — human review required</td></tr>
    <tr><td><span class="label-badge label-escalation">strat-creator-ignore</span></td><td>Exclusion</td><td>Permanent exclusion from pipeline (human-set only)</td></tr>
    </tbody>
    </table>
    </div>

</div>
</div><!-- end pipeline -->

<div class="footer">
    strat-creator pipeline | RHAI Agentic SDLC
</div>

<script>
const RUNS = {runs_json};
const EXEC = {exec_json};

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
    document.querySelectorAll('.nav-tab')[2].classList.add('active');
}}

// ─── Executive summary ──────────────────────────────────────────────────────
function renderExecutiveSummary() {{
    const e = EXEC;
    const el = document.getElementById('exec-content');
    const dims = ['feasibility','testability','scope','architecture'];
    const rate = e.approval_rate;
    const heroColor = healthColor(rate);
    const avgScoreHtml = e.avg_total_score !== null && e.avg_total_score !== undefined
        ? `${{e.avg_total_score}}<span style="font-size:16px;color:#6e7681">/8</span>`
        : '—';
    const avgScorePct = e.avg_total_score !== null ? Math.round(e.avg_total_score / 8 * 100) : 0;

    let html = `<div class="hero">
        <div class="hero-statement" style="color:${{heroColor}}">${{e.approved}} of ${{e.reviewed}} unique strategies approved (${{rate}}%)</div>
        <div class="hero-sub">${{e.total}} unique strategies across ${{e.total_runs}} pipeline runs | Deduped by most recent run per strategy</div>
    </div>`;

    // KPI cards
    html += `<div class="kpi-grid" style="grid-template-columns: repeat(4, 1fr)">
        <div class="kpi"><div class="kpi-value" style="color:#58a6ff">${{e.total}}</div><div class="kpi-label">Unique Strategies</div><div class="kpi-detail">Across ${{e.total_runs}} runs</div></div>
        <div class="kpi"><div class="kpi-value" style="color:${{heroColor}}">${{rate}}%</div><div class="kpi-label">Approval Rate</div><div class="kpi-detail">${{e.approved}} approved</div></div>
        <div class="kpi"><div class="kpi-value" style="color:${{healthColor(avgScorePct)}}">${{avgScoreHtml}}</div><div class="kpi-label">Avg Score</div><div class="kpi-detail">Threshold: 6/8</div></div>
        <div class="kpi"><div class="kpi-value" style="color:#f85149">${{e.needs_attention}}</div><div class="kpi-label">Needs Attention</div><div class="kpi-detail">${{e.needs_attention === 0 ? 'All clear' : 'Staff engineer review'}}</div></div>
    </div>`;

    // Verdict distribution
    html += `<div class="two-col">`;

    // Left: verdict donut
    html += `<div class="chart-card"><h3>Verdict Distribution</h3>
        <div style="display:flex;align-items:center;gap:24px">
        <canvas id="exec-donut" width="200" height="200" style="max-width:200px"></canvas>
        <div style="font-size:13px;line-height:2">
            <div><span style="display:inline-block;width:12px;height:12px;background:#3fb950;border-radius:2px;margin-right:6px"></span>Approve: <strong>${{e.approved}}</strong></div>
            <div><span style="display:inline-block;width:12px;height:12px;background:#d29922;border-radius:2px;margin-right:6px"></span>Revise: <strong>${{e.revise}}</strong></div>
            <div><span style="display:inline-block;width:12px;height:12px;background:#f78166;border-radius:2px;margin-right:6px"></span>Split: <strong>${{e.split}}</strong></div>
            <div><span style="display:inline-block;width:12px;height:12px;background:#f85149;border-radius:2px;margin-right:6px"></span>Reject: <strong>${{e.reject}}</strong></div>
        </div>
        </div>
    </div>`;

    // Right: dimension health bars
    html += `<div class="chart-card"><h3>Quality by Dimension</h3>`;
    dims.forEach(dim => {{
        const ds = e.dimensions[dim];
        const drate = ds.rate;
        const pw = ds.total > 0 ? Math.round(100*(ds.pass||0)/ds.total) : 0;
        const partw = ds.total > 0 ? Math.round(100*(ds.partial||0)/ds.total) : 0;
        const fw = ds.total > 0 ? Math.round(100*(ds.fail||0)/ds.total) : 0;
        html += `<div class="dim-row" style="margin-bottom:8px">
            <div class="dim-label" style="width:100px">${{dim.charAt(0).toUpperCase()+dim.slice(1)}}</div>
            <div class="dim-bar-container"><div class="dim-bar-track">
                <div class="dim-bar-seg" style="width:${{pw}}%;background:#3fb950" title="${{ds.pass||0}} scored 2/2"></div>
                <div class="dim-bar-seg" style="width:${{partw}}%;background:#d29922" title="${{ds.partial||0}} scored 1/2"></div>
                <div class="dim-bar-seg" style="width:${{fw}}%;background:#f85149" title="${{ds.fail||0}} scored 0/2"></div>
            </div></div>
            <div class="dim-rate" style="color:${{healthColor(drate)}}">${{drate}}%</div>
        </div>`;
    }});
    html += `<div style="display:flex;gap:16px;margin-top:8px;font-size:11px;color:#6e7681">
        <span><span style="display:inline-block;width:10px;height:10px;background:#3fb950;border-radius:2px;margin-right:4px"></span>2/2 (pass)</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#d29922;border-radius:2px;margin-right:4px"></span>1/2 (gaps)</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#f85149;border-radius:2px;margin-right:4px"></span>0/2 (fail)</span>
    </div></div>`;
    html += `</div>`;

    // Attention funnel
    const readyCount = e.reviewed - e.needs_attention;
    html += `<div class="two-col">
        <div class="chart-card"><h3>Readiness Funnel</h3>
        <div style="display:flex;flex-direction:column;gap:8px">
            <div style="display:flex;align-items:center;gap:12px">
                <div style="background:#23302a;border-radius:6px;height:32px;display:flex;align-items:center;padding:0 16px;width:${{e.total > 0 ? Math.max(Math.round(100*e.total/e.total), 10) : 10}}%;min-width:fit-content">
                    <span style="color:#3fb950;font-weight:600">${{e.total}}</span></div>
                <span style="color:#8b949e;font-size:13px">Total strategies created</span>
            </div>
            <div style="display:flex;align-items:center;gap:12px">
                <div style="background:#1f3a5f;border-radius:6px;height:32px;display:flex;align-items:center;padding:0 16px;width:${{e.total > 0 ? Math.max(Math.round(100*e.reviewed/e.total), 10) : 10}}%;min-width:fit-content">
                    <span style="color:#58a6ff;font-weight:600">${{e.reviewed}}</span></div>
                <span style="color:#8b949e;font-size:13px">Reviewed</span>
            </div>
            <div style="display:flex;align-items:center;gap:12px">
                <div style="background:#23302a;border-radius:6px;height:32px;display:flex;align-items:center;padding:0 16px;width:${{e.total > 0 ? Math.max(Math.round(100*readyCount/e.total), 10) : 10}}%;min-width:fit-content">
                    <span style="color:#3fb950;font-weight:600">${{readyCount}}</span></div>
                <span style="color:#8b949e;font-size:13px">Ready for implementation</span>
            </div>
            <div style="display:flex;align-items:center;gap:12px">
                <div style="background:#2d1418;border-radius:6px;height:32px;display:flex;align-items:center;padding:0 16px;width:${{e.total > 0 ? Math.max(Math.round(100*e.needs_attention/e.total), 10) : 10}}%;min-width:fit-content">
                    <span style="color:#f85149;font-weight:600">${{e.needs_attention}}</span></div>
                <span style="color:#8b949e;font-size:13px">Needs staff engineer input</span>
            </div>
        </div>
        </div>
        <div class="chart-card"><h3>Score Distribution</h3>
            <canvas id="exec-histogram"></canvas>
        </div>
    </div>`;

    // Per-strategy table
    html += `<div class="grid-section"><h3>All Unique Strategies (deduped)</h3>
    <table><thead><tr>
        <th>Strat ID</th><th>Title</th><th>Source RFE</th><th>Priority</th>
        <th>F</th><th>T</th><th>S</th><th>A</th><th>Score</th><th>Verdict</th><th>Attention</th><th>Run</th>
    </tr></thead><tbody>`;
    e.strategies.forEach(s => {{
        const sc = s.scores;
        let scoreCells = '';
        if (sc) {{
            ['feasibility','testability','scope','architecture'].forEach(d => {{
                const v = sc[d];
                scoreCells += `<td style="${{scoreStyle(v)}};text-align:center;font-weight:600">${{v !== null && v !== undefined ? v : '—'}}</td>`;
            }});
            const totalPct = sc.total !== null ? Math.round(sc.total / 8 * 100) : 0;
            scoreCells += `<td style="color:${{healthColor(totalPct)}};font-weight:600;text-align:center">${{sc.total}}/8</td>`;
        }} else {{
            scoreCells += '<td>—</td><td>—</td><td>—</td><td>—</td><td>—</td>';
        }}
        const attentionHtml = s.needs_attention
            ? '<span style="color:#f85149;font-weight:600">&#9679; Yes</span>'
            : '<span style="color:#3fb950">&#10003;</span>';
        html += `<tr>
            <td><strong>${{s.strat_id}}</strong></td>
            <td>${{s.title}}</td>
            <td>${{s.source_rfe}}</td>
            <td>${{s.priority}}</td>
            ${{scoreCells}}
            <td class="${{verdictClass(s.recommendation)}}">${{verdictLabel(s.recommendation)}}</td>
            <td style="text-align:center">${{attentionHtml}}</td>
            <td style="font-size:12px;color:#6e7681">${{s.run_label}}</td>
        </tr>`;
    }});
    html += '</tbody></table></div>';

    el.innerHTML = html;

    // Donut chart
    new Chart(document.getElementById('exec-donut'), {{
        type: 'doughnut',
        data: {{
            labels: ['Approve', 'Revise', 'Split', 'Reject'],
            datasets: [{{
                data: [e.approved, e.revise, e.split, e.reject],
                backgroundColor: ['#3fb950', '#d29922', '#f78166', '#f85149'],
                borderWidth: 0,
                hoverOffset: 6,
            }}]
        }},
        options: {{
            responsive: true,
            cutout: '60%',
            plugins: {{
                legend: {{ display: false }},
            }},
        }},
    }});

    // Score histogram
    const scoreBuckets = [0,0,0,0,0,0,0,0,0]; // 0-8
    e.strategies.forEach(s => {{
        if (s.scores && s.scores.total !== null && s.scores.total !== undefined) {{
            scoreBuckets[s.scores.total]++;
        }}
    }});
    new Chart(document.getElementById('exec-histogram'), {{
        type: 'bar',
        data: {{
            labels: ['0','1','2','3','4','5','6','7','8'],
            datasets: [{{
                label: 'Strategies',
                data: scoreBuckets,
                backgroundColor: scoreBuckets.map((_, i) => i >= 6 ? '#3fb950' : i >= 3 ? '#d29922' : '#f85149'),
                borderRadius: 4,
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{ display: false }},
                annotation: {{
                    annotations: {{
                        threshold: {{
                            type: 'line',
                            xMin: 5.5, xMax: 5.5,
                            borderColor: '#3fb950',
                            borderWidth: 2,
                            borderDash: [6, 3],
                            label: {{
                                display: true,
                                content: 'Approve threshold',
                                position: 'start',
                                color: '#3fb950',
                                font: {{ size: 10 }},
                                backgroundColor: 'rgba(0,0,0,0.7)',
                            }}
                        }}
                    }}
                }}
            }},
            scales: {{
                x: {{ title: {{ display: true, text: 'Total Score', color: '#6e7681' }}, grid: {{ display: false }} }},
                y: {{ title: {{ display: true, text: 'Count', color: '#6e7681' }}, ticks: {{ stepSize: 1 }}, grid: {{ color: '#161b22' }} }},
            }},
        }},
    }});
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
    if (v === 'split') return 'verdict-split';
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
    if (v === 'split') return 'background:#2d1a0d;border-color:#f78166';
    if (['reject','rejected','infeasible'].includes(v)) return 'background:#2d1418;border-color:#f85149';
    return 'background:#161b22;border-color:#30363d';
}}

function scoreStyle(score) {{
    if (score === 2) return 'background:#23302a;border-color:#3fb950;color:#3fb950';
    if (score === 1) return 'background:#2d2400;border-color:#d29922;color:#d29922';
    if (score === 0) return 'background:#2d1418;border-color:#f85149;color:#f85149';
    return 'background:#161b22;border-color:#30363d;color:#6e7681';
}}

function scoreText(score) {{
    if (score === null || score === undefined) return '—';
    return score + '/2';
}}

function labelCssClass(label) {{
    if (label.includes('needs-attention') || label.includes('ignore')) return 'label-escalation';
    if (label.includes('review-pass')) return 'label-gate';
    if (label.includes('auto-')) return 'label-provenance';
    return 'label-stage';
}}

function renderLabelBadges(labels) {{
    if (!labels || !labels.length) return '';
    return labels.map(l => `<span class="label-badge ${{labelCssClass(l)}}">${{l}}</span>`).join(' ');
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
    const avgScoreHtml = r.avg_total_score !== null && r.avg_total_score !== undefined
        ? `${{r.avg_total_score}}<span style="font-size:14px;color:#6e7681">/8</span>`
        : '—';
    const avgScorePct = r.avg_total_score !== null ? Math.round(r.avg_total_score / 8 * 100) : 0;
    html += `<div class="kpi-grid" style="grid-template-columns: repeat(6, 1fr)">
        <div class="kpi"><div class="kpi-value" style="color:#f0f6fc">${{r.reviewed}}</div><div class="kpi-label">Reviewed</div></div>
        <div class="kpi"><div class="kpi-value" style="color:${{healthColor(r.approval_rate)}}">${{r.approval_rate}}%</div><div class="kpi-label">Approval Rate</div></div>
        <div class="kpi"><div class="kpi-value" style="color:${{healthColor(avgScorePct)}}">${{avgScoreHtml}}</div><div class="kpi-label">Avg Score</div></div>
        <div class="kpi"><div class="kpi-value" style="color:#f85149">${{r.needs_attention || 0}}</div><div class="kpi-label">Needs Attention</div></div>
        <div class="kpi"><div class="kpi-value" style="color:${{healthColor(100-r.revision_rate)}}">${{r.revision_rate}}%</div><div class="kpi-label">Revision Rate</div></div>
        <div class="kpi"><div class="kpi-value" style="color:${{healthColor(r.weakest_rate)}}">${{r.weakest_rate}}%</div><div class="kpi-label">Weakest: ${{r.weakest_dim.charAt(0).toUpperCase()+r.weakest_dim.slice(1)}}</div></div>
    </div>`;

    // Two-col: dimension bars + verdict grid
    // Dimension bars
    let dimHtml = '<div class="dim-section"><h3>Review Dimensions</h3>';
    dims.forEach(dim => {{
        const ds = r.dimensions[dim];
        const rate = ds.rate;
        const pw = ds.total > 0 ? Math.round(100*(ds.pass||0)/ds.total) : 0;
        const partw = ds.total > 0 ? Math.round(100*(ds.partial||0)/ds.total) : 0;
        const fw = ds.total > 0 ? Math.round(100*(ds.fail||0)/ds.total) : 0;
        dimHtml += `<div class="dim-row">
            <div class="dim-label">${{dim.charAt(0).toUpperCase()+dim.slice(1)}}</div>
            <div class="dim-bar-container"><div class="dim-bar-track">
                <div class="dim-bar-seg" style="width:${{pw}}%;background:#3fb950" title="${{ds.pass||0}} scored 2/2"></div>
                <div class="dim-bar-seg" style="width:${{partw}}%;background:#d29922" title="${{ds.partial||0}} scored 1/2"></div>
                <div class="dim-bar-seg" style="width:${{fw}}%;background:#f85149" title="${{ds.fail||0}} scored 0/2"></div>
            </div></div>
            <div class="dim-rate" style="color:${{healthColor(rate)}}">${{rate}}%</div>
        </div>`;
    }});
    dimHtml += `<div style="display:flex;gap:16px;margin-top:12px;font-size:11px;color:#6e7681">
        <span><span style="display:inline-block;width:10px;height:10px;background:#3fb950;border-radius:2px;margin-right:4px"></span>2/2 (pass)</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#d29922;border-radius:2px;margin-right:4px"></span>1/2 (gaps)</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#f85149;border-radius:2px;margin-right:4px"></span>0/2 (fail)</span>
    </div></div>`;

    // Verdict grid with numeric scores
    let gridHtml = `<div class="grid-section"><h3>Per-Strategy Scores</h3>
        <div class="grid-header">
            <div class="grid-header-id">Strategy</div>
            <div class="grid-header-dim">Feas</div>
            <div class="grid-header-dim">Test</div>
            <div class="grid-header-dim">Scope</div>
            <div class="grid-header-dim">Arch</div>
            <div class="grid-header-dim">Total</div>
            <div class="grid-header-verdict">Verdict</div>
        </div>`;
    r.strategies.forEach(s => {{
        const sid = s.strat_id.replace('STRAT-','');
        const sc = s.scores;
        let cells = '';
        if (sc) {{
            dims.forEach(d => {{
                const v = sc[d];
                cells += `<div class="grid-cell" style="${{scoreStyle(v)}}" title="${{d}}: ${{scoreText(v)}}">${{scoreText(v)}}</div>`;
            }});
            const totalPct = sc.total !== null ? Math.round(sc.total / 8 * 100) : 0;
            cells += `<div class="grid-cell" style="color:${{healthColor(totalPct)}};font-weight:600" title="Total: ${{sc.total}}/8">${{sc.total}}/8</div>`;
        }} else {{
            dims.forEach(d => {{
                cells += `<div class="grid-cell" style="${{cellStyle(s[d])}}" title="${{d}}: ${{s[d]}}"></div>`;
            }});
            cells += `<div class="grid-cell" style="color:#6e7681">—</div>`;
        }}
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
        <th>F</th><th>T</th><th>S</th><th>A</th><th>Score</th><th>Verdict</th><th>Attention</th>
    </tr></thead><tbody>`;
    r.strategies.forEach((s, i) => {{
        let badges = '';
        if (s.baseline) badges += ' <span class="badge badge-baseline">baseline</span>';
        if (s.cross_component) badges += ' <span class="badge badge-cross">cross-component</span>';
        const sc = s.scores;
        let scoreCells = '';
        if (sc) {{
            ['feasibility','testability','scope','architecture'].forEach(d => {{
                const v = sc[d];
                scoreCells += `<td style="${{scoreStyle(v)}};text-align:center;font-weight:600">${{v !== null && v !== undefined ? v : '—'}}</td>`;
            }});
            const totalPct = sc.total !== null ? Math.round(sc.total / 8 * 100) : 0;
            scoreCells += `<td style="color:${{healthColor(totalPct)}};font-weight:600;text-align:center">${{sc.total}}/8</td>`;
        }} else {{
            scoreCells += `<td class="${{verdictClass(s.feasibility)}}">${{verdictLabel(s.feasibility)}}</td>`;
            scoreCells += `<td class="${{verdictClass(s.testability)}}">${{verdictLabel(s.testability)}}</td>`;
            scoreCells += `<td class="${{verdictClass(s.scope)}}">${{verdictLabel(s.scope)}}</td>`;
            scoreCells += `<td class="${{verdictClass(s.architecture)}}">${{verdictLabel(s.architecture)}}</td>`;
            scoreCells += `<td style="color:#6e7681;text-align:center">—</td>`;
        }}
        const attentionHtml = s.needs_attention
            ? '<span style="color:#f85149;font-weight:600">&#9679; Yes</span>'
            : '<span style="color:#3fb950">&#10003;</span>';
        html += `<tr class="clickable" onclick="toggleRunDetail(${{idx}},${{i}})">
            <td><span class="expand-icon" id="ricon-${{idx}}-${{i}}">&#9654;</span></td>
            <td><strong>${{s.strat_id}}</strong></td>
            <td>${{s.title}}${{badges}}</td>
            <td>${{s.source_rfe}}</td>
            <td><span class="badge badge-size">${{s.size}}</span></td>
            ${{scoreCells}}
            <td class="${{verdictClass(s.recommendation)}}">${{verdictLabel(s.recommendation)}}</td>
            <td style="text-align:center">${{attentionHtml}}</td>
        </tr>
        <tr><td colspan="10" style="padding:0">
            <div class="detail-panel" id="rpanel-${{idx}}-${{i}}">
                <h2>${{s.strat_id}}: ${{s.title}}</h2>
                <div class="label-bar">${{renderLabelBadges(s.labels || [])}}</div>
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
                label: 'Split',
                data: RUNS.map(r => r.split || 0),
                backgroundColor: '#f78166',
                borderRadius: 4,
            }}, {{
                label: 'Reject',
                data: RUNS.map(r => r.reject || 0),
                backgroundColor: '#f85149',
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

    // First-pass quality score
    new Chart(document.getElementById('chart-quality'), {{
        type: 'line',
        data: {{
            labels,
            datasets: [{{
                label: 'Quality Score %',
                data: RUNS.map(r => r.quality_score),
                borderColor: '#a371f7',
                backgroundColor: 'rgba(163,113,247,0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 6,
                pointHoverRadius: 8,
                pointBackgroundColor: '#a371f7',
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
                x: {{ grid: {{ display: false }} }},
            }},
        }},
    }});

    // Average score trend
    new Chart(document.getElementById('chart-avg-score'), {{
        type: 'line',
        data: {{
            labels,
            datasets: [{{
                label: 'Avg Score',
                data: RUNS.map(r => r.avg_total_score),
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88,166,255,0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 6,
                pointHoverRadius: 8,
                pointBackgroundColor: '#58a6ff',
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{ display: false }},
                annotation: {{
                    annotations: {{
                        threshold: {{
                            type: 'line',
                            yMin: 6, yMax: 6,
                            borderColor: '#3fb950',
                            borderWidth: 2,
                            borderDash: [6, 3],
                            label: {{
                                display: true,
                                content: 'Approval threshold (6)',
                                position: 'start',
                                color: '#3fb950',
                                font: {{ size: 11 }},
                                backgroundColor: 'rgba(0,0,0,0.7)',
                            }}
                        }}
                    }}
                }}
            }},
            scales: {{
                y: {{
                    min: 0, max: 8,
                    ticks: {{ stepSize: 1 }},
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
renderExecutiveSummary();
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
    parser.add_argument("--config", "-c", default=None,
                        help="Optional config file for size/baseline metadata")
    parser.add_argument("--output", "-o", default="/tmp/dashboard/index.html",
                        help="Output HTML file path")
    parser.add_argument("--max-runs", type=int, default=30,
                        help="Maximum number of runs to include (default: 30)")
    args = parser.parse_args()

    # Load config (optional — provides size/baseline metadata)
    config = {}
    if args.config and os.path.exists(args.config):
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
    exec_summary = compute_executive_summary(runs)
    print(f"Executive summary: {exec_summary['total']} unique strategies "
          f"({exec_summary['approved']} approved, {exec_summary['needs_attention']} need attention)")
    generate_dashboard(runs, exec_summary, args.output)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate an HTML report from strategy pipeline artifacts.

Reads strat-tasks/, strat-reviews/, and config/test-rfes.yaml to produce
a self-contained HTML report with summary table and drill-down details.

Usage:
    python3 scripts/generate-report.py [--output artifacts/report.html]
"""

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Add scripts/ to path for frontmatter imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from artifact_utils import read_frontmatter

def load_yaml_config(path):
    """Read test-rfes.yaml and return dict keyed by RFE ID."""
    import yaml
    with open(path) as f:
        data = yaml.safe_load(f)
    result = {}
    for rfe in data.get("test_rfes", []):
        result[rfe["id"]] = rfe
    return result

def load_artifacts(artifacts_dir):
    """Load all strategy tasks and reviews."""
    tasks = {}
    reviews = {}

    for path in sorted(glob.glob(os.path.join(artifacts_dir, "strat-tasks", "STRAT-*.md"))):
        try:
            meta, body = read_frontmatter(path)
            strat_id = meta.get("strat_id", Path(path).stem)
            tasks[strat_id] = {"meta": meta, "body": body, "path": path}
        except Exception as e:
            print(f"Warning: failed to read {path}: {e}", file=sys.stderr)

    for path in sorted(glob.glob(os.path.join(artifacts_dir, "strat-reviews", "STRAT-*-review.md"))):
        try:
            meta, body = read_frontmatter(path)
            strat_id = meta.get("strat_id", Path(path).stem.replace("-review", ""))
            reviews[strat_id] = {"meta": meta, "body": body, "path": path}
        except Exception as e:
            print(f"Warning: failed to read {path}: {e}", file=sys.stderr)

    return tasks, reviews

def md_to_html(md_text):
    """Minimal markdown to HTML conversion for rendering in report."""
    lines = md_text.split("\n")
    html_lines = []
    in_list = False
    in_code = False
    code_block = []

    for line in lines:
        # Code blocks
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

        # Empty line
        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("")
            continue

        # Headings
        heading_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading_match:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            level = len(heading_match.group(1))
            text = inline_format(heading_match.group(2))
            html_lines.append(f"<h{level}>{text}</h{level}>")
            continue

        # List items
        list_match = re.match(r'^[\s]*[-*]\s+(.*)', line)
        if list_match:
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{inline_format(list_match.group(1))}</li>")
            continue

        # Numbered list items
        num_match = re.match(r'^[\s]*\d+\.\s+(.*)', line)
        if num_match:
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{inline_format(num_match.group(1))}</li>")
            continue

        # Regular paragraph
        if in_list:
            html_lines.append("</ul>")
            in_list = False
        html_lines.append(f"<p>{inline_format(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")
    if in_code:
        html_lines.append("<pre><code>" + escape_html("\n".join(code_block)) + "</code></pre>")

    return "\n".join(html_lines)

def escape_html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def inline_format(text):
    text = escape_html(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text

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
    return verdict or "—"

def is_approve(v):
    return v in ("approve", "approved")

def is_revise(v):
    return v in ("revise", "needs revision", "needs_revision")

def is_reject(v):
    return v in ("reject", "rejected", "infeasible")

def pct(n, total):
    return round(100 * n / total) if total > 0 else 0

def health_color(rate):
    """Green >=70%, yellow 40-70%, red <40%."""
    if rate >= 70:
        return "#3fb950"
    elif rate >= 40:
        return "#d29922"
    return "#f85149"

def generate_html(tasks, reviews, config, output_path):
    """Generate the full HTML report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build rows
    rows = []
    for strat_id in sorted(tasks.keys()):
        task = tasks[strat_id]
        review = reviews.get(strat_id, {})
        meta = task["meta"]
        rev_meta = review.get("meta", {})
        reviewers = rev_meta.get("reviewers", {})
        source_rfe = meta.get("source_rfe", "")
        cfg = config.get(source_rfe, {})

        rows.append({
            "strat_id": strat_id,
            "title": meta.get("title", ""),
            "source_rfe": source_rfe,
            "priority": meta.get("priority", "—"),
            "status": meta.get("status", "—"),
            "size": cfg.get("size", "—"),
            "baseline": cfg.get("baseline", False),
            "cross_component": cfg.get("cross_component", False),
            "recommendation": rev_meta.get("recommendation", "—"),
            "feasibility": reviewers.get("feasibility", "—"),
            "testability": reviewers.get("testability", "—"),
            "scope": reviewers.get("scope", "—"),
            "architecture": reviewers.get("architecture", "—"),
            "strategy_body": task.get("body", ""),
            "review_body": review.get("body", ""),
        })

    # --- Executive stats ---
    reviewed_rows = [r for r in rows if r["recommendation"] not in ("—", "")]
    total = len(rows)
    total_reviewed = len(reviewed_rows)
    approved = sum(1 for r in reviewed_rows if is_approve(r["recommendation"]))
    revise = sum(1 for r in reviewed_rows if is_revise(r["recommendation"]))
    reject = sum(1 for r in reviewed_rows if is_reject(r["recommendation"]))
    baselines = sum(1 for r in rows if r["baseline"])

    approval_rate = pct(approved, total_reviewed)
    revision_rate = pct(revise, total_reviewed)

    # Per-dimension stats
    dimensions = ["feasibility", "testability", "scope", "architecture"]
    dim_stats = {}
    for dim in dimensions:
        vals = [r[dim] for r in reviewed_rows if r[dim] not in ("—", "")]
        dim_total = len(vals)
        dim_approve = sum(1 for v in vals if is_approve(v))
        dim_revise = sum(1 for v in vals if is_revise(v))
        dim_reject = sum(1 for v in vals if is_reject(v))
        dim_stats[dim] = {
            "total": dim_total,
            "approve": dim_approve,
            "revise": dim_revise,
            "reject": dim_reject,
            "rate": pct(dim_approve, dim_total),
        }

    # Weakest dimension
    weakest_dim = min(dimensions, key=lambda d: dim_stats[d]["rate"])
    weakest_rate = dim_stats[weakest_dim]["rate"]
    strongest_dim = max(dimensions, key=lambda d: dim_stats[d]["rate"])
    strongest_rate = dim_stats[strongest_dim]["rate"]

    # Hero statement
    if approval_rate >= 70:
        hero_text = f"{approved} of {total_reviewed} strategies ready — pipeline is healthy"
    elif approval_rate >= 40:
        hero_text = f"{approved} of {total_reviewed} strategies ready — {revise} need revision"
    else:
        hero_text = f"Only {approved} of {total_reviewed} strategies ready — {weakest_dim} is the bottleneck ({weakest_rate}% pass)"
    hero_color = health_color(approval_rate)

    # --- Build dimension bars HTML ---
    dim_bars_html = ""
    for dim in dimensions:
        ds = dim_stats[dim]
        rate = ds["rate"]
        color = health_color(rate)
        approve_w = pct(ds["approve"], ds["total"]) if ds["total"] else 0
        revise_w = pct(ds["revise"], ds["total"]) if ds["total"] else 0
        reject_w = pct(ds["reject"], ds["total"]) if ds["total"] else 0
        dim_bars_html += f"""
        <div class="dim-row">
            <div class="dim-label">{dim.title()}</div>
            <div class="dim-bar-container">
                <div class="dim-bar-track">
                    <div class="dim-bar-seg" style="width:{approve_w}%;background:#3fb950;" title="{ds['approve']} approved"></div>
                    <div class="dim-bar-seg" style="width:{revise_w}%;background:#d29922;" title="{ds['revise']} revise"></div>
                    <div class="dim-bar-seg" style="width:{reject_w}%;background:#f85149;" title="{ds['reject']} rejected"></div>
                </div>
            </div>
            <div class="dim-rate" style="color:{color}">{rate}%</div>
        </div>"""

    # --- Build verdict grid HTML ---
    grid_html = ""
    for row in rows:
        rec = row["recommendation"]
        rec_cls = verdict_class(rec)
        cells = ""
        for dim in dimensions:
            v = row[dim]
            if is_approve(v):
                bg = "#23302a"
                border = "#3fb950"
            elif is_revise(v):
                bg = "#2d2400"
                border = "#d29922"
            elif is_reject(v):
                bg = "#2d1418"
                border = "#f85149"
            else:
                bg = "#161b22"
                border = "#30363d"
            cells += f'<div class="grid-cell" style="background:{bg};border-color:{border}" title="{dim.title()}: {v}"></div>'
        strat_short = row["strat_id"].replace("STRAT-", "")
        grid_html += f"""
        <div class="grid-row">
            <div class="grid-id">STRAT-{escape_html(strat_short)}</div>
            {cells}
            <div class="grid-verdict {rec_cls}">{verdict_label(rec)}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Strategy Pipeline Report</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 24px; }}
.header {{ margin-bottom: 32px; }}
.header h1 {{ font-size: 28px; color: #f0f6fc; margin-bottom: 8px; }}
.header .subtitle {{ color: #8b949e; font-size: 14px; }}

/* Hero section */
.hero {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 32px; margin-bottom: 24px; text-align: center; }}
.hero-statement {{ font-size: 28px; font-weight: 700; margin-bottom: 8px; }}
.hero-sub {{ color: #8b949e; font-size: 14px; }}

/* KPI cards */
.kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }}
.kpi {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px 24px; text-align: center; }}
.kpi .kpi-value {{ font-size: 36px; font-weight: 700; line-height: 1.1; }}
.kpi .kpi-label {{ font-size: 12px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 6px; }}
.kpi .kpi-detail {{ font-size: 12px; color: #6e7681; margin-top: 4px; }}

/* Dimension breakdown */
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
.grid-legend {{ display: flex; gap: 16px; margin-bottom: 16px; font-size: 12px; color: #8b949e; }}
.grid-legend-item {{ display: flex; align-items: center; gap: 4px; }}
.grid-legend-swatch {{ width: 12px; height: 12px; border-radius: 3px; border: 2px solid; }}
.grid-header {{ display: flex; align-items: center; gap: 4px; padding: 0 0 8px; border-bottom: 1px solid #21262d; margin-bottom: 8px; }}
.grid-header-id {{ width: 90px; font-size: 11px; color: #6e7681; text-transform: uppercase; }}
.grid-header-dim {{ width: 40px; text-align: center; font-size: 10px; color: #6e7681; text-transform: uppercase; }}
.grid-header-verdict {{ width: 72px; text-align: right; font-size: 11px; color: #6e7681; text-transform: uppercase; }}
.grid-row {{ display: flex; align-items: center; gap: 4px; padding: 4px 0; }}
.grid-id {{ width: 90px; font-size: 13px; color: #c9d1d9; font-weight: 500; }}
.grid-cell {{ width: 40px; height: 24px; border-radius: 4px; border: 2px solid; }}
.grid-verdict {{ width: 72px; text-align: right; font-size: 12px; font-weight: 600; }}

/* Summary panels */
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }}
@media (max-width: 900px) {{
    .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .two-col {{ grid-template-columns: 1fr; }}
}}

/* Legacy styles (table, details, etc.) */
table {{ width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; margin-bottom: 24px; }}
thead {{ background: #21262d; }}
th {{ text-align: left; padding: 12px 16px; font-size: 12px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; border-bottom: 1px solid #30363d; }}
td {{ padding: 12px 16px; border-bottom: 1px solid #21262d; font-size: 14px; }}
tr:hover {{ background: #1c2128; }}
tr.clickable {{ cursor: pointer; }}
.verdict-approve {{ color: #3fb950; font-weight: 600; }}
.verdict-revise {{ color: #d29922; font-weight: 600; }}
.verdict-reject {{ color: #f85149; font-weight: 600; }}
.verdict-unknown {{ color: #8b949e; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
.badge-baseline {{ background: #1f3a5f; color: #58a6ff; }}
.badge-cross {{ background: #3d2e00; color: #d29922; }}
.badge-size {{ background: #21262d; color: #8b949e; border: 1px solid #30363d; }}
.detail-panel {{ display: none; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; margin: 8px 16px 16px; padding: 24px; }}
.detail-panel.open {{ display: block; }}
.detail-panel h2 {{ color: #f0f6fc; font-size: 20px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #21262d; }}
.detail-panel h3 {{ color: #c9d1d9; font-size: 16px; margin: 16px 0 8px; }}
.detail-panel h4 {{ color: #8b949e; font-size: 14px; margin: 12px 0 6px; }}
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
.footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #21262d; color: #484f58; font-size: 12px; }}
.nav-tabs {{ display: flex; gap: 0; margin-bottom: 24px; border-bottom: 2px solid #21262d; }}
.nav-tab {{ padding: 12px 24px; cursor: pointer; color: #8b949e; font-size: 15px; font-weight: 600; border-bottom: 2px solid transparent; margin-bottom: -2px; transition: all 0.2s; }}
.nav-tab:hover {{ color: #c9d1d9; background: #161b22; }}
.nav-tab.active {{ color: #f0f6fc; border-bottom-color: #f78166; }}
.nav-page {{ display: none; }}
.nav-page.active {{ display: block; }}
.pipeline {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 24px; position: relative; height: calc(100vh - 180px); display: flex; flex-direction: column; }}
.pipeline h2 {{ color: #f0f6fc; font-size: 16px; margin-bottom: 16px; flex-shrink: 0; }}
.pipeline .mermaid {{ cursor: grab; }}
.pipeline .mermaid:active {{ cursor: grabbing; }}
.zoom-controls {{ position: absolute; top: 16px; right: 16px; display: flex; gap: 4px; z-index: 10; }}
.zoom-btn {{ background: #21262d; border: 1px solid #30363d; color: #c9d1d9; width: 32px; height: 32px; border-radius: 6px; cursor: pointer; font-size: 16px; display: flex; align-items: center; justify-content: center; }}
.zoom-btn:hover {{ background: #30363d; color: #f0f6fc; }}
.diagram-container {{ overflow: hidden; position: relative; flex: 1; }}
.diagram-inner {{ transform-origin: 0 0; transition: transform 0.1s ease; height: 100%; display: flex; align-items: center; justify-content: center; }}
</style>
</head>
<body>

<div class="header">
    <h1>Strategy Pipeline Report</h1>
    <div class="subtitle">Generated {timestamp} | {total} strategies processed</div>
</div>

<div class="nav-tabs">
    <div class="nav-tab active" onclick="switchPage('summary')">Summary</div>
    <div class="nav-tab" onclick="switchPage('details')">Details</div>
    <div class="nav-tab" onclick="switchPage('pipeline')">Pipeline</div>
</div>

<div class="nav-page active" id="page-summary">

<!-- Hero statement -->
<div class="hero">
    <div class="hero-statement" style="color:{hero_color}">{escape_html(hero_text)}</div>
    <div class="hero-sub">Strategy readiness across {total_reviewed} reviewed strategies | Generated {timestamp}</div>
</div>

<!-- KPI cards -->
<div class="kpi-grid">
    <div class="kpi">
        <div class="kpi-value" style="color:#f0f6fc">{total_reviewed}</div>
        <div class="kpi-label">Strategies Reviewed</div>
        <div class="kpi-detail">{total} total processed</div>
    </div>
    <div class="kpi">
        <div class="kpi-value" style="color:{health_color(approval_rate)}">{approval_rate}%</div>
        <div class="kpi-label">Approval Rate</div>
        <div class="kpi-detail">{approved} of {total_reviewed} approved</div>
    </div>
    <div class="kpi">
        <div class="kpi-value" style="color:{health_color(100 - revision_rate)}">{revision_rate}%</div>
        <div class="kpi-label">Revision Rate</div>
        <div class="kpi-detail">{revise} need rework</div>
    </div>
    <div class="kpi">
        <div class="kpi-value" style="color:{health_color(weakest_rate)}">{weakest_rate}%</div>
        <div class="kpi-label">Weakest: {weakest_dim.title()}</div>
        <div class="kpi-detail">Strongest: {strongest_dim.title()} ({strongest_rate}%)</div>
    </div>
</div>

<!-- Two-column: Dimension breakdown + Verdict grid -->
<div class="two-col">
    <div class="dim-section">
        <h3>Review Dimensions</h3>
        {dim_bars_html}
        <div style="display:flex;gap:16px;margin-top:12px;font-size:11px;color:#6e7681">
            <span><span style="display:inline-block;width:10px;height:10px;background:#3fb950;border-radius:2px;margin-right:4px"></span>Approve</span>
            <span><span style="display:inline-block;width:10px;height:10px;background:#d29922;border-radius:2px;margin-right:4px"></span>Revise</span>
            <span><span style="display:inline-block;width:10px;height:10px;background:#f85149;border-radius:2px;margin-right:4px"></span>Reject</span>
        </div>
    </div>
    <div class="grid-section">
        <h3>Per-Strategy Verdicts</h3>
        <div class="grid-header">
            <div class="grid-header-id">Strategy</div>
            <div class="grid-header-dim">Feas</div>
            <div class="grid-header-dim">Test</div>
            <div class="grid-header-dim">Scope</div>
            <div class="grid-header-dim">Arch</div>
            <div class="grid-header-verdict">Result</div>
        </div>
        {grid_html}
    </div>
</div>

<!-- Full summary table -->
<table>
<thead>
<tr>
    <th>Strat ID</th>
    <th>Title</th>
    <th>Source RFE</th>
    <th>Size</th>
    <th>Feasibility</th>
    <th>Testability</th>
    <th>Scope</th>
    <th>Architecture</th>
    <th>Recommendation</th>
</tr>
</thead>
<tbody>
"""

    for i, row in enumerate(rows):
        badges = ""
        if row["baseline"]:
            badges += ' <span class="badge badge-baseline">baseline</span>'
        if row["cross_component"]:
            badges += ' <span class="badge badge-cross">cross-component</span>'

        html += f"""<tr>
    <td><strong>{escape_html(row["strat_id"])}</strong></td>
    <td>{escape_html(row["title"])}{badges}</td>
    <td>{escape_html(row["source_rfe"])}</td>
    <td><span class="badge badge-size">{escape_html(str(row["size"]))}</span></td>
    <td class="{verdict_class(row["feasibility"])}">{verdict_label(row["feasibility"])}</td>
    <td class="{verdict_class(row["testability"])}">{verdict_label(row["testability"])}</td>
    <td class="{verdict_class(row["scope"])}">{verdict_label(row["scope"])}</td>
    <td class="{verdict_class(row["architecture"])}">{verdict_label(row["architecture"])}</td>
    <td class="{verdict_class(row["recommendation"])}">{verdict_label(row["recommendation"])}</td>
</tr>
"""

    html += f"""</tbody>
</table>
</div><!-- end page-summary -->

<div class="nav-page" id="page-pipeline">
<div class="pipeline">
    <h2>RHAI Agentic SDLC Pipeline</h2>
    <div class="zoom-controls">
        <button class="zoom-btn" onclick="zoomDiagram(1.2)" title="Zoom in">+</button>
        <button class="zoom-btn" onclick="zoomDiagram(0.8)" title="Zoom out">&minus;</button>
        <button class="zoom-btn" onclick="resetDiagram()" title="Reset">&#8634;</button>
    </div>
    <div class="diagram-container" id="diagram-container">
    <div class="diagram-inner" id="diagram-inner">
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
</div><!-- end page-pipeline -->

<div class="nav-page" id="page-details">

<table>
<thead>
<tr>
    <th></th>
    <th>Strat ID</th>
    <th>Title</th>
    <th>Recommendation</th>
</tr>
</thead>
<tbody>
"""

    for i, row in enumerate(rows):
        badges = ""
        if row["baseline"]:
            badges += ' <span class="badge badge-baseline">baseline</span>'
        if row["cross_component"]:
            badges += ' <span class="badge badge-cross">cross-component</span>'

        html += f"""<tr class="clickable" onclick="toggleDetail({i})">
    <td><span class="expand-icon" id="icon-{i}">&#9654;</span></td>
    <td><strong>{escape_html(row["strat_id"])}</strong></td>
    <td>{escape_html(row["title"])}{badges}</td>
    <td class="{verdict_class(row["recommendation"])}">{verdict_label(row["recommendation"])}</td>
</tr>
<tr><td colspan="4" style="padding:0">
    <div class="detail-panel" id="detail-{i}">
        <h2>{escape_html(row["strat_id"])}: {escape_html(row["title"])}</h2>
        <div class="detail-tabs">
            <div class="detail-tab active" onclick="switchTab({i}, 'review')">Review</div>
            <div class="detail-tab" onclick="switchTab({i}, 'strategy')">Strategy</div>
        </div>
        <div class="tab-content active" id="tab-{i}-review">
            {md_to_html(row["review_body"])}
        </div>
        <div class="tab-content" id="tab-{i}-strategy">
            {md_to_html(row["strategy_body"])}
        </div>
    </div>
</td></tr>
"""

    html += f"""</tbody>
</table>
</div><!-- end page-details -->

<div class="footer">
    strat-creator pipeline | RHAI Agentic SDLC
</div>

<script>
let mermaidRendered = false;
function switchPage(page) {{
    document.querySelectorAll('.nav-page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.getElementById('page-' + page).classList.add('active');
    event.target.classList.add('active');
    if (page === 'pipeline' && !mermaidRendered) {{
        mermaidRendered = true;
        renderMermaid();
    }}
}}

function toggleDetail(i) {{
    const panel = document.getElementById('detail-' + i);
    const icon = document.getElementById('icon-' + i);
    panel.classList.toggle('open');
    icon.classList.toggle('open');
}}

function switchTab(i, tab) {{
    const tabs = document.querySelectorAll('#detail-' + i + ' .detail-tab');
    const contents = document.querySelectorAll('#detail-' + i + ' .tab-content');
    tabs.forEach(t => t.classList.remove('active'));
    contents.forEach(c => c.classList.remove('active'));
    document.getElementById('tab-' + i + '-' + tab).classList.add('active');
    event.target.classList.add('active');
}}
</script>

<script>
let diagramScale = 1;
let diagramX = 0, diagramY = 0;
let isDragging = false, startX, startY;

function zoomDiagram(factor) {{
    diagramScale *= factor;
    diagramScale = Math.max(0.3, Math.min(3, diagramScale));
    updateDiagramTransform();
}}

function resetDiagram() {{
    diagramScale = 1;
    diagramX = 0;
    diagramY = 0;
    updateDiagramTransform();
}}

function updateDiagramTransform() {{
    const inner = document.getElementById('diagram-inner');
    inner.style.transform = `translate(${{diagramX}}px, ${{diagramY}}px) scale(${{diagramScale}})`;
}}

const container = document.getElementById('diagram-container');
container.addEventListener('wheel', (e) => {{
    e.preventDefault();
    zoomDiagram(e.deltaY < 0 ? 1.1 : 0.9);
}}, {{ passive: false }});

container.addEventListener('mousedown', (e) => {{
    isDragging = true;
    startX = e.clientX - diagramX;
    startY = e.clientY - diagramY;
}});

document.addEventListener('mousemove', (e) => {{
    if (!isDragging) return;
    diagramX = e.clientX - startX;
    diagramY = e.clientY - startY;
    const inner = document.getElementById('diagram-inner');
    inner.style.transition = 'none';
    updateDiagramTransform();
    inner.style.transition = 'transform 0.1s ease';
}});

document.addEventListener('mouseup', () => {{ isDragging = false; }});
</script>

<script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{
        startOnLoad: false,
        theme: 'dark',
        flowchart: {{
            useMaxWidth: false,
            htmlLabels: true,
            curve: 'basis'
        }}
    }});

    // Deferred render — Mermaid can't measure inside display:none
    window.renderMermaid = async function() {{
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
</script>

</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"Report generated: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate strategy pipeline HTML report")
    parser.add_argument("--output", "-o", default=None,
                        help="Output HTML file path (default: artifacts/reports/<timestamp>/report.html)")
    parser.add_argument("--config", "-c", default="config/test-rfes.yaml",
                        help="Test RFEs config file (default: config/test-rfes.yaml)")
    parser.add_argument("--artifacts", "-a", default="artifacts",
                        help="Artifacts directory (default: artifacts)")
    args = parser.parse_args()

    # Default output: timestamped folder
    if args.output is None:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        report_dir = os.path.join(args.artifacts, "reports", ts)
        os.makedirs(report_dir, exist_ok=True)
        output_path = os.path.join(report_dir, "report.html")
    else:
        output_path = args.output
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Load config
    config = {}
    if os.path.exists(args.config):
        try:
            config = load_yaml_config(args.config)
        except Exception as e:
            print(f"Warning: failed to read config: {e}", file=sys.stderr)

    # Load artifacts
    tasks, reviews = load_artifacts(args.artifacts)

    if not tasks:
        print("Error: no strategy artifacts found in", args.artifacts, file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(tasks)} strategies, {len(reviews)} reviews")
    generate_html(tasks, reviews, config, output_path)

if __name__ == "__main__":
    main()

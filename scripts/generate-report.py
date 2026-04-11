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

    # Stats
    total = len(rows)
    approved = sum(1 for r in rows if r["recommendation"] in ("approve", "approved"))
    revise = sum(1 for r in rows if r["recommendation"] in ("revise", "needs revision"))
    reject = sum(1 for r in rows if r["recommendation"] in ("reject", "rejected"))
    baselines = sum(1 for r in rows if r["baseline"])

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
.stats {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
.stat {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px 24px; min-width: 120px; }}
.stat .number {{ font-size: 32px; font-weight: 700; color: #f0f6fc; }}
.stat .label {{ font-size: 12px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }}
.stat.approve .number {{ color: #3fb950; }}
.stat.revise .number {{ color: #d29922; }}
.stat.reject .number {{ color: #f85149; }}
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
.pipeline {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 24px; margin-bottom: 24px; }}
.pipeline h2 {{ color: #f0f6fc; font-size: 16px; margin-bottom: 16px; }}
.pipeline-flow {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }}
.pipeline-step {{ padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 600; white-space: nowrap; }}
.pipeline-arrow {{ color: #484f58; font-size: 18px; }}
.step-done {{ background: #1a3a1a; color: #3fb950; border: 1px solid #2d6a2d; }}
.step-current {{ background: #3d2e00; color: #d29922; border: 1px solid #c77d1a; }}
.step-pending {{ background: #21262d; color: #484f58; border: 1px solid #30363d; }}
.pipeline-legend {{ display: flex; gap: 16px; margin-top: 8px; }}
.pipeline-legend span {{ font-size: 11px; color: #8b949e; }}
.pipeline-legend .dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }}
.dot-done {{ background: #3fb950; }}
.dot-current {{ background: #d29922; }}
.dot-pending {{ background: #484f58; }}
</style>
</head>
<body>

<div class="header">
    <h1>Strategy Pipeline Report</h1>
    <div class="subtitle">Generated {timestamp} | {total} RFEs processed | Dry run mode</div>
</div>

<div class="pipeline">
    <h2>RHAI Agentic SDLC Pipeline</h2>
    <div class="pipeline-flow">
        <span class="pipeline-step step-done">rfe.create</span>
        <span class="pipeline-arrow">&rarr;</span>
        <span class="pipeline-step step-done">rfe.review</span>
        <span class="pipeline-arrow">&rarr;</span>
        <span class="pipeline-step step-done">rfe.auto-fix</span>
        <span class="pipeline-arrow">&rarr;</span>
        <span class="pipeline-step step-done">rfe.submit</span>
        <span class="pipeline-arrow">&rArr;</span>
        <span class="pipeline-step step-current">strategy.create</span>
        <span class="pipeline-arrow">&rarr;</span>
        <span class="pipeline-step step-current">strategy.refine</span>
        <span class="pipeline-arrow">&rarr;</span>
        <span class="pipeline-step step-current">strategy.review</span>
        <span class="pipeline-arrow">&rarr;</span>
        <span class="pipeline-step step-pending">strategy.revise</span>
        <span class="pipeline-arrow">&rarr;</span>
        <span class="pipeline-step step-pending">strategy.submit</span>
        <span class="pipeline-arrow">&rArr;</span>
        <span class="pipeline-step step-pending">Feature Dev</span>
    </div>
    <div class="pipeline-legend">
        <span><span class="dot dot-done"></span> Phase 1: RFE Assessment (rfe-creator)</span>
        <span><span class="dot dot-current"></span> Phase 2: Strategy Refinement (strat-creator)</span>
        <span><span class="dot dot-pending"></span> Not started</span>
    </div>
</div>

<div class="stats">
    <div class="stat">
        <div class="number">{total}</div>
        <div class="label">Total</div>
    </div>
    <div class="stat approve">
        <div class="number">{approved}</div>
        <div class="label">Approved</div>
    </div>
    <div class="stat revise">
        <div class="number">{revise}</div>
        <div class="label">Needs Revision</div>
    </div>
    <div class="stat reject">
        <div class="number">{reject}</div>
        <div class="label">Rejected</div>
    </div>
    <div class="stat">
        <div class="number">{baselines}</div>
        <div class="label">Baselines</div>
    </div>
</div>

<table>
<thead>
<tr>
    <th></th>
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

        html += f"""<tr class="clickable" onclick="toggleDetail({i})">
    <td><span class="expand-icon" id="icon-{i}">&#9654;</span></td>
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
<tr><td colspan="10" style="padding:0">
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

<div class="footer">
    strat-creator pipeline | RHAI Agentic SDLC
</div>

<script>
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

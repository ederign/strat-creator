#!/usr/bin/env python3
"""Pull a RHAISTRAT issue from Jira into the local/ workspace for human review.

Fetches the strategy description, linked RFE context, and review comments.
Only works on post-CI strategies (must have strat-creator-rubric-pass or
strat-creator-needs-attention label).

Usage:
    python3 scripts/pull_strategy.py RHAISTRAT-1520
    python3 scripts/pull_strategy.py RHAISTRAT-1520 --local-dir local

Exit codes:
    0 — success
    1 — issue not found, missing post-CI labels, or API error
    2 — missing JIRA credentials
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from jira_utils import (
    require_env,
    get_issue,
    get_comments,
    adf_to_markdown,
    download_attachment,
)

POST_CI_LABELS = {"strat-creator-rubric-pass", "strat-creator-needs-attention"}

STRAT_CREATOR_COMMENT_MARKER = "[Strat Creator]"


def find_linked_rfe(server, user, token, strat_key):
    """Find the RHAIRFE source linked via Cloners to this RHAISTRAT."""
    data = get_issue(server, user, token, strat_key, fields=["issuelinks"])
    links = data.get("fields", {}).get("issuelinks", [])

    for link in links:
        if link.get("type", {}).get("name") != "Cloners":
            continue
        for direction in ("outwardIssue", "inwardIssue"):
            issue = link.get(direction, {})
            key = issue.get("key", "")
            if key.startswith("RHAIRFE-"):
                return key
    return None


def extract_review_comment(comments):
    """Find the most recent review comment posted by strat-creator.

    Looks for comments containing the [Strat Creator] marker.
    Returns the markdown body of the most recent match, or None.
    """
    matches = []
    for comment in comments:
        body_adf = comment.get("body")
        if not body_adf:
            continue
        body_md = adf_to_markdown(body_adf).strip()
        if STRAT_CREATOR_COMMENT_MARKER in body_md:
            matches.append(body_md)
    return matches[-1] if matches else None


def pull_strategy(server, user, token, strat_key, local_dir="local"):
    """Pull a RHAISTRAT issue and its context into the local workspace.

    Returns a dict summarizing what was pulled, or raises SystemExit on error.
    """
    # Fetch the STRAT issue
    issue = get_issue(server, user, token, strat_key,
                      fields=["summary", "description", "labels",
                              "priority", "issuelinks", "attachment"])
    fields = issue.get("fields", {})

    # Validate post-CI labels
    labels = set(fields.get("labels", []))
    if not labels & POST_CI_LABELS:
        print(f"Error: {strat_key} does not have a post-CI label "
              f"({', '.join(sorted(POST_CI_LABELS))}). "
              f"Current labels: {', '.join(sorted(labels)) or '(none)'}",
              file=sys.stderr)
        sys.exit(1)

    summary = fields.get("summary", "Untitled")
    priority_field = fields.get("priority")
    priority = priority_field.get("name", "Major") if priority_field else "Major"
    description_adf = fields.get("description")
    description_md = adf_to_markdown(description_adf).strip() if description_adf else ""

    # Find linked RFE via Cloners
    rfe_key = None
    strat_links = fields.get("issuelinks", [])
    for link in strat_links:
        if link.get("type", {}).get("name") != "Cloners":
            continue
        for direction in ("outwardIssue", "inwardIssue"):
            issue_ref = link.get(direction, {})
            key = issue_ref.get("key", "")
            if key.startswith("RHAIRFE-"):
                rfe_key = key
                break
        if rfe_key:
            break

    result = {"strat_key": strat_key, "files": []}

    # Write strategy file
    tasks_dir = os.path.join(local_dir, "strat-tasks")
    os.makedirs(tasks_dir, exist_ok=True)
    strat_path = os.path.join(tasks_dir, f"{strat_key}.md")

    from artifact_utils import write_frontmatter
    frontmatter = {
        "strat_id": strat_key,
        "title": summary,
        "source_rfe": rfe_key or "RHAIRFE-0",
        "jira_key": strat_key,
        "priority": priority,
        "status": "Refined",
        "workflow": "local",
    }
    write_frontmatter(strat_path, frontmatter, "strat-task")

    # Append body content
    with open(strat_path, "a", encoding="utf-8") as f:
        f.write(f"\n{description_md}\n")
    result["files"].append(strat_path)
    print(f"  Strategy: {strat_path}")

    # Fetch and write RFE original
    if rfe_key:
        originals_dir = os.path.join(local_dir, "strat-originals")
        os.makedirs(originals_dir, exist_ok=True)

        rfe_data = get_issue(server, user, token, rfe_key,
                             fields=["description"])
        rfe_desc_adf = rfe_data.get("fields", {}).get("description")
        rfe_md = adf_to_markdown(rfe_desc_adf).strip() if rfe_desc_adf else ""

        rfe_path = os.path.join(originals_dir, f"{rfe_key}.md")
        with open(rfe_path, "w", encoding="utf-8") as f:
            f.write(rfe_md + "\n")
        result["files"].append(rfe_path)
        result["rfe_key"] = rfe_key
        print(f"  RFE original: {rfe_path}")

        # Fetch RFE comments
        rfe_comments = get_comments(server, user, token, rfe_key)
        if rfe_comments:
            comments_path = os.path.join(originals_dir, f"{rfe_key}-comments.md")
            with open(comments_path, "w", encoding="utf-8") as f:
                f.write(f"# Comments: {rfe_key}\n\n")
                for comment in rfe_comments:
                    author = (comment.get("author", {}).get("displayName")
                              or "Unknown")
                    created = comment.get("created", "")[:10]
                    body_adf = comment.get("body")
                    body_md = adf_to_markdown(body_adf).strip() if body_adf else ""
                    f.write(f"## {author} — {created}\n\n{body_md}\n\n")
            result["files"].append(comments_path)
            print(f"  RFE comments: {comments_path}")

    # Fetch review summary from comments
    reviews_dir = os.path.join(local_dir, "strat-reviews")
    strat_comments = get_comments(server, user, token, strat_key)
    review_md = extract_review_comment(strat_comments)
    if review_md:
        os.makedirs(reviews_dir, exist_ok=True)
        summary_path = os.path.join(reviews_dir, f"{strat_key}-review-summary.md")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(review_md + "\n")
        result["files"].append(summary_path)
        print(f"  Review summary: {summary_path}")

    # Fetch full review from attachment
    attachments = fields.get("attachment", [])
    review_attachment = None
    for att in attachments:
        if att.get("filename") == f"{strat_key}-review.md":
            review_attachment = att
    if review_attachment:
        os.makedirs(reviews_dir, exist_ok=True)
        full_path = os.path.join(reviews_dir, f"{strat_key}-review.md")
        download_attachment(server, user, token,
                            review_attachment["content"], full_path)
        result["files"].append(full_path)
        print(f"  Full review: {full_path}")

    has_rubric_pass = "strat-creator-rubric-pass" in labels
    result["has_rubric_pass"] = has_rubric_pass
    result["has_needs_attention"] = "strat-creator-needs-attention" in labels

    return result


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("strat_key", help="RHAISTRAT issue key")
    parser.add_argument("--local-dir", default="local",
                        help="Local workspace directory (default: local)")
    args = parser.parse_args()

    if not args.strat_key.startswith("RHAISTRAT-"):
        print(f"Error: expected RHAISTRAT-NNNN key, got '{args.strat_key}'",
              file=sys.stderr)
        sys.exit(1)

    server, user, token = require_env()
    if not all([server, user, token]):
        print("Error: JIRA_SERVER, JIRA_USER, and JIRA_TOKEN required.",
              file=sys.stderr)
        sys.exit(2)

    print(f"Pulling {args.strat_key} into {args.local_dir}/...")
    result = pull_strategy(server, user, token, args.strat_key, args.local_dir)

    print(f"\nPulled {len(result['files'])} files.")
    if result.get("has_rubric_pass"):
        print("Status: CI-approved (rubric-pass). Use /strategy-signoff when ready.")
    elif result.get("has_needs_attention"):
        print("Status: Needs attention. Use /strategy-push to resubmit after fixing.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fetch a Jira issue and print its fields as JSON.

Lightweight read utility for skills that need to fetch issues when the
Atlassian MCP server is unavailable. Outputs JSON to stdout for the
calling skill to parse.

Usage:
    python3 scripts/fetch_issue.py RHAIRFE-1234 [--fields summary,description,comment,priority,labels,status] [--markdown]

    # Fetch everything and write all artifact files at once
    python3 scripts/fetch_issue.py RHAIRFE-1234 --fetch-all artifacts

Environment variables:
    JIRA_SERVER  Jira server URL (e.g. https://mysite.atlassian.net)
    JIRA_USER    Jira username/email
    JIRA_TOKEN   Jira API token

Exit codes:
    0  Success
    1  API/network/script error
    2  Missing JIRA credentials (caller should try MCP fallback)
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

from jira_utils import require_env, get_issue, get_comments, adf_to_markdown


MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB

TEXT_EXTENSIONS = {
    ".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".xml",
    ".html", ".htm", ".rst", ".adoc", ".log", ".conf", ".cfg",
    ".ini", ".toml", ".properties", ".sh", ".bash", ".py",
    ".java", ".go", ".js", ".ts",
}

TEXT_MIME_PREFIXES = ("text/", "application/json", "application/xml",
                      "application/yaml", "application/x-yaml")


def _desc_to_markdown(desc_raw):
    """Convert a raw description field (ADF dict or string) to markdown."""
    if isinstance(desc_raw, dict):
        return adf_to_markdown(desc_raw).strip()
    elif desc_raw is not None:
        return str(desc_raw).strip()
    return ""


def _format_comment_date(iso_date):
    """Format an ISO timestamp to a human-readable date string."""
    # Jira dates look like "2025-01-15T10:30:00.000+0000"
    if not iso_date:
        return "Unknown date"
    return iso_date[:10]


def _sanitize_filename(name):
    """Remove path traversal characters and unsafe chars from a filename."""
    name = os.path.basename(name)
    name = re.sub(r'[^\w.\-() ]', '_', name)
    return name or "unnamed"


def _is_text_attachment(attachment):
    """Check if an attachment is text-based and within size limits."""
    size = attachment.get("size", 0)
    if size > MAX_ATTACHMENT_BYTES:
        return False
    filename = attachment.get("filename", "")
    mime = attachment.get("mimeType", "")
    _, ext = os.path.splitext(filename.lower())
    if ext in TEXT_EXTENSIONS:
        return True
    if any(mime.startswith(p) for p in TEXT_MIME_PREFIXES):
        return True
    return False


def _download_attachment(url, dest_path, user, token):
    """Download a Jira attachment file using basic auth."""
    credentials = base64.b64encode(f"{user}:{token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        with open(dest_path, "wb") as f:
            f.write(resp.read())


def _fetch_attachments(attachments, issue_key, artifacts_dir, user, token):
    """Download text-based attachments to artifacts/attachments/{key}/."""
    if not attachments:
        return
    att_dir = os.path.join(artifacts_dir, "attachments", issue_key)
    os.makedirs(att_dir, exist_ok=True)
    count = 0
    for att in attachments:
        if not _is_text_attachment(att):
            filename = att.get("filename", "?")
            size_kb = att.get("size", 0) // 1024
            print(f"  Skipping attachment {filename} "
                  f"(type={att.get('mimeType')}, {size_kb}KB)",
                  file=sys.stderr)
            continue
        filename = _sanitize_filename(att.get("filename", "unnamed"))
        dest = os.path.join(att_dir, filename)
        content_url = att.get("content", "")
        if not content_url:
            continue
        try:
            _download_attachment(content_url, dest, user, token)
            count += 1
            print(f"  Downloaded attachment: {filename}", file=sys.stderr)
        except Exception as e:
            print(f"  Error downloading {filename}: {e}", file=sys.stderr)
    if count == 0:
        os.rmdir(att_dir)
    else:
        print(f"  {count} attachment(s) saved to {att_dir}", file=sys.stderr)


def _fetch_linked_issues(issuelinks, issue_key, artifacts_dir,
                         server, user, token):
    """Fetch summary + description from linked issues (one level deep)."""
    if not issuelinks:
        return
    tasks_dir = os.path.join(artifacts_dir, "rfe-tasks")
    os.makedirs(tasks_dir, exist_ok=True)
    links_path = os.path.join(tasks_dir, f"{issue_key}-links.md")

    sections = []
    for link in issuelinks:
        link_type = link.get("type", {}).get("name", "Related")
        inward = link.get("inwardIssue")
        outward = link.get("outwardIssue")
        linked = inward or outward
        if not linked:
            continue
        linked_key = linked.get("key", "")
        direction = "inward" if inward else "outward"
        relation = link.get("type", {}).get(direction, link_type)

        try:
            linked_issue = get_issue(server, user, token, linked_key,
                                     fields=["summary", "description"])
            fields = linked_issue.get("fields", {})
            summary = fields.get("summary", "")
            desc_md = _desc_to_markdown(fields.get("description"))
            sections.append(
                f"## {linked_key}: {summary}\n\n"
                f"**Relationship**: {relation}\n\n"
                f"{desc_md}\n"
            )
            print(f"  Fetched linked issue: {linked_key} ({relation})",
                  file=sys.stderr)
        except Exception as e:
            sections.append(
                f"## {linked_key}\n\n"
                f"**Relationship**: {relation}\n\n"
                f"Error fetching: {e}\n"
            )
            print(f"  Error fetching linked {linked_key}: {e}",
                  file=sys.stderr)

    if sections:
        with open(links_path, "w", encoding="utf-8") as f:
            f.write(f"# Linked Issues: {issue_key}\n\n")
            f.write("\n".join(sections))
        print(f"  {len(sections)} linked issue(s) saved to {links_path}",
              file=sys.stderr)


def _fetch_all(issue_key, artifacts_dir, server, user, token):
    """Fetch issue and write all artifact files.

    Returns 0 on success, 1 on error.
    """
    tasks_dir = os.path.join(artifacts_dir, "rfe-tasks")
    originals_dir = os.path.join(artifacts_dir, "rfe-originals")
    os.makedirs(tasks_dir, exist_ok=True)
    os.makedirs(originals_dir, exist_ok=True)

    # Fetch issue fields (including attachments and links for context)
    try:
        issue = get_issue(server, user, token, issue_key,
                          fields=["summary", "description", "priority",
                                  "labels", "status", "attachment",
                                  "issuelinks"])
    except Exception as e:
        print(f"Error fetching issue {issue_key}: {e}", file=sys.stderr)
        return 1

    fields = issue.get("fields", {})
    desc_md = _desc_to_markdown(fields.get("description"))

    # Extract field values
    summary = fields.get("summary", "")
    priority_obj = fields.get("priority")
    priority = priority_obj.get("name", "Major") if isinstance(
        priority_obj, dict) else "Major"
    labels = fields.get("labels", [])
    labels_str = ",".join(labels) if labels else "null"

    # Write task file (description body)
    task_path = os.path.join(tasks_dir, f"{issue_key}.md")
    with open(task_path, "w", encoding="utf-8") as f:
        f.write(desc_md + "\n")

    # Set frontmatter via frontmatter.py
    fm_args = [
        sys.executable, "scripts/frontmatter.py", "set", task_path,
        f"rfe_id={issue_key}",
        f"title={summary}",
        f"priority={priority}",
        "status=Ready",
        f"original_labels={labels_str}",
    ]
    result = subprocess.run(fm_args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error setting frontmatter: {result.stderr.strip()}",
              file=sys.stderr)
        return 1

    # Write original description (deterministic baseline for conflict
    # detection)
    orig_path = os.path.join(originals_dir, f"{issue_key}.md")
    with open(orig_path, "w", encoding="utf-8") as f:
        f.write(desc_md + "\n")

    # Fetch and write comments
    try:
        comments = get_comments(server, user, token, issue_key)
    except Exception as e:
        print(f"Error fetching comments for {issue_key}: {e}",
              file=sys.stderr)
        return 1

    comments_path = os.path.join(tasks_dir, f"{issue_key}-comments.md")
    with open(comments_path, "w", encoding="utf-8") as f:
        f.write(f"# Comments: {issue_key}\n\n")
        if not comments:
            f.write("No comments found.\n")
        else:
            for c in comments:
                author = c.get("author", {}).get("displayName", "Unknown")
                date = _format_comment_date(c.get("created", ""))
                body = c.get("body", {})
                if isinstance(body, dict):
                    body = adf_to_markdown(body).strip()
                elif body is not None:
                    body = str(body).strip()
                else:
                    body = ""
                f.write(f"## {author} — {date}\n\n{body}\n\n")

    # Fetch and save text-based attachments
    attachments = fields.get("attachment", [])
    _fetch_attachments(attachments, issue_key, artifacts_dir, user, token)

    # Fetch linked issue summaries + descriptions (one level deep)
    issuelinks = fields.get("issuelinks", [])
    _fetch_linked_issues(issuelinks, issue_key, artifacts_dir,
                         server, user, token)

    print(f"OK: wrote {task_path}, {orig_path}, {comments_path}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("issue_key",
                        help="Jira issue key (e.g. RHAIRFE-1234)")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--fields", default=None,
                            help="Comma-separated list of fields to fetch "
                                 "(default: summary,description,priority,"
                                 "labels,status). "
                                 "Use 'comment' to also fetch comments.")
    mode_group.add_argument("--fetch-all", metavar="ARTIFACTS_DIR",
                            help="Fetch issue and write all artifact files "
                                 "(rfe-tasks, rfe-originals, comments) to "
                                 "the given directory.")

    parser.add_argument("--markdown", action="store_true",
                        help="Convert ADF fields (description, comments) "
                             "to markdown strings in the output")
    parser.add_argument("--write-original", metavar="DIR",
                        help="Write the description as markdown to "
                             "DIR/<issue_key>.md. If JIRA creds are "
                             "available, refetches via REST API and uses "
                             "adf_to_markdown for deterministic output. "
                             "If not, copies DIR/<issue_key>.input.md "
                             "as a fallback.")
    args = parser.parse_args()

    server, user, token = require_env()

    # --fetch-all mode: script does everything
    if args.fetch_all:
        if not all([server, user, token]):
            print("Error: JIRA_SERVER, JIRA_USER, and JIRA_TOKEN env vars "
                  "required for --fetch-all mode.", file=sys.stderr)
            sys.exit(2)
        rc = _fetch_all(args.issue_key, args.fetch_all, server, user, token)
        sys.exit(rc)

    # --write-original-only mode: no --fields means caller just wants
    # the original description snapshot written to disk.
    if args.write_original and not args.fields:
        os.makedirs(args.write_original, exist_ok=True)
        orig_path = os.path.join(args.write_original,
                                 f"{args.issue_key}.md")
        base, ext = os.path.splitext(orig_path)
        input_path = base + ".input" + ext
        if all([server, user, token]):
            issue = get_issue(server, user, token, args.issue_key,
                              fields=["description"])
            desc_md = _desc_to_markdown(
                issue.get("fields", {}).get("description"))
            with open(orig_path, "w", encoding="utf-8") as f:
                f.write(desc_md + "\n")
            if os.path.exists(input_path):
                os.remove(input_path)
        elif os.path.exists(input_path):
            shutil.copy2(input_path, orig_path)
            os.remove(input_path)
        else:
            print(f"Warning: no JIRA creds and no {input_path}, "
                  "skipping --write-original", file=sys.stderr)
        return

    # Default fields when not in write-original-only mode
    if not args.fields:
        args.fields = "summary,description,priority,labels,status"

    if not all([server, user, token]):
        print("Error: JIRA_SERVER, JIRA_USER, and JIRA_TOKEN env vars "
              "required.", file=sys.stderr)
        sys.exit(1)

    requested = [f.strip() for f in args.fields.split(",")]
    fetch_comments = "comment" in requested
    api_fields = [f for f in requested if f != "comment"]

    # Fetch the issue
    issue = get_issue(server, user, token, args.issue_key,
                      fields=api_fields if api_fields else None)

    # Build output
    fields = issue.get("fields", {})
    output = {
        "key": issue.get("key"),
        "fields": {},
    }

    for field_name in api_fields:
        value = fields.get(field_name)
        # Convert ADF description to markdown if requested
        if args.markdown and field_name == "description" and \
                isinstance(value, dict):
            value = adf_to_markdown(value).strip()
        output["fields"][field_name] = value

    # Fetch comments separately if requested
    if fetch_comments:
        comments = get_comments(server, user, token, args.issue_key)
        output["comments"] = []
        for c in comments:
            body = c.get("body", {})
            if args.markdown and isinstance(body, dict):
                body = adf_to_markdown(body).strip()
            output["comments"].append({
                "author": c.get("author", {}).get("displayName", "Unknown"),
                "created": c.get("created", ""),
                "body": body,
            })

    # Write original description snapshot for conflict detection
    if args.write_original:
        desc_md = _desc_to_markdown(fields.get("description"))
        os.makedirs(args.write_original, exist_ok=True)
        orig_path = os.path.join(args.write_original,
                                 f"{args.issue_key}.md")
        with open(orig_path, "w", encoding="utf-8") as f:
            f.write(desc_md + "\n")

    json.dump(output, sys.stdout, indent=2)
    print()  # trailing newline


if __name__ == "__main__":
    main()

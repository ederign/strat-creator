#!/usr/bin/env python3
"""Clone a Jira issue into a target project via REST API.

Replicates Jira's UI clone: creates a new issue with the same summary,
description, and priority, then links the two with a Cloners link.

Usage:
    python3 scripts/clone_issue.py RHAIRFE-1397 --target-project RHAISTRAT --issue-type Feature

Output (stdout):
    The new issue key (e.g. RHAISTRAT-1500)

Environment variables:
    JIRA_SERVER  Jira server URL
    JIRA_USER    Jira username/email
    JIRA_TOKEN   Jira API token
"""

import argparse
import sys

from jira_utils import (
    require_env,
    get_issue,
    create_issue,
    create_issue_link,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source_key", help="Source issue key (e.g. RHAIRFE-1397)")
    parser.add_argument("--target-project", required=True,
                        help="Target project key (e.g. RHAISTRAT)")
    parser.add_argument("--issue-type", default="Feature",
                        help="Issue type in target project (default: Feature)")
    args = parser.parse_args()

    server, user, token = require_env()
    if not all([server, user, token]):
        print("Error: JIRA_SERVER, JIRA_USER, and JIRA_TOKEN required.",
              file=sys.stderr)
        sys.exit(2)

    source = get_issue(server, user, token, args.source_key,
                       fields=["summary", "description", "priority", "labels"])
    fields = source.get("fields", {})

    summary = fields.get("summary", "")
    description_adf = fields.get("description")
    priority_obj = fields.get("priority")
    priority = priority_obj.get("name", "Major") if isinstance(
        priority_obj, dict) else "Major"
    labels = [l for l in fields.get("labels", [])
              if l != "strat-creator-processing"]

    new_key = create_issue(
        server, user, token,
        project=args.target_project,
        issue_type=args.issue_type,
        summary=summary,
        description_adf=description_adf,
        priority=priority,
        labels=labels,
    )

    # Cloners link: new issue "is cloned by" source (STRAT is the clone of the RFE)
    create_issue_link(server, user, token,
                      type_name="Cloners",
                      inward_key=new_key,
                      outward_key=args.source_key)

    print(new_key)


if __name__ == "__main__":
    main()

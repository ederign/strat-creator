#!/usr/bin/env python3
"""List RFE IDs from a config file or Jira JQL query.

Usage:
    # From config file (existing behavior)
    python3 scripts/list-rfe-ids.py --config config/road-to-production/batch-03.yaml

    # From Jira using pipeline-settings.yaml
    python3 scripts/list-rfe-ids.py --jql-default

    # From Jira with raw JQL
    python3 scripts/list-rfe-ids.py --jql 'project = RHAIRFE AND labels = "strat-creator-3.5"'

    # Batching
    python3 scripts/list-rfe-ids.py --jql-default --batch-size 10
    python3 scripts/list-rfe-ids.py --jql-default --batch-size 10 --batch-offset 10
"""

import argparse
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(__file__))

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "pipeline-settings.yaml"


def ids_from_config(config_path, baseline=None):
    """Read RFE IDs from a YAML config file."""
    with open(config_path) as f:
        data = yaml.safe_load(f)
    ids = []
    for rfe in data.get("test_rfes", []):
        is_baseline = rfe.get("baseline", False)
        if baseline is True and not is_baseline:
            continue
        if baseline is False and is_baseline:
            continue
        ids.append(rfe["id"])
    return ids


def ids_from_jql(jql):
    """Search Jira with a JQL query and return issue keys."""
    from jira_utils import require_env, search_issues

    server, user, token = require_env()
    if not all([server, user, token]):
        print("Error: JIRA_SERVER, JIRA_USER, JIRA_TOKEN required for "
              "--jql mode.", file=sys.stderr)
        sys.exit(2)
    issues = search_issues(server, user, token, jql, fields=["key"])
    return [issue["key"] for issue in issues]


def main():
    parser = argparse.ArgumentParser(description="List RFE IDs")

    source = parser.add_mutually_exclusive_group()
    source.add_argument("--config", default=None,
                        help="Path to batch config YAML")
    source.add_argument("--jql", default=None,
                        help="Raw JQL query string")
    source.add_argument("--jql-default", nargs="?", const="",
                        default=None, metavar="SETTINGS",
                        help="Build JQL from pipeline-settings.yaml "
                             "(optionally pass a custom settings path)")

    baseline_group = parser.add_mutually_exclusive_group()
    baseline_group.add_argument("--baseline", action="store_true",
                                help="Only baseline RFEs (config mode)")
    baseline_group.add_argument("--no-baseline", action="store_true",
                                help="Exclude baseline RFEs (config mode)")

    parser.add_argument("--include-processed", action="store_true",
                        help="Include RFEs whose STRATs already have "
                             "skip labels (default: exclude them)")
    parser.add_argument("--batch-size", type=int, default=None,
                        help="Limit output to N RFE IDs")
    parser.add_argument("--batch-offset", type=int, default=0,
                        help="Skip first N RFE IDs")

    args = parser.parse_args()

    # Determine source mode
    if args.jql is not None:
        ids = ids_from_jql(args.jql)
        print(f"JQL returned {len(ids)} RFE(s)", file=sys.stderr)

    elif args.jql_default is not None:
        from jira_utils import build_jql_from_config
        settings = args.jql_default if args.jql_default else str(SETTINGS_PATH)
        jql = build_jql_from_config(settings)
        print(f"JQL: {jql}", file=sys.stderr)
        ids = ids_from_jql(jql)
        print(f"JQL returned {len(ids)} RFE(s)", file=sys.stderr)

        # Read batch_size from settings if not overridden on CLI
        if args.batch_size is None:
            with open(settings) as f:
                cfg = yaml.safe_load(f)
            args.batch_size = cfg.get("batch_size")

    else:
        config_path = args.config or str(
            Path(__file__).resolve().parent.parent / "config" / "test-rfes.yaml"
        )
        if not Path(config_path).exists():
            print(f"Error: {config_path} not found", file=sys.stderr)
            sys.exit(1)
        baseline = None
        if args.baseline:
            baseline = True
        elif args.no_baseline:
            baseline = False
        ids = ids_from_config(config_path, baseline)

    # Exclude already-processed RFEs (JQL modes only, unless --include-processed)
    in_jql_mode = args.jql is not None or args.jql_default is not None
    if not args.include_processed and in_jql_mode:
        from jira_utils import find_processed_rfe_ids, require_env
        settings = None
        if args.jql_default is not None:
            settings = args.jql_default if args.jql_default else str(SETTINGS_PATH)
        if settings:
            with open(settings) as f:
                skip_cfg = yaml.safe_load(f)
            skip_labels = skip_cfg.get("skip_labels", [])
        else:
            skip_labels = ["strat-creator-rubric-pass",
                           "strat-creator-needs-attention"]
        if skip_labels:
            server, user, token = require_env()
            processed = find_processed_rfe_ids(server, user, token, skip_labels)
            before = len(ids)
            ids = [i for i in ids if i not in processed]
            excluded = before - len(ids)
            if excluded:
                print(f"Excluded {excluded} already-processed RFE(s), "
                      f"{len(ids)} remaining", file=sys.stderr)

    # Apply batching
    ids = ids[args.batch_offset:]
    if args.batch_size is not None:
        ids = ids[:args.batch_size]

    for rfe_id in ids:
        print(rfe_id)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Export the assess-strat scoring rubric to artifacts/strat-rubric.md.

Reads the rubric from the bootstrapped assess-strat plugin and writes
it to artifacts/strat-rubric.md in the current working directory.

Usage:
    python3 scripts/export_rubric.py
    python3 scripts/export_rubric.py --source /path/to/agent_prompt.md
    python3 scripts/export_rubric.py --output /path/to/output.md
"""

import argparse
import os
import sys


DEFAULT_SOURCE = os.path.join(".context", "assess-strat", "scripts", "agent_prompt.md")
DEFAULT_OUTPUT = os.path.join("artifacts", "strat-rubric.md")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default=DEFAULT_SOURCE,
                        help=f"Path to rubric source (default: {DEFAULT_SOURCE})")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help=f"Path to write rubric (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()

    if not os.path.exists(args.source):
        print(f"ERROR: Rubric source not found at {args.source}", file=sys.stderr)
        print("Run bootstrap-assess-strat.sh first to clone the assess-strat plugin.", file=sys.stderr)
        sys.exit(1)

    with open(args.source, encoding="utf-8") as f:
        rubric = f.read()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(rubric)

    print(f"Rubric exported to {args.output}")


if __name__ == "__main__":
    main()

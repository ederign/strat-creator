#!/usr/bin/env python3
import json
import os
import urllib.request
import urllib.error
import base64
import math
import sys

JIRA_SERVER = os.environ["JIRA_SERVER"]
JIRA_USER = os.environ["JIRA_USER"]
JIRA_TOKEN = os.environ["JIRA_TOKEN"]

TARGET_LABELS = {
    "rfe-creator-autofix-rubric-pass",
    "tech-reviewed",
    "strat-creator-3.5",
}

BATCH_SIZE = 10

RFE_BIG_ROCK = {
    184: ["AutoRAG"],
    238: ["Eval Hub"],
    262: ["Observability"],
    284: ["BYO Agent"],
    428: ["BYO Agent"],
    522: ["BYO Agent"],
    648: ["BYO Agent"],
    709: ["Gen AI Studio"],
    710: ["BYO Agent"],
    727: ["Gen AI Studio", "BYO Agent"],
    728: ["Gen AI Studio", "BYO Agent"],
    794: ["BYO Agent"],
    795: ["Eval Hub"],
    856: ["BYO Agent"],
    911: ["BYO Agent"],
    912: ["Gen AI Studio", "BYO Agent"],
    913: ["Gen AI Studio", "BYO Agent"],
    928: ["BYO Agent"],
    940: ["MaaS"],
    976: ["BYO Agent"],
    1021: ["Eval Hub"],
    1028: ["BYO Agent"],
    1056: ["llm-d"],
    1061: ["Gen AI Studio", "BYO Agent"],
    1131: ["MaaS", "Observability"],
    1160: ["Eval Hub"],
    1161: ["Eval Hub"],
    1163: ["Eval Hub"],
    1164: ["Eval Hub"],
    1165: ["Eval Hub"],
    1166: ["Eval Hub"],
    1167: ["Eval Hub"],
    1168: ["Eval Hub"],
    1169: ["Eval Hub"],
    1179: ["Eval Hub"],
    1180: ["Eval Hub"],
    1181: ["Eval Hub"],
    1189: ["Tool Calling", "AI Hub"],
    1230: ["BYO Agent"],
    1236: ["llm-d"],
    1237: ["llm-d"],
    1239: ["AI Hub"],
    1273: ["BYO Agent"],
    1293: ["AI Hub"],
    1313: ["BYO Agent"],
    1331: ["BYO Agent"],
    1332: ["BYO Agent"],
    1351: ["BYO Agent"],
    1391: ["BYO Agent", "AI Safety", "Gen AI Studio"],
    1428: ["Tool Calling"],
    1429: ["Tool Calling"],
    1431: ["Tool Calling"],
    1432: ["Tool Calling"],
    1433: ["Tool Calling"],
    1435: ["BYO Agent"],
    1436: ["BYO Agent"],
    1443: ["MaaS"],
    1445: ["BYO Agent"],
    1449: ["AutoRAG"],
    1451: ["Gen AI Studio", "BYO Agent"],
    1452: ["AutoRAG"],
    1454: ["Gen AI Studio", "BYO Agent"],
    1455: ["Gen AI Studio", "BYO Agent"],
    1457: ["BYO Agent"],
    1461: ["AutoML"],
    1469: ["BYO Agent"],
    1470: ["AutoML"],
    1472: ["AutoML"],
    1482: ["AutoML"],
    1484: ["AI Hub", "BYO Agent"],
    1486: ["MaaS"],
    1487: ["MaaS"],
    1495: ["llm-d"],
    1506: ["BYO Agent"],
    1528: ["BYO Agent"],
    1531: ["BYO Agent"],
    1543: ["Tool Calling"],
    1554: ["Tool Calling", "BYO Agent"],
    1586: ["BYO Agent"],
    1614: ["BYO Agent"],
    1639: ["BYO Agent"],
    1640: ["BYO Agent"],
    1641: ["BYO Agent"],
    1642: ["BYO Agent"],
    1643: ["BYO Agent"],
    1644: ["BYO Agent"],
    1645: ["BYO Agent"],
    1646: ["BYO Agent"],
    1651: ["BYO Agent"],
    1652: ["BYO Agent"],
    1712: ["BYO Agent"],
    1713: ["BYO Agent"],
    1779: ["Tool Calling"],
    1917: ["BYO Agent"],
    1927: ["AI Hub"],
    1930: ["Tool Calling"],
    1931: ["Tool Calling"],
}


def fetch_rfe(rfe_num):
    key = f"RHAIRFE-{rfe_num}"
    url = f"{JIRA_SERVER}/rest/api/2/issue/{key}?fields=summary,labels"
    creds = base64.b64encode(f"{JIRA_USER}:{JIRA_TOKEN}".encode()).decode()
    req = urllib.request.Request(url, headers={
        "Authorization": f"Basic {creds}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        fields = data["fields"]
        return {
            "summary": fields["summary"],
            "labels": [l for l in fields.get("labels", []) if l in TARGET_LABELS],
        }
    except urllib.error.HTTPError as e:
        print(f"  WARNING: Failed to fetch {key}: HTTP {e.code}", file=sys.stderr)
        return None


def yaml_escape(s):
    if any(c in s for c in ":#{}[]&*?|>!%@`,"):
        return f"'{s}'"
    if s.startswith("- ") or s.startswith("  "):
        return f"'{s}'"
    return s


def write_batch(batch_num, total_batches, rfes, output_dir):
    filename = f"batch-{batch_num:02d}.yaml"
    path = os.path.join(output_dir, filename)
    lines = [
        f"# Engineering 3.5 — Batch {batch_num} of {total_batches}",
        f"# {len(rfes)} RFEs",
        "test_rfes:",
    ]
    for rfe in rfes:
        lines.append(f"- id: RHAIRFE-{rfe['num']}")
        lines.append(f"  title: {yaml_escape(rfe['title'])}")
        lines.append("  big_rock:")
        for br in rfe["big_rock"]:
            lines.append(f"    - {br}")
        if rfe["labels"]:
            lines.append("  labels:")
            for label in sorted(rfe["labels"]):
                lines.append(f"    - {label}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Wrote {filename} ({len(rfes)} RFEs)")


def main():
    output_dir = os.path.dirname(os.path.abspath(__file__))
    sorted_nums = sorted(RFE_BIG_ROCK.keys())
    print(f"Processing {len(sorted_nums)} RFEs...")

    rfes = []
    for num in sorted_nums:
        print(f"  Fetching RHAIRFE-{num}...")
        jira_data = fetch_rfe(num)
        if jira_data is None:
            print(f"  Skipping RHAIRFE-{num} (fetch failed)")
            continue
        rfes.append({
            "num": num,
            "title": jira_data["summary"],
            "big_rock": RFE_BIG_ROCK[num],
            "labels": jira_data["labels"],
        })

    total_batches = math.ceil(len(rfes) / BATCH_SIZE)
    print(f"\nGenerating {total_batches} batches...")

    for i in range(total_batches):
        batch_rfes = rfes[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
        write_batch(i + 1, total_batches, batch_rfes, output_dir)

    print(f"\nDone: {len(rfes)} RFEs in {total_batches} batches")


if __name__ == "__main__":
    main()

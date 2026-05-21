# Troubleshooting

Common issues and how to resolve them.

## Strategy Not Picked Up by Pipeline

**Symptoms:** Your RFE exists in Jira but no RHAISTRAT was created.

**Check:**

1. Does the RHAIRFE have `strat-creator-3.5` label? (or matching Target Version)
2. Does it have a quality gate label (`rfe-creator-autofix-rubric-pass` or `tech-reviewed`)?
3. Is the status something other than `Closed`, `Resolved`, or `Draft`?
4. Does it already have a RHAISTRAT with `strat-creator-rubric-pass` or `strat-creator-needs-attention`? (pre-filter exclusion)

**Bypass pre-filter:**

```bash
python3 scripts/list-rfe-ids.py --jql-default --include-processed
```

## Stuck Processing Lock

**Symptoms:** RHAISTRAT has `strat-creator-processing` label for over an hour.

**Cause:** Pipeline job crashed before removing the lock.

**Fix:**

```bash
python3 scripts/lock_issues.py unlock RHAIRFE-NNNN
```

## CI Scoring Failure

**Symptoms:** Review file has no scores or the scorer agent timed out.

**Check:**

1. Did `scripts/bootstrap-assess-strat.sh` succeed? Check if `.context/assess-strat/` exists.
2. Is the assess-strat plugin accessible? It's cloned from GitHub at runtime.
3. Check the scorer agent output in `/tmp/strat-assess/review/` for error details.

**Workaround:** Run scoring locally:

```bash
claude "/strategy-review RHAISTRAT-NNNN --dry-run"
```

## Jira Connectivity Issues

**Symptoms:** `fetch_issue.py` or skill commands fail with authentication errors.

**Check:**

1. Are `JIRA_SERVER`, `JIRA_USER`, `JIRA_TOKEN` set?
2. Has the API token expired? Regenerate at [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
3. Are you behind a VPN that blocks Jira access?

## Large Strategy Attachment Issues

**Symptoms:** Jira description shows only a TL;DR stub.

**Explanation:** Strategies exceeding ~32K characters are stored as Jira attachments (`RHAISTRAT-NNNN-strategy.md`) with a stub in the description. This is normal behavior.

**To view the full strategy:** Use `/strategy-pull RHAISTRAT-NNNN` which reassembles the full content, or download the attachment from Jira directly.

## Architecture Context Stale

**Symptoms:** Strategies reference outdated component versions or missing dependencies.

**Fix:**

1. Check if an [overlay](architecture-context.md) exists for the issue
2. If not, create one and test locally
3. Submit PR to [architecture-context](https://github.com/opendatahub-io/architecture-context)
4. Re-fetch: `bash scripts/fetch-architecture-context.sh`

## Skills Not Loading

**Symptoms:** Claude Code doesn't recognize `/strategy-pull` or other commands.

**Check:**

1. Are you in the strat-creator repo directory?
2. Is the `.claude/skills/` directory present with skill subdirectories?
3. Try restarting Claude Code: `exit` then `claude`

## Local Review Scores Don't Match CI

**Symptoms:** Strategy passes locally but fails in CI (or vice versa).

**Possible causes:**

- Different architecture context version (CI fetches fresh, local may be stale)
- Local Staff Engineer Input not pushed to Jira yet
- Different assess-strat rubric version (CI bootstraps latest)

**Fix:** Re-fetch architecture context and re-bootstrap assess-strat before local review.

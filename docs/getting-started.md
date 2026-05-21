# Getting Started

This page covers setup for all roles. After completing these steps, follow the workflow guide for your role.

## Prerequisites

- A Red Hat Jira account with access to the RHAIRFE and RHAISTRAT projects
- Git and Python 3.11+

## 1. Install Claude Code

Follow the [Claude Code installation guide](https://docs.anthropic.com/en/docs/claude-code). Verify it's working:

```bash
claude --version
```

## 2. Clone the Repository

```bash
git clone https://github.com/ederign/strat-creator.git
cd strat-creator
```

## 3. Install Dependencies

```bash
uv sync
```

## 4. Set Up Jira Credentials

Export your Jira credentials so the pipeline can read from and write to Jira:

```bash
export JIRA_SERVER="https://redhat.atlassian.net"
export JIRA_USER="your-email@redhat.com"
export JIRA_TOKEN="your-atlassian-api-token"
```

To generate an API token, go to [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens).

!!! tip
    Add these exports to your shell profile (`~/.zshrc` or `~/.bashrc`) so they persist across sessions.

## 5. Verify Skills Load

Start a Claude Code session and verify the strategy skills are available:

```bash
claude
```

Then type `/strategy-pull` and confirm it responds (it will ask for a strategy key). This confirms the skills are loaded and Jira credentials are configured.

## Next Steps

- **Product Managers**: [PM Workflow Guide](workflow-guide/product-managers.md)
- **Staff Engineers / Architects**: [Staff Engineer Workflow Guide](workflow-guide/staff-engineers.md)
- **Engineering Managers**: [EM Workflow Guide](workflow-guide/engineering-managers.md)

For reference material, see the [Concepts & Glossary](glossary.md).

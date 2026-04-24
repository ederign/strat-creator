# Road to Production — Batch Index

| Batch | RFEs | Theme | Status |
|-------|------|-------|--------|
| [batch-01](batch-01.yaml) | 3 | Initial validation (Kubeflow SDK, Guardrails, Model Serving) | ran 2026-04-21 |
| [batch-02](batch-02.yaml) | 5 | External endpoints, Chat metrics, Persistence, YAML Editor | ran 2026-04-22 |
| [small-batch](small-batch.yaml) | 1 | Granular Role Creation UI (single-RFE test) | ran 2026-04-22 |
| [batch-03](batch-03.yaml) | 10 | MaaS (policy, multi-tenancy, HA, consumer portal, PII) | ran 2026-04-23 |
| [batch-04](batch-04.yaml) | 10 | MaaS quotas, Gen AI Studio (RAG, vector stores, prompts), Model Catalog | ran 2026-04-23 |
| [batch-05](batch-05.yaml) | 10 | Gen AI Studio (guardrails, prompts, secrets), Observability, EvalHub | ran 2026-04-23 |
| [batch-06](batch-06.yaml) | 10 | EvalHub (diagnostics, notifications), MCP operators, Kueue | ran 2026-04-24 |
| [batch-07](batch-07.yaml) | 10 | RBAC, Inference UI, Guardrails, Hardware Profiles, RAG, Kueue | pending |
| [batch-08](batch-08.yaml) | 1 | AutoRAG (MLFlow integration) | pending |

**Total: 60 RFEs across 9 configs**

## Log

- **2026-04-23**: Accidentally ran `config/dashboard35-batches/batch-03.yaml` instead of `config/road-to-production/batch-03.yaml` in pipeline #2474351509. Dashboard batch-03 processed 3 strategies (RHAISTRAT-1172, 1182, 1314). Re-triggered with the correct road-to-production batch-03 in pipeline #2474597269.

## STRATs without source RFE

These STRATs have no Cloners link to any RHAIRFE and cannot be processed through the RFE→STRAT pipeline:

RHAISTRAT-1378, RHAISTRAT-1415, RHAISTRAT-1281, RHAISTRAT-138, RHAISTRAT-1455, RHAISTRAT-1267, RHAISTRAT-1518, RHAISTRAT-1078

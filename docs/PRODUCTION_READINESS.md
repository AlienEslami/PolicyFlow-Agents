# Production readiness and Azure fit-gap

The repository separates what runs now from a credible Azure production target. The
deployment files are reviewable patterns; no cloud deployment is claimed.

| Capability | Local implementation | Production target / gap |
|---|---|---|
| Identity | Typed roles from demo headers | Entra ID OIDC validation, group/app-role mapping, managed workload identity |
| Secrets | No live credentials | Azure Key Vault through the Secrets Store CSI driver; rotation and startup-failure tests |
| Compute | Hardened local container | Private AKS, Azure CNI policy, pod identity, signed image from ACR, multi-zone replicas |
| Data | In-process workflow store and frozen JSON | Azure Database for PostgreSQL with pgvector, RLS, private endpoint, backups, PITR, migrations |
| Models | Deterministic default; optional local adapters | Approved model gateway, private networking, quotas, version pinning, content filters |
| Observability | Prometheus counters/histograms | OpenTelemetry traces, Azure Monitor dashboards, redacted logs, alerts, runbook links |
| Delivery | GitHub Actions lint/type/test/eval/build | OIDC federation, SBOM, image/signature scan, policy admission, staged promotion and rollback |
| Reliability | Bounded graph and idempotent adapter | Durable queue/outbox worker, timeouts, circuit breakers, retries with jitter, dead-letter queue |
| Governance | Deterministic gates and audit chain | Model inventory, DPIA/PIA, risk tier, validation sign-off, change approval, evidence retention |

## Proposed service levels

- API availability: 99.9% monthly for case-brief creation, excluding planned maintenance.
- p95 synchronous workflow latency: under 8 seconds excluding approved asynchronous work.
- Action duplication: zero accepted duplicates for the same idempotency key.
- Tenant leakage and unauthorized dispatch: zero tolerance, with page-level alerts.
- Recovery objectives: product-owned RPO/RTO established before pilot; restore exercises
  must be completed before production approval.

## Promotion gates

1. Threat model, privacy assessment, data classification, and connector scopes approved.
2. Frozen benign/adversarial evaluation meets task-specific thresholds in both languages.
3. Model and prompt versions, retrieval corpus, tool schemas, and policy versions are in a
   signed release manifest.
4. Load, chaos, timeout, retry, idempotency, tenant-isolation, and rollback tests pass.
5. Dashboards, alerts, on-call ownership, runbooks, kill switch, and manual fallback exist.
6. A controlled pilot proves business value without autonomous adjudication.


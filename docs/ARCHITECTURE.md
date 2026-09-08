# Architecture

Status: implemented local vertical slice with an explicit production target.

## System boundary

The local system begins at the authenticated FastAPI boundary and ends at an idempotent
call to a synthetic case-management adapter. It includes a typed LangGraph, a frozen
retrieval snapshot, read-only enterprise adapters, scoped memory, deterministic policy
gates, action approval, metrics, and a hash-chained audit trail.

It excludes claim adjudication, payment, customer communication, fraud scoring, real
identity, insurer data, live connectors, cloud deployment, and operational certification.

## Agent responsibilities

| Agent | Responsibility | Explicit prohibition |
|---|---|---|
| Intake guard | Validate role and reject injection or prohibited objectives | Cannot rewrite or soften a blocked objective |
| Memory agent | Recall tenant/user/case-scoped redacted notes | Cannot access another user, case, or tenant namespace |
| Supervisor agent | Produce a bounded five-step plan and allowlisted read calls | Cannot invent tools or dispatch actions |
| Knowledge agent | Retrieve approved guidance after tenant/classification filtering | Cannot rank unauthorized or quarantined content |
| Tool agent | Invoke typed minimum-data enterprise reads | Cannot expose direct identifiers or call write tools |
| Synthesis agent | Create a bilingual cited brief | Cannot approve, deny, or decide coverage/eligibility |
| Risk agent | Independently evaluate citations, completeness, status, and review tier | Cannot be overridden by the synthesis model |
| Action agent | Stage an adjuster-review proposal and idempotency key | Cannot approve or execute its own proposal |

## Trust boundaries and data flow

1. The API maps trusted identity claims to a `Principal`. The local header adapter is a
   demonstrator; production uses verified Entra ID tokens and workload identity.
2. The objective crosses an untrusted-text boundary and is inspected before model,
   retrieval, tool, or memory access.
3. Knowledge ACL, lifecycle, locale, classification, and injection predicates run before
   ranking. The PostgreSQL adapter additionally sets a transaction-local tenant context
   used by row-level security.
4. The supervisor emits a fixed plan. Tool calls are reconstructed from the validated case
   ID; arbitrary model-authored tool names and arguments are never executed.
5. The gateway returns an allowlisted field projection. Synthetic names and emails remain
   in the backing fixture and prove that direct identifiers are excluded.
6. The synthesis result is checked against the frozen citation set. Missing enterprise
   reads, missing documents, and inactive policy status stop action staging.
7. The action is immutable in meaning and requires a different approver. Dispatch accepts
   only approved actions and uses a stable idempotency key.

## Persistence target

`migrations/0001_initial.sql` defines PostgreSQL 17 tables for versioned knowledge,
pgvector/full-text chunks, runs, tool events, findings, action outbox, approvals, TTL
memory, and audit events. Tenant row-level security, immutable approval/audit triggers,
foreign keys, unique idempotency keys, and HNSW/GIN indexes reinforce application policy.

The default executable intentionally uses in-process repositories so reviewers can run it
without infrastructure. `PostgresHybridRetriever` implements the tenant-filtered hybrid
query. Wiring all state adapters to PostgreSQL is a named production gap.

## Reliability properties

- The graph is acyclic; there are no open-ended tool or reflection loops.
- All tool names are statically allowlisted and all connector calls return typed outcomes.
- Actions are staged before execution and dispatch is idempotent.
- Failed enterprise reads fail closed to `needs_information`.
- Every workflow terminal state is counted; every agent node and tool call is measurable.
- Audit events form an application-verifiable hash chain.


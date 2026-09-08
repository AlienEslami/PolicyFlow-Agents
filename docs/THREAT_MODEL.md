# Threat model

## Protected assets

- tenant and case isolation;
- direct identifiers and confidential case data;
- approved knowledge and its retrieval provenance;
- tool credentials and connector authority;
- human-approval integrity;
- action idempotency and audit history.

## Abuse cases and controls

| Threat | Implemented control | Verification |
|---|---|---|
| Prompt injection in an objective | Intake patterns fail closed before retrieval/tools | Unsafe-objective tests and red-team cases |
| Prompt injection in knowledge | Lifecycle and injection flags filter before ranking | Poisoned-document retrieval test |
| Cross-tenant discovery | Pre-ranking tenant predicate and gateway tenant check | Cross-tenant retrieval, case, and run tests |
| Sensitive-data prompt/log leakage | Minimum-field tool projections and memory redaction | Tool projection and memory tests |
| Arbitrary model tool execution | Fixed registry and trusted argument reconstruction | Unknown-tool rejection test |
| Autonomous approval/denial | Objective gate plus non-model risk/action state machine | Autonomous-decision red-team case |
| Self-approval | Requester/approver separation of duties | Independent-approval test |
| Duplicate downstream task | Stable action idempotency key and replay result | Double-dispatch test |
| Audit alteration | Hash chain locally; immutable triggers in PostgreSQL target | Audit verification test and migration |
| Denial of service through loops | Acyclic graph, fixed tool count, bounded request fields | Graph inspection and Pydantic limits |

## Residual risks

- Pattern matching is not a complete injection detector. Production needs layered content
  scanning, model isolation, output validation, attack telemetry, and incident response.
- The local header identity adapter is forgeable and is unsuitable for deployment.
- The deterministic synthesis baseline is not evidence of LLM quality or robustness.
- Hash chaining detects application-level modification but is not an external timestamp or
  tamper-proof ledger.
- Memory deletion, legal hold, consent, retention policy, data residency, and backup
  procedures require product-, privacy-, and jurisdiction-specific decisions.
- Human approval can still be negligent or compromised; production requires strong
  authentication, least privilege, training, sampling, and review analytics.


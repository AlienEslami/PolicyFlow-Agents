# Verified AWS deployment evidence

PolicyFlow Agents was deployed to AWS Canada Central on 2026-09-08. The workload remains
synthetic-only and Bedrock is implemented but disabled in the continuously running stack.

## Artefact-fit extension release

| Evidence | Verified value |
|---|---|
| Public operator console | <https://d20g4ajd2f79hc.cloudfront.net/ui/> (`200`, browser-inspected) |
| CloudFormation service stack | `UPDATE_COMPLETE` |
| Stable ECS task definition | `policyflow-agents-prod:8` (1 desired, 1 running, 0 pending) |
| Deployed source revision | `cf08e521ef9d5d842b35c8d6b6b0402ea9a0dc4e` |
| Immutable image | `071239861872.dkr.ecr.ca-central-1.amazonaws.com/policyflow-agents-prod:cf08e521ef9d5d842b35c8d6b6b0402ea9a0dc4e` |
| Image digest | `sha256:9e922a9f3de7329477f14290640dab5bb591f09796592a639a19965d4d630fcf` |
| GitHub deployment | [successful Deploy AWS run](https://github.com/AlienEslami/PolicyFlow-Agents/actions/runs/34284020832) |
| Companion validation | [successful CI run](https://github.com/AlienEslami/PolicyFlow-Agents/actions/runs/34284020819) |

The extension adds the React/TypeScript operator console, a scoped MCP Streamable HTTP
surface, model usage/latency reporting, and the S3/SQS/Lambda ingestion path. The deployed
MCP client discovered exactly `get_claim` and `check_required_documents`, then invoked
`get_claim` with an authorized tenant context through CloudFront. The minimum-necessary
response omitted direct personal identifiers. A request without the bearer token returned
`401`.

The live ingestion proof created two content-addressed chunks from the frozen sample. One
safe chunk remained available and the deliberately hostile prompt-injection-shaped chunk
was tagged `quarantined: true`. Lambda was `Active`; ingestion-error, DLQ, CPU, target-5xx,
and unhealthy-target alarms were all `OK`. The manifest is tracked as
[`docs/evidence/ingestion-manifest-2026-09-08.json`](evidence/ingestion-manifest-2026-09-08.json).

The final GitHub HTTPS gate sent 60 requests at concurrency 6: all 60 returned `200`, mean
latency was 127.666 ms, p95 was 404.590 ms, and maximum was 406.135 ms. Its JSON artifact is
retained as `policyflow-aws-cf08e521ef9d5d842b35c8d6b6b0402ea9a0dc4e`, with a durable
repository copy at
[`docs/evidence/aws-deployment-cf08e521/load-test.json`](evidence/aws-deployment-cf08e521/load-test.json).
The ECR scan
completed with zero critical and three high findings. A separate controlled Bedrock
evaluation made three successful Nova 2 Lite requests and is documented in
[the Bedrock evaluation report](BEDROCK_EVALUATION.md).

The stack's automatic rollbacks were also exercised during implementation: an initial S3
notification/KMS incompatibility and an account-level Lambda reserved-concurrency limit
both rolled back cleanly. The final design uses S3-compatible SSE-SQS and an event-source
maximum-concurrency cap, then reached `UPDATE_COMPLETE`. This is concrete failure-recovery
evidence rather than a claimed production incident history.

The first extension workflow exposed a separate delivery failure: a local stack update
mistakenly reclassified its stack-managed GitHub OIDC provider as external and CloudFormation
deleted it. GitHub correctly failed closed before ECR or ECS mutation. The deployment script
now detects stack ownership, CloudFormation restored the provider, and the next workflow
successfully assumed the least-privilege role and completed every release gate.

The first final alarm review found S3's automatic notification-configuration `TestEvent`
in the ingestion DLQ. The normal sample had processed successfully, but this control
envelope intentionally has no `Records[]` field. The Lambda now explicitly acknowledges
that event shape; the single message was redriven after the fix and the DLQ alarm returned
to `OK`.

## Baseline release (historical)

| Evidence | Verified value |
|---|---|
| Public endpoint | <https://d20g4ajd2f79hc.cloudfront.net> |
| AWS region | `ca-central-1` |
| CloudFormation stacks | `policyflow-agents-prod-ecr`, `policyflow-agents-prod-service` |
| ECS cluster and service | `policyflow-agents-prod` |
| Stable task definition | `policyflow-agents-prod:3` |
| Deployed source revision | `4e28852745de4e5aee930c6a81d17ecc4d385224` |
| Immutable image | `071239861872.dkr.ecr.ca-central-1.amazonaws.com/policyflow-agents-prod:4e28852745de4e5aee930c6a81d17ecc4d385224` |
| Image digest | `sha256:2113dc033e9ef3c354a4a2df5a954fb1864e6d8b83c75a2597c7025876d453ea` |
| GitHub deployment | [successful Deploy AWS run](https://github.com/AlienEslami/PolicyFlow-Agents/actions/runs/34272524845) |
| Companion validation | [successful CI run](https://github.com/AlienEslami/PolicyFlow-Agents/actions/runs/34272524902) |

At the final check, ECS reported one desired task, one running task, no pending tasks, and
a completed deployment rollout. CloudFormation reported both stacks as complete.

## Release gates and runtime checks

- The GitHub workflow assumed its AWS role using OIDC, built and pushed the commit-SHA
  image, waited for an ECR scan to complete, verified zero critical findings, registered
  a new task revision, and waited for ECS stability.
- The public landing page and `/health/live` returned `200`. An unauthenticated protected
  API request returned `401`; the same request with the generated runtime bearer token
  returned `200`.
- A direct request to the ALB returned `403`, confirming the CloudFront origin-verification
  control. The public CloudFront endpoint enforces HTTPS.
- The post-deployment gate sent 60 requests at concurrency 6: 60 succeeded, none failed,
  mean latency was 117.447 ms, p95 was 352.147 ms, and maximum latency was 366.337 ms.
  GitHub retained the JSON result as artifact
  `policyflow-aws-4e28852745de4e5aee930c6a81d17ecc4d385224`.

## Security and observability evidence

- The container runs as UID/GID `10001:10001`, has a read-only root filesystem, and drops
  Linux capabilities. The bearer token is generated and stored in Secrets Manager, then
  injected into the task without appearing in source, task JSON, GitHub variables, or
  logs.
- The execution role is scoped to the one ECR repository, log group, and runtime secret.
  The task role has no AWS permissions while Bedrock is disabled. The GitHub role trusts
  the exact repository/environment subject and can operate only the named delivery
  resources and pass the two task roles.
- The final deployed image's ECR scan completed with zero critical and three high findings
  in Alpine's `libuuid`/`util-linux` runtime package. They require local privileged access;
  the non-root, read-only, capability-dropped task reduces exposure, but the findings remain
  tracked residual risk until Alpine publishes the applicable package fix.
- The `/ecs/policyflow-agents-prod` log group receives structured application and EMF
  events through the `awslogs` driver; a final read returned both a structured
  `request_completed` record and its EMF latency/count record. The `PolicyFlow` namespace
  exposed request count, latency, and application-error metrics, while
  `ECS/ContainerInsights` exposed running task metrics. The stack also created health,
  5xx, CPU, and latency alarms plus a CloudWatch dashboard.

## Reproduction and recovery

The deployment is reproducible through `.github/workflows/deploy-aws.yml` and the two
CloudFormation templates under `infra/aws`. Automatic rollback uses the ECS deployment
circuit breaker. Manual rollback and failure-specific recovery steps are documented in
[AWS operations](AWS_OPERATIONS.md); the architecture and trust boundaries are documented
in [AWS architecture](AWS_ARCHITECTURE.md).

## Defensible resume statement

> Deployed a containerized FastAPI/LangGraph service to AWS ECS Fargate using immutable
> ECR images and GitHub Actions OIDC; implemented least-privilege IAM, Secrets Manager,
> CloudFront HTTPS, ALB/ECS health checks, CloudWatch observability, vulnerability and load
> gates, and automatic/manual rollback procedures.

This statement describes the synthetic portfolio deployment. It does not claim production
insurance traffic, availability history, or autonomous claim adjudication.

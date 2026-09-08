# Verified AWS deployment evidence

PolicyFlow Agents was deployed to AWS Canada Central on 2026-09-08. The workload remains
synthetic-only and Bedrock is implemented but disabled in the live stack.

## Live release

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
- ECR scanning found no critical findings. A validation scan reported three high findings
  in Alpine's `libuuid`/`util-linux` runtime package. They require local privileged access;
  the non-root, read-only, capability-dropped task reduces exposure, but the findings remain
  tracked residual risk until Alpine publishes the applicable package fix.
- The `/ecs/policyflow-agents-prod` log group receives structured application and EMF
  events through the `awslogs` driver. The `PolicyFlow` namespace exposed request count,
  latency, and application-error metrics, while `ECS/ContainerInsights` exposed running
  task metrics. The stack also created health, 5xx, CPU, and latency alarms plus a
  CloudWatch dashboard.

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

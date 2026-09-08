# AWS operations, recovery, and costs

## Initial deployment

Prerequisites are Docker, AWS CLI v2 authenticated with a short-lived administrator or
infrastructure-provisioning session, and a GitHub repository whose owner/repository IDs are
known. The recommended region is `ca-central-1`.

1. Create the GitHub repository and `aws-production` environment, then read its numeric
   owner and repository IDs.
2. Form the immutable subject:
   `repo:OWNER@OWNER_ID/REPOSITORY@REPOSITORY_ID:environment:aws-production`.
3. Run `scripts/deploy_aws.ps1 -GitHubSubject '<subject>'`. Leave Bedrock disabled for the
   first deployment.
4. Put the returned role ARN and HTTPS URL into GitHub repository variables
   `AWS_DEPLOY_ROLE_ARN` and `POLICYFLOW_HTTPS_URL`.
5. Push `main`; the deployment workflow must pass and retain its load-test artifact.

The deploy script writes only non-secret outputs to `artifacts/aws-stack-outputs.json` and
the measured result to `artifacts/aws-load-test.json`. Both are ignored until explicitly
reviewed for publication.

## Rollback

Automatic rollback is enabled in the ECS deployment circuit breaker. If an already-stable
release later regresses, run:

```powershell
.\scripts\rollback_aws.ps1
```

The script selects the previous active task-definition revision, updates the service, and
waits for stability. Pass `-TaskDefinitionArn` to select a specific known-good revision.
After rollback, rerun the HTTPS load test and inspect the CloudWatch dashboard, target
health, ECS stopped-task reasons, and application logs.

## Failure recovery

| Failure | Detection | Recovery |
|---|---|---|
| Container fails to start or health check | ECS circuit breaker, unhealthy-target alarm, ECS events | Automatic rollback; inspect stopped-task reason and `/ecs/policyflow-agents-prod` logs |
| Application 5xx increase | ALB target-5xx alarm and dashboard | Roll back task revision; correlate request IDs in structured logs |
| High CPU or latency | ECS CPU alarm, Container Insights, ALB p95, EMF latency | Inspect hot route; temporarily raise desired count; fix and redeploy |
| Secret retrieval failure | Task stops with resource-initialization error | Verify execution-role resource ARN and secret state; rotate/redeploy without printing value |
| ECR image scan fails | GitHub deployment stops before ECS update | Patch dependencies/base image and push a new commit-SHA tag |
| CloudFront returns 403 | ALB origin rule or custom header mismatch | Compare stack resources; redeploy the stack to synchronize the NoEcho parameter |
| One task or AZ fails | ECS replaces task; ALB routes only to healthy targets | Wait for replacement; increase desired count to two for real high availability |
| AWS regional incident | CloudWatch/Health event and regional unavailability | Local demonstrator has no multi-region failover; deploy a second controlled stack if required |
| Ingestion message repeatedly fails | Lambda error alarm and visible-DLQ alarm | Inspect metadata-only Lambda logs; correct the synthetic object; redrive only after validating the fix |

## Backup and state

The deployed runtime intentionally has no durable customer or workflow state; all records
are synthetic fixtures inside the immutable image. ECS task replacement therefore needs no
data restore. A future PostgreSQL adapter requires encrypted backups, point-in-time
recovery, migration rollback, tenant-isolation tests, and restore exercises before the
recovery claim can expand.

## Bedrock option

`-EnableBedrock true` switches synthesis from the deterministic path to Bedrock Converse
using `us.amazon.nova-2-lite-v1:0`. From Canada Central, that geographic profile may route
requests through Canada and U.S. regions. It is disabled by default; even synthetic use
should record the model/profile, region-routing choice, evaluation, token costs, and
fallback rate. The adapter fails safely to the deterministic grounded response.

A controlled three-case Bedrock execution is recorded in
[the evaluation report](BEDROCK_EVALUATION.md): 100% workflow-quality checks, three
successful model requests, 804 total tokens, 1.485-second mean latency, and an estimated
US$0.0005602 model cost. One response used the safe deterministic fallback.

## Cost envelope

For one continuously running 0.25-vCPU/0.5-GB Linux/x86 Fargate task in Canada Central at
low traffic, budget approximately **US$45–60 per month**, before taxes and Bedrock. This is
an engineering estimate, not a quote:

| Component | Low-traffic monthly estimate |
|---|---:|
| Fargate task | US$9–12 |
| Application Load Balancer and light LCU use | US$20–25 |
| Public IPv4 addresses | US$8–12 |
| CloudFront HTTPS/data | US$0–3 at portfolio traffic |
| CloudWatch logs, EMF, alarms, dashboard, Container Insights | US$2–6 |
| ECR and Secrets Manager | Under US$2 |
| S3/SQS/Lambda ingestion at portfolio volume | Near US$0–1 |
| **Expected total** | **US$45–60** |

Pricing varies by region, traffic, log volume, retention, and AWS pricing changes. Confirm
with the [AWS Pricing Calculator](https://calculator.aws/) and actual Cost Explorer after
24–48 hours. Fargate bills requested CPU and memory per second; ALB bills per hour plus
LCUs; public IPv4, CloudWatch, transfer, CloudFront, Secrets Manager, ECR, and Bedrock are
separate charges.

To stop recurring cost completely, explicitly run `scripts/destroy_aws.ps1` and approve
its PowerShell confirmation. It deletes both CloudFormation stacks, ECR images, logs, and
the runtime secret. This operation is irreversible.

# AWS decommission audit and approval plan

Status: **approved, completed, and independently verified**.

Audit date: 2026-09-08. Scope: AWS account `071239861872`, Canada Central
(`ca-central-1`), and only the PolicyFlow production deployment.

Decommission was verified complete by 2026-09-08 20:13 America/Toronto
(2026-09-09 00:13 UTC).

## Approval and preservation boundary

The repository owner explicitly approved this inventory and plan before deletion began.
The source repository, documentation, test evidence, GitHub Actions history, and deployment
artifacts remained outside the deletion scope and were preserved.

The final GitHub deployment load-test artifact was also downloaded before teardown to
[`docs/evidence/aws-deployment-cf08e521/load-test.json`](evidence/aws-deployment-cf08e521/load-test.json),
so it remains available after the Actions artifact expires on 2026-12-07.

## Charge-bearing inventory

| Area | Audited PolicyFlow resources |
|---|---|
| CloudFormation | `policyflow-agents-prod-service` (`UPDATE_COMPLETE`); `policyflow-agents-prod-ecr` (`CREATE_COMPLETE`) |
| ECS/Fargate | Cluster and service `policyflow-agents-prod`; one healthy public-IP Fargate task, task definition `policyflow-agents-prod:8`, ENI `eni-0cb77d4ef8b0d45d1` |
| ECR | Repository `policyflow-agents-prod`; 21 image/manifest records using 1,446,702,855 bytes |
| ALB | `policyflow-agents-prod`; ALB ARN suffix `app/policyflow-agents-prod/65fa9eb2f7f13a7a`; target group suffix `policy-Targe-3O4Z00KZZHAN/7f82ac87733555be` |
| Public IPv4 | ALB addresses `52.60.155.0` and `15.223.21.89`; Fargate task address `35.183.30.121` |
| CloudFront | Distribution `E2FWQ4LX0SYIGW`, domain `d20g4ajd2f79hc.cloudfront.net`, plus its authorization function and three managed policies |
| S3 | Versioned bucket `policyflow-agents-prod-ingestion-071239861872-ca-central-1`; two current versions, 1,344 bytes total; zero noncurrent versions and zero delete markers |
| SQS | `policyflow-agents-prod-ingestion` and `policyflow-agents-prod-ingestion-dlq`; both empty at audit time |
| Lambda | Function `policyflow-agents-prod-ingestion` and event-source mapping `8edf40d8-442c-4cb7-9f54-1ad2289ff739` |
| Secrets Manager | `policyflow-agents/prod/runtime` |
| CloudWatch | Log groups `/ecs/policyflow-agents-prod` and `/aws/lambda/policyflow-agents-prod-ingestion`; five alarms; dashboard `policyflow-agents-prod`; metric filter `policyflow-agents-prod-errors`; PolicyFlow custom-metric history |
| VPC | VPC `vpc-0b75a05979127dc32`; subnets `subnet-0cd2441747cd83458` and `subnet-08fcbe5101f5414b2`; route table `rtb-02a2a0f18ebfc82cb`; internet gateway `igw-0d41ba46092ee3556`; security groups `sg-0ad4fd38066656f7b` and `sg-091292f84f25410e8`; no NAT gateways or VPC endpoints |
| Bedrock | Disabled in the live stack; the task role has no Bedrock permission; no PolicyFlow provisioned throughput, custom model, agent, or knowledge base. Historical controlled evaluation cost was approximately US$0.0005602 |

The two exact S3 version IDs observed were
`CnxKj20bJBD58y0Hz5ITqThFQBlIz_NM` and
`GAHcy.WnTw6WrpBqZhf0AM4W4w1h4fNs`.

The current S3 keys were
`incoming/ingestion_sample-cc4908e4ba49499194fc7b61fd4abde4.json` (614 bytes) and
`processed/ingestion_sample-cc4908e4ba49499194fc7b61fd4abde4.manifest.json` (730 bytes).
There were no older versions hidden behind either current version.

The CloudFront policy IDs were `68871dff-6686-4522-b522-e4d6778497f0` (cache),
`a197687c-4d8b-452b-bdc6-f369814494b3` (origin request), and
`d632417d-30db-4183-b1e9-34952d1afcd3` (response headers). The function ARN was
`arn:aws:cloudfront::071239861872:function/policyflow-agents-prod-authorization`.

The exact queue URLs were
`https://sqs.ca-central-1.amazonaws.com/071239861872/policyflow-agents-prod-ingestion`
and
`https://sqs.ca-central-1.amazonaws.com/071239861872/policyflow-agents-prod-ingestion-dlq`.

The five alarms, all `OK` at audit time, were:

- `policyflow-agents-prod-service-HighCpuAlarm-X87ecv9VUz6X`
- `policyflow-agents-prod-service-IngestionDlqAlarm-gUr1yAABxF5A`
- `policyflow-agents-prod-service-IngestionErrorAlarm-de7vAjQQSXrN`
- `policyflow-agents-prod-service-TargetFiveXxAlarm-PtdNpnRYd6Wq`
- `policyflow-agents-prod-service-UnhealthyTargetAlarm-IRbrZHpdwGps`

The nine recently active `PolicyFlow` custom metric series were `ApplicationErrors`
(no dimensions), plus `Latency` and `RequestCount` for each of these dimension pairs:
`Route=/health/live, StatusCode=200`, `Route=/health/ready, StatusCode=200`,
`Route=<unmatched>, StatusCode=200`, and `Route=<unmatched>, StatusCode=401`.
ECS Container Insights was also enabled on the cluster. Metric history cannot be manually
deleted; removing the task, metric filter, log groups, and cluster stops new publication.

### ECR image and manifest inventory

The repository contained these 21 digest records. A dash means the record was untagged.

| Tag | Digest | Size (bytes) |
|---|---|---:|
| — | `sha256:a69d498d90542490e9719f6a53d23b5af54a947e4263bd62e63afc85fa6157cf` | 1,599 |
| — | `sha256:6eefa23e3536004dae7dec8284167ca2b2e6c3fd2739e79742e02c715a02d77b` | 91,952,312 |
| — | `sha256:9bbd6395198bef46b42f6aadfade5bbddd10d4fea0eb5274c04334ae0567a454` | 1,599 |
| `b8c5ce12ace4` | `sha256:6f1b41cb43f302eae9b1eaadf5369822105cf9e345042dc7f6aac1fe762ad2a4` | 91,952,312 |
| — | `sha256:9bace55defd36252aaefdc7ced7c7f81e4a71a5069b33baf0647bcb53d25651e` | 1,599 |
| — | `sha256:79a34bb2ee0bd65e41f499be6ac59455a308cab38749bb2415b543ca44653d44` | 91,952,312 |
| `efad36672906` | `sha256:5d654dd00c208274206e4e3932f4a8f1fc5a949fd173f12f3e18ce648678d4ab` | 91,952,312 |
| — | `sha256:17c240ac7e2aafe4f82b483368ad91249ae00b4520b01db39da10c9424f17b09` | 91,955,516 |
| — | `sha256:a65c12a9a8d6d1e985d475c9377daf5c5e705f7ed78a0a252ffc65752493c190` | 1,599 |
| `98f868a8aa17` | `sha256:fd3b997675b4eaf6b4828b7977fd6b865b5d797fd1bbbd2ff53ce0b27fb26e48` | 91,955,516 |
| `6babb38062fc6424d286c9bcb8ad98feaa2aa637` | `sha256:5d8e5992c813729ed0fcc8df77f2d3b1d901ff3511b72b3010ae3f70bffdd84a` | 91,904,730 |
| `ad7588f0538f4b8ebd2734acd67f611fedbb844e` | `sha256:566959bc15628dae5fd821918f2d8190aa4381bdf0c18a6817646f0cdf84675a` | 91,905,064 |
| `security-efa3434` | `sha256:6f5af3112d726529bc8f45febf2116adb3261baf729247c66d05fcda40faac0a` | 92,722,001 |
| `security-4e28852` | `sha256:a795c6785a6e22c697aeb42fd482b4e2341e85d8b3394484ca08b0c90ab06945` | 67,758,754 |
| `4e28852745de4e5aee930c6a81d17ecc4d385224` | `sha256:2113dc033e9ef3c354a4a2df5a954fb1864e6d8b83c75a2597c7025876d453ea` | 67,710,328 |
| `f9596f3e4ead` | `sha256:79ec938fb2d255327522533219ad5d924b59f321e32a3731312ce36399fed147` | 80,505,360 |
| `862a0f323cca` | `sha256:61450c683bb66894ebace2e54e784c28e5649bad534640bd615e2ad96f719bce` | 80,505,360 |
| `090f1c51b704` | `sha256:a97214ebd07e06580c2007ffe054135b621714f8fb4f865a2115d079d38349f0` | 80,505,360 |
| `cf08e521ef9d` | `sha256:217f6477be48169eb38e318dcbbdfb2464516e68300a30b61816a26760041ca3` | 80,505,360 |
| `cf08e521ef9d5d842b35c8d6b6b0402ea9a0dc4e` | `sha256:9e922a9f3de7329477f14290640dab5bb591f09796592a639a19965d4d630fcf` | 80,448,502 |
| `0241aa874fed` | `sha256:a1f20fb9a903772e2aed57f8440375b2f010c4625f3ec50a6353459d147e8b2b` | 80,505,360 |

## GitHub OIDC decision

The account-level provider is
`arn:aws:iam::071239861872:oidc-provider/token.actions.githubusercontent.com`. A complete
IAM role trust-policy scan found only
`policyflow-agents-prod-service-GitHubDeployRole-8VCpicaliACQ`, scoped to the PolicyFlow
repository and `aws-production` environment. No GridTwin-Ops or other role currently trusts
the provider. It will nevertheless be retained because doing so has no material recurring
cost and prevents accidental damage if another project begins sharing it.

## Approved and executed sequence

1. Commit and push the preparation changes. The AWS deployment workflow becomes manual-only;
   the ordinary `CI` workflow remains enabled for pushes and pull requests.
2. Confirm the preparation commit's ordinary CI run is successful and confirm no deployment
   workflow is queued or running.
3. Run `scripts/destroy_aws.ps1` from an authenticated session. The script refuses any account
   except `071239861872`, any region except `ca-central-1`, and any unexpected stack or bucket.
4. Install the stack-level retain policy for the GitHub OIDC provider.
5. Permanently delete every version and delete marker from the exact ingestion bucket, then
   verify its version inventory is zero.
6. Delete `policyflow-agents-prod-service` and wait for completion. If deletion fails, print
   the `DELETE_FAILED` resources and stop without touching the ECR stack.
7. Delete `policyflow-agents-prod-ecr` and wait for completion. Its `EmptyOnDelete` policy
   removes every image and manifest.
8. Run an independent read-only audit of every category in the inventory, including ENIs and
   public IP associations. Historical CloudWatch metric datapoints can remain visible until
   they age out, but no PolicyFlow metric publisher or billable infrastructure may remain.
9. Only after verification, update the README and deployment-evidence document to record the
   decommission date and state that the former live URL is intentionally unavailable.

Do not use forced stack deletion as the first response to a failure. Diagnose the resource,
remove only the exact blocker, retry standard deletion, and record the result.

## Post-delete verification

The independent service-by-service audit found:

- Both exact CloudFormation stacks absent.
- ECS cluster and service retained only as `INACTIVE` history with zero active services,
  zero desired tasks, zero running tasks, and zero pending tasks. The former task is
  `STOPPED`; its attachment is `DELETED`. Task definitions `:3` and `:8` remain active as
  nonbillable deployment metadata and do not reference a runnable image because ECR is gone.
- No PolicyFlow load balancer, target group, ECR repository or image, VPC, subnet, ENI,
  public address, NAT gateway, or VPC endpoint.
- No CloudFront distribution, function, cache policy, origin-request policy, or
  response-headers policy. The former hostname no longer resolves.
- No ingestion S3 bucket, Lambda function or event mapping, SQS queue, runtime secret,
  application/Lambda log group, alarm, or dashboard.
- No PolicyFlow provisioned Bedrock throughput or custom model.
- Historical `PolicyFlow` metric series remain discoverable in CloudWatch, but the ECS task,
  log metric filter, log groups, and all publishers are gone, so no new datapoints can be
  emitted. The Resource Groups Tagging API also temporarily returns stale ECS metadata;
  direct ECS calls are authoritative and show it inactive/stopped with no billable capacity.
- The GitHub OIDC provider remains. Its PolicyFlow IAM deployment role is absent.

The teardown first installed OIDC retention and emptied both S3 versions. Two null-handling
defects in the defensive S3 checks caused safe stops before `delete-stack`; each was fixed,
committed, validated, and pushed before retrying. CloudFormation then deleted the service
stack and ECR stack successfully using standard deletion; no `DELETE_FAILED` state occurred.

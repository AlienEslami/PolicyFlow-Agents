# Verified Amazon Bedrock evaluation

On 2026-09-08, PolicyFlow executed three frozen synthetic cases through Amazon Nova 2
Lite using the `us.amazon.nova-2-lite-v1:0` cross-region inference profile from
`ca-central-1`. This was a controlled evaluation from the authenticated development
environment. Bedrock was disabled in the then-running ECS stack, which was subsequently
decommissioned on 2026-09-08 after the deployment evidence was preserved.

| Measure | Result |
|---|---:|
| Quality checks passed | 3 / 3 (100%) |
| Successful Bedrock requests | 3 / 3 |
| Mean model latency | 1,484.966 ms |
| p95 model latency (small-sample order statistic) | 2,474.816 ms |
| Input / output tokens | 659 / 145 |
| Total tokens | 804 |
| Safe deterministic fallback | 1 / 3 (33.33%) |
| Estimated model cost | US$0.0005602 |

The gate checked expected workflow state and reason code, evidence citations, and absence
of prohibited autonomous-approval language. One incomplete-document response failed the
strict model-output contract and safely fell back to the grounded deterministic synthesis;
the workflow still produced the expected `needs_information` result. This fallback is a
useful reliability finding rather than a quality miss.

Cost uses a captured assumption of US$0.30 per million input tokens and US$2.50 per
million output tokens, excluding discounts and free tier. The detailed, non-secret report
including Bedrock request IDs is tracked in
[`docs/evidence/bedrock-evaluation-2026-09-08.json`](evidence/bedrock-evaluation-2026-09-08.json).

Reproduce with an AWS identity permitted to invoke the named inference profile:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_bedrock.py `
  --region ca-central-1 `
  --model-id us.amazon.nova-2-lite-v1:0 `
  --max-cases 3
```

The evaluator is intentionally bounded to 12 synthetic cases and exits nonzero if no
Bedrock request succeeds or any quality check fails.

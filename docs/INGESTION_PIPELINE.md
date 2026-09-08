# Synthetic document ingestion pipeline

The optional ingestion path demonstrates a small event-driven data pipeline without
adding another continuously running service. Uploading a JSON object under `incoming/`
in the stack-managed S3 bucket sends an event to SQS and invokes a Lambda consumer whose
event-source concurrency is capped at two.

The consumer validates a one-megabyte/50-document envelope, requires document and tenant
identifiers, chunks text at 800 characters with 100-character overlap, assigns
content-addressed chunk IDs, and writes a manifest under `processed/`. Content matching
prompt-injection markers is tagged `quarantined` rather than made retrievable. It logs
only object metadata and counts, not document text.

Security and recovery controls include:

- S3 public access blocking, SSE-S3 encryption, versioning, and short lifecycle rules.
- SSE-SQS, a resource policy limited to the exact bucket/account, batch size one, and a
  dead-letter queue after three receives.
- A Lambda role limited to consuming the one queue, reading `incoming/*`, writing
  `processed/*`, and its one log group.
- Event-source maximum concurrency two, partial-batch failure reporting, 14-day logs,
  and alarms for Lambda errors and visible DLQ messages.
- Explicit acknowledgement of S3's notification-configuration `s3:TestEvent`, whose
  envelope intentionally differs from normal object-created events.

Run the live synthetic proof after deploying the CloudFormation stack:

```powershell
.\scripts\submit_ingestion.ps1
```

The script uploads [`data/synthetic/ingestion_sample.json`](../data/synthetic/ingestion_sample.json),
waits for the corresponding manifest, and downloads non-secret evidence to the ignored
`artifacts/` directory. The sample deliberately includes one safe document and one
prompt-injection-shaped document to verify quarantine tagging.

This is an architectural ingestion proof, not a production vector indexing system. A
production expansion would add schema evolution, malware scanning, PII classification,
embedding versioning, idempotency storage, reprocessing controls, and a tenant-filtered
vector store.

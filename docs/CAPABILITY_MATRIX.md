# Enterprise agent capability matrix

| Capability | Concrete repository evidence | Honest boundary |
|---|---|---|
| Agent and multi-agent orchestration | Nine-node LangGraph with six role-separated agent responsibilities | Deterministic local workflow, not a deployed enterprise agent platform |
| Reasoning and planning | Supervisor emits an inspectable bounded plan | Plan is policy-constrained, not open-ended autonomous reasoning |
| RAG, vector search, embeddings | ACL-first hybrid retriever, embedding port, pgvector/FTS SQL, HNSW and GIN indexes | CI uses a declared hash-vector test double |
| Enterprise API/tool integration | Typed claims/policy/document tools and a case-management dispatch adapter | Backing systems are synthetic JSON and in-memory state |
| Memory | Redacted tenant/user/case scope with TTL and SQL target table | Local memory is not durable |
| Evaluation and analytics | Frozen bilingual/adversarial suite with metrics plus an optional local LLM-as-a-Judge adapter | CI metrics come from the declared deterministic judge unless the model run is separately recorded |
| Responsible AI and governance | No autonomous adjudication, protected-attribute block, human approval, audit chain | Formal organization approval is outside the project |
| Security and privacy | Least-data projection, tenant checks/RLS, quarantined content, hardened container | Demo headers are not production authentication |
| Reliability and SRE | Bounded graph, fail-closed reads, idempotency, health, metrics, PDB/HPA/probes | No live SLO history, incident response, or disaster-recovery evidence |
| Cloud-native and CI/CD | Docker, Compose, GitHub Actions, AKS workload and Key Vault CSI patterns | Reference manifests have not been applied to Azure |
| Python and SQL | Typed Python service/tests and PostgreSQL migration/hybrid query | No production database workload is claimed |
| Financial-services context | Synthetic insurance service routing with claim-decision boundaries | No insurer data, domain approval, or production experience is implied |
| English/French support | `en-CA` / `fr-CA` contracts, knowledge, responses, and evaluation cases | Product-quality translation requires bilingual domain review |

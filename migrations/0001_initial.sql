CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE knowledge_documents (
    id text PRIMARY KEY,
    document_id text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    tenant_id text NOT NULL,
    title text NOT NULL,
    classification integer NOT NULL CHECK (classification BETWEEN 0 AND 2),
    locale text NOT NULL CHECK (locale IN ('en-CA', 'fr-CA', 'bilingual')),
    lifecycle text NOT NULL CHECK (lifecycle IN ('approved', 'quarantined', 'retired')),
    injection_flag boolean NOT NULL DEFAULT false,
    content_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, document_id, version)
);

CREATE TABLE knowledge_chunks (
    id text PRIMARY KEY,
    document_row_id text NOT NULL REFERENCES knowledge_documents(id) ON DELETE RESTRICT,
    document_id text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal > 0),
    content text NOT NULL,
    content_sha256 char(64) NOT NULL,
    embedding vector(384) NOT NULL,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(content, ''))
    ) STORED,
    UNIQUE (document_row_id, ordinal)
);

CREATE INDEX ix_policyflow_chunks_vector ON knowledge_chunks
USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ix_policyflow_chunks_text ON knowledge_chunks USING gin (search_vector);
CREATE INDEX ix_policyflow_documents_acl ON knowledge_documents
(tenant_id, classification, lifecycle, locale);

CREATE TABLE workflow_runs (
    id uuid PRIMARY KEY,
    tenant_id text NOT NULL,
    case_id text NOT NULL,
    requested_by text NOT NULL,
    objective_sha256 char(64) NOT NULL,
    status text NOT NULL CHECK (
        status IN ('needs_information', 'pending_approval', 'refused', 'failed')
    ),
    reason_code text,
    graph_version text NOT NULL,
    model_backend text NOT NULL,
    model_name text NOT NULL,
    retrieval_digest char(64),
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tool_events (
    id bigserial PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES workflow_runs(id) ON DELETE RESTRICT,
    tenant_id text NOT NULL,
    sequence integer NOT NULL CHECK (sequence > 0),
    tool_name text NOT NULL,
    arguments_sha256 char(64) NOT NULL,
    outcome text NOT NULL CHECK (outcome IN ('success', 'failure', 'denied')),
    result_sha256 char(64),
    duration_ms double precision NOT NULL,
    UNIQUE (run_id, sequence)
);

CREATE TABLE risk_findings (
    id bigserial PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES workflow_runs(id) ON DELETE RESTRICT,
    tenant_id text NOT NULL,
    code text NOT NULL,
    severity text NOT NULL,
    blocking boolean NOT NULL,
    detail text NOT NULL
);

CREATE TABLE action_outbox (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL UNIQUE REFERENCES workflow_runs(id) ON DELETE RESTRICT,
    tenant_id text NOT NULL,
    action_kind text NOT NULL,
    state text NOT NULL CHECK (
        state IN ('pending_human_approval', 'approved', 'rejected', 'dispatched')
    ),
    payload jsonb NOT NULL,
    idempotency_key char(64) NOT NULL UNIQUE,
    downstream_reference text,
    created_at timestamptz NOT NULL DEFAULT now(),
    dispatched_at timestamptz
);

CREATE TABLE approvals (
    id uuid PRIMARY KEY,
    action_id uuid NOT NULL UNIQUE REFERENCES action_outbox(id) ON DELETE RESTRICT,
    tenant_id text NOT NULL,
    decision text NOT NULL CHECK (decision IN ('approve', 'reject')),
    decided_by text NOT NULL,
    note text,
    action_digest char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE agent_memory (
    id bigserial PRIMARY KEY,
    tenant_id text NOT NULL,
    subject_id text NOT NULL,
    case_id text NOT NULL,
    redacted_content text NOT NULL,
    content_sha256 char(64) NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (expires_at > created_at)
);
CREATE INDEX ix_policyflow_memory_scope ON agent_memory
(tenant_id, subject_id, case_id, expires_at);

CREATE TABLE audit_events (
    id bigserial PRIMARY KEY,
    run_id uuid NOT NULL,
    tenant_id text NOT NULL,
    sequence integer NOT NULL CHECK (sequence > 0),
    event_type text NOT NULL,
    actor text NOT NULL,
    payload jsonb NOT NULL,
    previous_hash char(64) NOT NULL,
    event_hash char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, sequence),
    UNIQUE (run_id, event_hash)
);

ALTER TABLE knowledge_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE action_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_documents ON knowledge_documents
USING (tenant_id IN (current_setting('app.tenant_id', true), 'SHARED'));
CREATE POLICY tenant_runs ON workflow_runs
USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_tools ON tool_events
USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_risk ON risk_findings
USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_actions ON action_outbox
USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_approvals ON approvals
USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_memory ON agent_memory
USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_audit ON audit_events
USING (tenant_id = current_setting('app.tenant_id', true));

CREATE OR REPLACE FUNCTION policyflow_forbid_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'immutable table: %', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER policyflow_approvals_immutable
BEFORE UPDATE OR DELETE ON approvals
FOR EACH ROW EXECUTE FUNCTION policyflow_forbid_mutation();

CREATE TRIGGER policyflow_audit_immutable
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION policyflow_forbid_mutation();


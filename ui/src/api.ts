export type Role = 'operator' | 'approver' | 'auditor' | 'service' | 'admin'

export interface Session {
  token: string
  subject: string
  tenantId: string
}

export interface PlanStep {
  sequence: number
  agent: string
  operation: string
  rationale: string
}

export interface ToolResult {
  name: string
  ok: boolean
  data: Record<string, unknown>
  error_code: string | null
}

export interface Evidence {
  chunk_id: string
  document_id: string
  title: string
  text: string
  score: number
  classification: number
}

export interface RiskFinding {
  code: string
  severity: string
  detail: string
  blocking: boolean
}

export interface ActionProposal {
  action_id: string
  kind: string
  state: 'pending_human_approval' | 'approved' | 'rejected' | 'dispatched'
  payload: Record<string, unknown>
  idempotency_key: string
}

export interface RunResponse {
  run_id: string
  case_id: string
  requested_by: string
  status: 'needs_information' | 'pending_approval' | 'refused' | 'failed'
  reason_code: string | null
  summary: string
  plan: PlanStep[]
  tool_trace: ToolResult[]
  evidence: Evidence[]
  citations: Array<{ chunk_id: string; document_id: string; title: string }>
  risk_findings: RiskFinding[]
  action: ActionProposal | null
  model_backend: string
  model_name: string
  model_latency_ms: number
  model_fallback: boolean
  model_input_tokens: number
  model_output_tokens: number
  model_request_id: string | null
  created_at: string
}

export interface AuditEvent {
  sequence: number
  event_type: string
  actor: string
  payload: Record<string, unknown>
  previous_hash: string
  event_hash: string
  created_at: string
}

export interface TimelineResponse {
  run_id: string
  chain_valid: boolean
  events: AuditEvent[]
}

export function buildHeaders(
  session: Session,
  role: Role = 'operator',
  subject = session.subject,
): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Subject': subject,
    'X-Role': role,
    'X-Tenant-ID': session.tenantId,
    'X-Correlation-ID': crypto.randomUUID(),
  }
  if (session.token.trim()) {
    headers.Authorization = `Bearer ${session.token.trim()}`
  }
  return headers
}

async function request<T>(
  path: string,
  session: Session,
  init: RequestInit = {},
  role: Role = 'operator',
  subject?: string,
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { ...buildHeaders(session, role, subject), ...init.headers },
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      code?: string
      detail?: string
    }
    throw new Error(body.code ?? body.detail ?? `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

export function createRun(
  session: Session,
  input: { case_id: string; objective: string; locale: string; top_k: number },
): Promise<RunResponse> {
  return request('/api/v1/runs', session, { method: 'POST', body: JSON.stringify(input) })
}

export function getRun(session: Session, runId: string): Promise<RunResponse> {
  return request(`/api/v1/runs/${runId}`, session)
}

export function getTimeline(session: Session, runId: string): Promise<TimelineResponse> {
  return request(`/api/v1/runs/${runId}/timeline`, session)
}

export function decideRun(
  session: Session,
  runId: string,
  decision: 'approve' | 'reject',
): Promise<unknown> {
  return request(
    `/api/v1/runs/${runId}/decision`,
    session,
    { method: 'POST', body: JSON.stringify({ decision, note: 'Reviewed in operator UI.' }) },
    'approver',
    'senior-reviewer',
  )
}

export function dispatchRun(session: Session, runId: string): Promise<unknown> {
  return request(
    `/api/v1/runs/${runId}/dispatch`,
    session,
    { method: 'POST' },
    'service',
    'workflow-service',
  )
}

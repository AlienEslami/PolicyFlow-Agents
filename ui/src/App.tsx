import { useMemo, useState } from 'react'

import {
  createRun,
  decideRun,
  dispatchRun,
  getRun,
  getTimeline,
  type RunResponse,
  type Session,
  type TimelineResponse,
} from './api'

const scenarios = {
  'CLM-1001': 'Prepare this case for adjuster review using the intake policy.',
  'CLM-1002': 'Check completeness and prepare a human review brief.',
}

function humanize(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>
}

export function App() {
  const [token, setToken] = useState('')
  const [tenantId, setTenantId] = useState('NORTHSTAR_CA')
  const [subject, setSubject] = useState('case-worker')
  const [caseId, setCaseId] = useState<keyof typeof scenarios>('CLM-1001')
  const [objective, setObjective] = useState(scenarios['CLM-1001'])
  const [locale, setLocale] = useState('en-CA')
  const [run, setRun] = useState<RunResponse | null>(null)
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const session = useMemo<Session>(
    () => ({ token, tenantId: tenantId.trim(), subject: subject.trim() }),
    [token, tenantId, subject],
  )

  const refresh = async (runId: string) => {
    const [nextRun, nextTimeline] = await Promise.all([
      getRun(session, runId),
      getTimeline(session, runId),
    ])
    setRun(nextRun)
    setTimeline(nextTimeline)
  }

  const execute = async () => {
    setBusy(true)
    setError(null)
    try {
      const created = await createRun(session, {
        case_id: caseId,
        objective,
        locale,
        top_k: 4,
      })
      setRun(created)
      setTimeline(await getTimeline(session, created.run_id))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unexpected request failure')
    } finally {
      setBusy(false)
    }
  }

  const decide = async (decision: 'approve' | 'reject') => {
    if (!run) return
    setBusy(true)
    setError(null)
    try {
      await decideRun(session, run.run_id, decision)
      await refresh(run.run_id)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Decision failed')
    } finally {
      setBusy(false)
    }
  }

  const dispatch = async () => {
    if (!run) return
    setBusy(true)
    setError(null)
    try {
      await dispatchRun(session, run.run_id)
      await refresh(run.run_id)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Dispatch failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="/ui/" aria-label="PolicyFlow home">
          <span className="brand-mark">PF</span>
          <span>PolicyFlow</span>
        </a>
        <div className="environment"><span /> AWS · Canada Central</div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">Synthetic operations workspace</p>
          <h1>Governed agents.<br /><em>Human decisions.</em></h1>
          <p className="hero-copy">
            Inspect every retrieval, tool call and control before a reversible action
            reaches an independent reviewer.
          </p>
        </div>
        <div className="boundary-card">
          <span className="boundary-icon">!</span>
          <div>
            <strong>Demonstration boundary</strong>
            <p>Synthetic records only. No claim decision is automated or sent to a live insurer.</p>
          </div>
        </div>
      </section>

      <section className="control-grid">
        <div className="panel credentials">
          <div className="panel-heading"><span>01</span><h2>Connect</h2></div>
          <label>Runtime bearer token<input type="password" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Stored in memory only" autoComplete="off" /></label>
          <div className="field-row">
            <label>Tenant<input value={tenantId} onChange={(event) => setTenantId(event.target.value)} /></label>
            <label>Operator<input value={subject} onChange={(event) => setSubject(event.target.value)} /></label>
          </div>
          <p className="hint">The token is never persisted to browser storage.</p>
        </div>

        <div className="panel launch">
          <div className="panel-heading"><span>02</span><h2>Launch case review</h2></div>
          <div className="field-row">
            <label>Case<select value={caseId} onChange={(event) => { const id = event.target.value as keyof typeof scenarios; setCaseId(id); setObjective(scenarios[id]) }}><option value="CLM-1001">CLM-1001 · Complete</option><option value="CLM-1002">CLM-1002 · Missing document</option></select></label>
            <label>Locale<select value={locale} onChange={(event) => setLocale(event.target.value)}><option value="en-CA">English</option><option value="fr-CA">Français</option></select></label>
          </div>
          <label>Objective<textarea value={objective} onChange={(event) => setObjective(event.target.value)} rows={3} /></label>
          <button className="primary" onClick={execute} disabled={busy || !token.trim() || !objective.trim()}>{busy ? 'Working…' : 'Run governed workflow'}<span>→</span></button>
        </div>
      </section>

      {error && <div className="error" role="alert"><strong>Request stopped</strong><span>{humanize(error)}</span></div>}

      {!run ? (
        <section className="empty-state">
          <div className="pulse-ring"><span /></div>
          <h2>Ready for a synthetic case</h2>
          <p>Connect with the runtime token, then launch a workflow to see its complete control trail.</p>
        </section>
      ) : (
        <section className="results">
          <div className="result-header">
            <div><p className="eyebrow">Run {run.run_id.slice(0, 8)}</p><h2>{run.case_id}</h2></div>
            <div className={`status status-${run.status}`}>{humanize(run.status)}</div>
          </div>

          <div className="summary-grid">
            <article className="panel summary-card"><p className="section-label">Agent brief</p><blockquote>{run.summary}</blockquote><div className="model-line"><span>{run.model_backend}</span><span>{run.model_name}</span><span>{run.model_latency_ms.toFixed(1)} ms</span>{run.model_input_tokens > 0 && <span>{run.model_input_tokens + run.model_output_tokens} tokens</span>}{run.model_fallback && <span>safe fallback</span>}</div></article>
            <article className="panel decision-card"><p className="section-label">Human control</p>{run.action ? <><h3>{humanize(run.action.state)}</h3><p>A different authorized identity must decide before dispatch.</p><div className="button-row"><button className="approve" onClick={() => decide('approve')} disabled={busy || run.action.state !== 'pending_human_approval'}>Approve</button><button onClick={() => decide('reject')} disabled={busy || run.action.state !== 'pending_human_approval'}>Reject</button><button onClick={dispatch} disabled={busy || run.action.state !== 'approved'}>Dispatch</button></div></> : <><h3>No action staged</h3><p>{run.reason_code ? humanize(run.reason_code) : 'Controls stopped this workflow.'}</p></>}</article>
          </div>

          <div className="detail-grid">
            <article className="panel"><p className="section-label">Agent activity</p><ol className="agent-list">{run.plan.map((step) => <li key={step.sequence}><span>{String(step.sequence).padStart(2, '0')}</span><div><strong>{humanize(step.agent)}</strong><p>{step.rationale}</p></div><small>{humanize(step.operation)}</small></li>)}</ol></article>
            <article className="panel"><p className="section-label">Risk decisions</p><div className="risk-list">{run.risk_findings.length ? run.risk_findings.map((finding) => <div className={finding.blocking ? 'risk blocking' : 'risk'} key={finding.code}><span>{finding.blocking ? 'Blocked' : finding.severity}</span><div><strong>{humanize(finding.code)}</strong><p>{finding.detail}</p></div></div>) : <div className="risk clear"><span>Clear</span><div><strong>Controls passed</strong><p>No blocking risk finding was produced.</p></div></div>}</div></article>
          </div>

          <article className="panel evidence-panel"><p className="section-label">Retrieved evidence</p><div className="evidence-grid">{run.evidence.map((item) => <section key={item.chunk_id}><div className="evidence-meta"><span>{item.document_id}</span><span>{item.score.toFixed(3)}</span></div><h3>{item.title}</h3><p>{item.text}</p><small>Chunk {item.chunk_id}</small></section>)}</div></article>

          <div className="detail-grid">
            <article className="panel"><p className="section-label">Enterprise tool trace</p>{run.tool_trace.map((tool) => <details key={tool.name}><summary><span className={tool.ok ? 'dot-ok' : 'dot-fail'} />{humanize(tool.name)}<small>{tool.ok ? 'read completed' : tool.error_code}</small></summary><JsonBlock value={tool.data} /></details>)}</article>
            <article className="panel"><p className="section-label">Tamper-evident audit</p><div className="chain-status"><span className={timeline?.chain_valid ? 'dot-ok' : 'dot-fail'} />Hash chain {timeline?.chain_valid ? 'verified' : 'unverified'}</div><ol className="timeline">{timeline?.events.map((event) => <li key={event.sequence}><span>{event.sequence}</span><div><strong>{humanize(event.event_type)}</strong><p>{event.actor} · {new Date(event.created_at).toLocaleTimeString()}</p></div><code>{event.event_hash.slice(0, 10)}…</code></li>)}</ol></article>
          </div>
        </section>
      )}

      <footer><span>PolicyFlow Agents</span><span>React · FastAPI · LangGraph · ECS Fargate</span><a href="/docs">API docs ↗</a></footer>
    </main>
  )
}

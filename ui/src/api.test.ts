import { describe, expect, it, vi } from 'vitest'

import { buildHeaders, createRun, type Session } from './api'

const session: Session = {
  token: 'test-token',
  subject: 'case-worker',
  tenantId: 'NORTHSTAR_CA',
}

describe('PolicyFlow API client', () => {
  it('builds scoped headers without persisting credentials', () => {
    expect(buildHeaders(session, 'approver', 'reviewer')).toMatchObject({
      Authorization: 'Bearer test-token',
      'X-Subject': 'reviewer',
      'X-Role': 'approver',
      'X-Tenant-ID': 'NORTHSTAR_CA',
    })
    expect(buildHeaders({ ...session, token: ' ' })).not.toHaveProperty('Authorization')
  })

  it('surfaces API policy error codes', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: () => Promise.resolve({ code: 'tenant_scope_denied' }),
      }),
    )
    await expect(
      createRun(session, {
        case_id: 'CLM-OTHER',
        objective: 'Prepare a human review brief.',
        locale: 'en-CA',
        top_k: 4,
      }),
    ).rejects.toThrow('tenant_scope_denied')
    vi.unstubAllGlobals()
  })
})

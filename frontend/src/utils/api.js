const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  searchAddress: (q) =>
    request(`/address/search?q=${encodeURIComponent(q)}`),

  diagnose: (payload) =>
    request('/diagnose', { method: 'POST', body: JSON.stringify(payload) }),

  whatIf: (payload) =>
    request('/whatif', { method: 'POST', body: JSON.stringify(payload) }),

  compare: (payload) =>
    request('/compare', { method: 'POST', body: JSON.stringify(payload) }),

  query: (payload) =>
    request('/query', { method: 'POST', body: JSON.stringify(payload) }),

  matchCases: (payload) =>
    request('/cases/match', { method: 'POST', body: JSON.stringify(payload) }),

  lawChanges: (jurisdictionCode) => {
    const qs = jurisdictionCode
      ? `?jurisdiction_code=${encodeURIComponent(jurisdictionCode)}`
      : ''
    return request(`/law/changes${qs}`)
  },

  seedDemoChange: () =>
    request('/law/changes/seed_demo', { method: 'POST' }),

  requestReview: (payload) =>
    request('/review/request', { method: 'POST', body: JSON.stringify(payload) }),
}

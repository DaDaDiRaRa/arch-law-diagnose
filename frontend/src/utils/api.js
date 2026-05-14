const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail
    const msg =
      typeof detail === 'string'
        ? detail
        : detail?.message || `HTTP ${res.status}`
    const e = new Error(msg)
    e.detail = detail // 구조화된 에러 객체 보존
    e.status = res.status
    throw e
  }
  return res.json()
}

export const api = {
  searchAddress: (q) =>
    request(`/address/search?q=${encodeURIComponent(q)}`),

  fetchLandInfo: ({ pnu, address }) => {
    const qs = new URLSearchParams()
    if (pnu) qs.set('pnu', pnu)
    if (address) qs.set('address', address)
    return request(`/land_info?${qs.toString()}`)
  },

  diagnose: (payload) =>
    request('/diagnose', { method: 'POST', body: JSON.stringify(payload) }),

  diagnoseMulti: (payload) =>
    request('/diagnose/multi', { method: 'POST', body: JSON.stringify(payload) }),

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

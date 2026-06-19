const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',  // 브라우저 디스크 캐시 우회 — 빈 응답 캐싱 방지
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

  diagnoseWhatif: (payload) =>
    request('/diagnose/whatif', { method: 'POST', body: JSON.stringify(payload) }),

  feasibility: (payload) =>
    request('/feasibility/run', { method: 'POST', body: JSON.stringify(payload) }),

  // 진단 결과 → MD / xlsx 다운로드 — Response를 직접 받아 blob으로 처리
  downloadDiagnoseExport: async (format, payload) => {
    const res = await fetch(`${BASE}/diagnose/export/${format}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || `HTTP ${res.status}`)
    }
    const blob = await res.blob()
    // Content-Disposition에서 파일명 추출 (없으면 fallback)
    const cd = res.headers.get('Content-Disposition') || ''
    const m = cd.match(/filename="?([^"]+)"?/)
    const filename = m ? m[1] : `diagnose_export.${format}`
    // 브라우저 다운로드 트리거
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    return filename
  },

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

  eumLawInfo: ({ areaCd, zoneUse, zoneDistrict }) => {
    const qs = new URLSearchParams({ area_cd: areaCd })
    if (zoneUse) qs.set('zone_use', zoneUse)
    if (zoneDistrict) qs.set('zone_district', zoneDistrict)
    return request(`/eum/law_info?${qs.toString()}`)
  },

  eumNotices: ({ areaCd, days = 90, pageNo = 1 }) => {
    const qs = new URLSearchParams({
      area_cd: areaCd,
      days: String(days),
      page_no: String(pageNo),
    })
    return request(`/eum/notices?${qs.toString()}`)
  },

  eumDevPermits: ({ areaCd, days = 14 }) => {
    const qs = new URLSearchParams({
      area_cd: areaCd,
      days: String(days),
    })
    return request(`/eum/dev_permits?${qs.toString()}`)
  },
}

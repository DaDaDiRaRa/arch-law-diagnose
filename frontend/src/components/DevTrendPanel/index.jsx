import { useState } from 'react'
import { api } from '../../utils/api'

export default function DevTrendPanel({ areaCd }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [days, setDays] = useState(14)

  const canFetch = !!areaCd

  const fetchData = async (d = days) => {
    setLoading(true)
    setError(null)
    try {
      const r = await api.eumDevPermits({ areaCd, days: d })
      setData(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleToggle = async () => {
    if (data || error) {
      setOpen(!open)
      return
    }
    if (!canFetch) return
    await fetchData(days)
    setOpen(true)
  }

  const handleDaysChange = async (newDays) => {
    setDays(newDays)
    if (open) await fetchData(newDays)
  }

  if (!canFetch) return null

  return (
    <div style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)'}}>
      <button
        onClick={handleToggle}
        className="w-full px-4 py-3 flex items-center justify-between text-left transition-colors"
      >
        <span className="text-sm font-semibold" style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}}>
          주변 개발 인허가 동향 (토지이음)
        </span>
        <span className="text-xs" style={{color:'var(--mute)'}}>
          {loading ? '조회 중...' : open ? '▲ 접기' : '▼ 펼쳐보기'}
        </span>
      </button>

      {open && error && (
        <div className="px-4 py-3 text-xs" style={{borderTop:'1px solid var(--hairline)',color:'var(--error)'}}>
          조회 실패: {error}
        </div>
      )}

      {open && data && !error && (
        <div className="px-4 py-3 space-y-3" style={{borderTop:'1px solid var(--hairline)'}}>
          {data.warning && (
            <p className="text-xs px-2.5 py-1.5" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--warn)',backgroundColor:'var(--canvas-elevated)',color:'var(--warn-deep)'}}>
              {data.warning}
            </p>
          )}

          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="text-xs" style={{color:'var(--body)'}}>
              최근 <span className="font-semibold" style={{color:'var(--ink)'}}>{data.period?.days}일</span> ·
              총 <span className="font-bold" style={{color:'var(--ink)'}}>{data.total}건</span>
              {data.total > (data.items?.length || 0) && (
                <span className="ml-1" style={{color:'var(--mute)'}}>(상위 {data.items.length}건 표시)</span>
              )}
              {data.fetch_errors > 0 && (
                <span className="ml-2" style={{color:'var(--warn-deep)'}}>· 일부 일자 조회 실패 ({data.fetch_errors}건)</span>
              )}
            </div>
            <div className="flex items-center gap-1 text-xs">
              <span style={{color:'var(--mute)'}}>기간:</span>
              {[7, 14, 30].map((d) => (
                <button
                  key={d}
                  onClick={() => handleDaysChange(d)}
                  disabled={loading}
                  className="px-2 py-0.5 disabled:opacity-50 transition-colors"
                  style={days === d
                    ? {borderRadius:'var(--radius-sm)',backgroundColor:'var(--brand)',color:'#fff',border:'1px solid var(--brand)',fontFamily:'var(--font-sans)'}
                    : {borderRadius:'var(--radius-sm)',backgroundColor:'var(--canvas-elevated)',color:'var(--body)',border:'1px solid var(--hairline)',fontFamily:'var(--font-sans)'}}
                >
                  {d}일
                </button>
              ))}
            </div>
          </div>

          {(data.items || []).length === 0 ? (
            <p className="text-xs italic py-2" style={{color:'var(--mute)'}}>해당 기간 인허가 정보 없음</p>
          ) : (
            <div className="space-y-1.5 max-h-96 overflow-y-auto">
              {data.items.map((it, i) => <PermitRow key={i} permit={it} />)}
            </div>
          )}

          <p className="text-[10px] leading-relaxed pt-2" style={{color:'var(--faint)',borderTop:'1px solid var(--hairline-soft)',fontFamily:'var(--font-mono)'}}>
            출처: 토지이음 (eum.go.kr) · 개발 인허가 정보 조회 서비스.
            진단 지번과 동일 시군구의 최근 인허가 — 주변 개발 동향 참고용.
          </p>
        </div>
      )}
    </div>
  )
}

const FIELD_CANDIDATES = {
  title: ['prmsnNm', 'prmisnNm', 'sigunNm', 'busiNm', 'busiName', 'title'],
  permitType: ['prmsnTy', 'prmisnTy', 'devTy', 'kind', 'cateNm', 'category'],
  location: ['locplc', 'addr', 'address', 'jibun', 'rnAddr', 'location'],
  area: ['area', 'siteArea', 'prmsnAr', 'prmisnAr'],
  applicant: ['aplcntNm', 'aplct', 'reqstNm', 'requester'],
  prmsnDate: ['prmsnDe', 'prmisnDe', 'prmsnDt', 'permitDt'],
}

function pickField(obj, candidates) {
  for (const k of candidates) {
    const v = obj[k]
    if (v != null && String(v).trim() !== '') return v
  }
  return null
}

const KNOWN_KEYS = new Set([...Object.values(FIELD_CANDIDATES).flat(), '_permit_date'])

function PermitRow({ permit }) {
  const title = pickField(permit, FIELD_CANDIDATES.title)
  const permitType = pickField(permit, FIELD_CANDIDATES.permitType)
  const location = pickField(permit, FIELD_CANDIDATES.location)
  const area = pickField(permit, FIELD_CANDIDATES.area)
  const applicant = pickField(permit, FIELD_CANDIDATES.applicant)
  const prmsnDate = pickField(permit, FIELD_CANDIDATES.prmsnDate) || permit._permit_date

  const extraEntries = Object.entries(permit).filter(
    ([k, v]) => !KNOWN_KEYS.has(k) && v != null && String(v).trim() !== '',
  )

  const [expanded, setExpanded] = useState(false)
  const hasExtras = extraEntries.length > 0

  return (
    <div className="px-2.5 py-1.5 text-xs" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas-elevated)'}}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            {permitType && (
              <span className="text-[10px] px-1.5 py-0.5 font-medium" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--body)',fontFamily:'var(--font-mono)'}}>
                {permitType}
              </span>
            )}
            <span className="font-medium truncate" style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}} title={title || ''}>
              {title || '(제목 없음)'}
            </span>
          </div>
          {location && (
            <p className="text-[10px] mt-0.5 truncate" style={{color:'var(--mute)'}} title={location}>
              {location}
            </p>
          )}
          <div className="flex items-center gap-2 mt-0.5 text-[10px] flex-wrap" style={{color:'var(--faint)',fontFamily:'var(--font-mono)'}}>
            {area && <span>면적 {area}㎡</span>}
            {applicant && <span>· 신청 {applicant}</span>}
          </div>
        </div>
        <span className="text-[10px] flex-shrink-0" style={{color:'var(--mute)',fontFamily:'var(--font-mono)'}}>
          {formatYmd(prmsnDate)}
        </span>
      </div>
      {hasExtras && (
        <button onClick={() => setExpanded((v) => !v)} className="text-[10px] hover:underline mt-1" style={{color:'var(--link)'}}>
          {expanded ? '상세 접기' : `상세 ${extraEntries.length}개 ▾`}
        </button>
      )}
      {expanded && hasExtras && (
        <dl className="mt-1 grid grid-cols-2 gap-x-2 gap-y-0.5 text-[10px] pt-1" style={{borderTop:'1px solid var(--hairline-soft)'}}>
          {extraEntries.map(([k, v]) => (
            <div key={k} className="flex gap-1 min-w-0">
              <dt style={{fontFamily:'var(--font-mono)',color:'var(--faint)',flexShrink:0}}>{k}:</dt>
              <dd className="truncate" style={{color:'var(--body)'}} title={String(v)}>{String(v)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}

function formatYmd(ymd) {
  if (!ymd) return ''
  const s = String(ymd).replace(/\D/g, '')
  if (s.length >= 8) return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
  return String(ymd)
}

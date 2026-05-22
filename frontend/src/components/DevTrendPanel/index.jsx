import { useState } from 'react'
import { api } from '../../utils/api'

/**
 * 주변 개발 인허가 동향 — Phase 3.
 *
 * 토지이음 sDevList API (단일 일자만 지원)를 백엔드에서 최근 N일 병렬 집계.
 * 사용자 클릭 시 lazy fetch.
 *
 * EUM 응답 필드명은 API 스펙 변경 가능 — 알려진 후보 키들을 순회해서
 * 첫 매칭값 표시. 모르는 필드는 details 안에 raw key/value 로 노출.
 */
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
    <div className="rounded-xl border border-emerald-200 bg-emerald-50/40">
      <button
        onClick={handleToggle}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-emerald-100/40 transition-colors"
      >
        <span className="text-sm font-semibold text-emerald-900">
          🏗 주변 개발 인허가 동향 (토지이음)
        </span>
        <span className="text-xs text-emerald-700">
          {loading ? '⟳ 조회 중...' : open ? '▲ 접기' : '▼ 펼쳐보기'}
        </span>
      </button>

      {open && error && (
        <div className="px-4 py-3 border-t border-emerald-200 text-xs text-red-600">
          조회 실패: {error}
        </div>
      )}

      {open && data && !error && (
        <div className="px-4 py-3 border-t border-emerald-200 space-y-3">
          {data.warning && (
            <p className="text-xs text-amber-700 bg-amber-50 px-2.5 py-1.5 rounded">
              ⚠ {data.warning}
            </p>
          )}

          {/* 기간 선택 + 요약 */}
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="text-xs text-emerald-800">
              최근 <span className="font-semibold">{data.period?.days}일</span> ·
              총 <span className="font-bold text-emerald-900">{data.total}건</span>
              {data.total > (data.items?.length || 0) && (
                <span className="text-emerald-600 ml-1">
                  (상위 {data.items.length}건 표시)
                </span>
              )}
              {data.fetch_errors > 0 && (
                <span className="text-amber-600 ml-2">
                  · 일부 일자 조회 실패 ({data.fetch_errors}건)
                </span>
              )}
            </div>
            <div className="flex items-center gap-1 text-[var(--font-size-xs)]">
              <span className="text-gray-500">기간:</span>
              {[7, 14, 30].map((d) => (
                <button
                  key={d}
                  onClick={() => handleDaysChange(d)}
                  disabled={loading}
                  className={`px-2 py-0.5 rounded border ${
                    days === d
                      ? 'bg-emerald-600 text-white border-emerald-600'
                      : 'bg-white text-emerald-700 border-emerald-300 hover:bg-emerald-50'
                  } disabled:opacity-50`}
                >
                  {d}일
                </button>
              ))}
            </div>
          </div>

          {/* 인허가 목록 */}
          {(data.items || []).length === 0 ? (
            <p className="text-xs text-gray-500 italic py-2">
              해당 기간 인허가 정보 없음
            </p>
          ) : (
            <div className="space-y-1.5 max-h-96 overflow-y-auto">
              {data.items.map((it, i) => (
                <PermitRow key={i} permit={it} />
              ))}
            </div>
          )}

          <p className="text-[var(--font-size-2xs)] text-emerald-700 leading-relaxed border-t border-emerald-100 pt-2">
            출처: 토지이음 (eum.go.kr) · 개발 인허가 정보 조회 서비스.
            진단 지번과 동일 시군구의 최근 인허가 — 주변 개발 동향 참고용.
          </p>
        </div>
      )}
    </div>
  )
}

/** 알려진 필드 후보 — EUM API 키 변동 대비. 첫 매칭값 사용. */
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

const KNOWN_KEYS = new Set([
  ...Object.values(FIELD_CANDIDATES).flat(),
  '_permit_date',
])

function PermitRow({ permit }) {
  const title = pickField(permit, FIELD_CANDIDATES.title)
  const permitType = pickField(permit, FIELD_CANDIDATES.permitType)
  const location = pickField(permit, FIELD_CANDIDATES.location)
  const area = pickField(permit, FIELD_CANDIDATES.area)
  const applicant = pickField(permit, FIELD_CANDIDATES.applicant)
  const prmsnDate = pickField(permit, FIELD_CANDIDATES.prmsnDate) || permit._permit_date

  // 알려지지 않은 필드들 — details 펼침에 노출
  const extraEntries = Object.entries(permit).filter(
    ([k, v]) => !KNOWN_KEYS.has(k) && v != null && String(v).trim() !== '',
  )

  const [expanded, setExpanded] = useState(false)
  const hasExtras = extraEntries.length > 0

  return (
    <div className="bg-white rounded border border-emerald-100 px-2.5 py-1.5 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            {permitType && (
              <span className="text-[var(--font-size-2xs)] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-medium">
                {permitType}
              </span>
            )}
            <span className="font-medium text-gray-900 truncate" title={title || ''}>
              {title || '(제목 없음)'}
            </span>
          </div>
          {location && (
            <p className="text-[var(--font-size-xs)] text-gray-600 mt-0.5 truncate" title={location}>
              📍 {location}
            </p>
          )}
          <div className="flex items-center gap-2 mt-0.5 text-[var(--font-size-2xs)] text-gray-500 flex-wrap">
            {area && <span>면적 {area}㎡</span>}
            {applicant && <span>· 신청 {applicant}</span>}
          </div>
        </div>
        <span className="text-[var(--font-size-2xs)] text-gray-500 flex-shrink-0">
          {formatYmd(prmsnDate)}
        </span>
      </div>
      {hasExtras && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-[var(--font-size-2xs)] text-emerald-600 hover:underline mt-1"
        >
          {expanded ? '상세 접기' : `상세 ${extraEntries.length}개 ▾`}
        </button>
      )}
      {expanded && hasExtras && (
        <dl className="mt-1 grid grid-cols-2 gap-x-2 gap-y-0.5 text-[var(--font-size-2xs)] text-gray-500 border-t border-emerald-50 pt-1">
          {extraEntries.map(([k, v]) => (
            <div key={k} className="flex gap-1 min-w-0">
              <dt className="font-mono text-gray-400 flex-shrink-0">{k}:</dt>
              <dd className="truncate text-gray-700" title={String(v)}>{String(v)}</dd>
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

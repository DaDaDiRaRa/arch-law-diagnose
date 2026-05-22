import { useEffect, useState } from 'react'
import { api } from '../../utils/api'

const RESULT_BADGE = {
  approved: { label: '승인',   cls: 'bg-green-100 text-green-700' },
  rejected: { label: '반려',   cls: 'bg-red-100 text-red-700' },
  pending:  { label: '진행 중', cls: 'bg-yellow-100 text-yellow-700' },
}

export default function CaseReference({ buildingUse, zoneUse, siteArea, jurisdiction }) {
  const [state, setState] = useState({ loading: true, data: null, error: null })

  useEffect(() => {
    let alive = true
    if (!buildingUse) {
      setState({ loading: false, data: null, error: null })
      return
    }
    setState({ loading: true, data: null, error: null })
    api.matchCases({
      building_use: buildingUse,
      zone_use: zoneUse || '',
      site_area: siteArea || undefined,
      jurisdiction: jurisdiction || undefined,
      limit: 5,
    })
      .then((data) => alive && setState({ loading: false, data, error: null }))
      .catch((e) => alive && setState({ loading: false, data: null, error: e.message }))
    return () => { alive = false }
  }, [buildingUse, zoneUse, siteArea, jurisdiction])

  if (state.loading) {
    return <SkeletonCard />
  }
  if (state.error) {
    return (
      <CardWrap>
        <p className="text-xs text-red-600">사내 케이스 조회 실패: {state.error}</p>
      </CardWrap>
    )
  }
  if (!state.data) return null

  const { matches, total_loaded, db_exists, db_path } = state.data

  if (!db_exists) {
    return (
      <CardWrap>
        <Header />
        <p className="text-xs text-gray-500 mt-2">
          KUNWON_DB 디렉토리 없음 — <code className="text-[var(--font-size-2xs)] bg-gray-100 px-1 py-0.5 rounded">{db_path}</code>
        </p>
        <p className="text-[var(--font-size-xs)] text-gray-400 mt-1">
          <code>.env</code> 의 <code>CASE_DB_PATH</code> 또는 프로젝트 루트의 <code>KUNWON_DB/cases/</code> 에 *.json 케이스 파일을 배치하세요.
        </p>
      </CardWrap>
    )
  }

  if (!matches || matches.length === 0) {
    return (
      <CardWrap>
        <Header total={total_loaded} />
        <p className="text-xs text-gray-500 mt-2">
          용도+지역 조건과 일치하는 케이스가 없습니다. (DB 총 {total_loaded}건)
        </p>
      </CardWrap>
    )
  }

  return (
    <CardWrap>
      <Header total={total_loaded} matched={matches.length} />
      <div className="mt-3 space-y-2">
        {matches.map((m, i) => <CaseRow key={i} match={m} />)}
      </div>
    </CardWrap>
  )
}

function Header({ total, matched }) {
  return (
    <div className="flex items-center justify-between">
      <p className="text-sm font-semibold text-amber-800">📁 유사 사내 케이스</p>
      {total != null && (
        <span className="text-xs text-amber-600">
          {matched != null ? `${matched}건 매칭 / 전체 ${total}건` : `DB ${total}건`}
        </span>
      )}
    </div>
  )
}

function CardWrap({ children }) {
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
      {children}
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-amber-100 bg-amber-50/50 p-4">
      <p className="text-xs text-amber-600">📁 유사 사내 케이스 검색 중...</p>
    </div>
  )
}

function CaseRow({ match }) {
  const { case: c, score, reasons } = match
  const badge = RESULT_BADGE[c.result] || { label: c.result || '미분류', cls: 'bg-gray-100 text-gray-600' }

  return (
    <div className="bg-white rounded-lg border border-amber-100 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {c.internal_url ? (
              <a
                href={c.internal_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-semibold text-blue-700 hover:underline truncate"
              >
                {c.project_name}
              </a>
            ) : (
              <span className="text-sm font-semibold text-gray-800 truncate">{c.project_name}</span>
            )}
            <span className={`text-[var(--font-size-2xs)] px-1.5 py-0.5 rounded-full font-medium ${badge.cls}`}>
              {badge.label}
            </span>
            {c.year && <span className="text-[var(--font-size-2xs)] text-gray-400">{c.year}</span>}
          </div>

          <div className="mt-1 text-xs text-gray-500 flex flex-wrap gap-x-3 gap-y-0.5">
            <span>{c.building_use}</span>
            <span>{c.zone_use}</span>
            {c.site_area && <span>대지 {c.site_area}㎡</span>}
            {c.floors_above && <span>지상 {c.floors_above}층</span>}
            {c.height && <span>{c.height}m</span>}
          </div>

          {c.tags?.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {c.tags.map((t, i) => (
                <span key={i} className="text-[var(--font-size-2xs)] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                  #{t}
                </span>
              ))}
            </div>
          )}

          {reasons?.length > 0 && (
            <p className="mt-1 text-[var(--font-size-xs)] text-amber-700">
              매칭 이유: {reasons.join(', ')}
            </p>
          )}
        </div>

        <div className="text-right flex-shrink-0">
          <p className="text-xs text-gray-400">유사도</p>
          <p className="text-base font-bold text-amber-700">{score}</p>
        </div>
      </div>
    </div>
  )
}

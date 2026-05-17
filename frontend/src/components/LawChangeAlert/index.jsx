import { useEffect, useState } from 'react'
import { api } from '../../utils/api'

/**
 * 법규/조례 변경 + 행정 고시 통합 알림.
 *
 * 두 가지 출처:
 *   1) 법제처 조례 본문 해시 변경 (능동 스캔) — 항상 조회
 *   2) 토지이음 행정 고시 (Phase 2) — areaCd 전달 시 자동 조회
 */
export default function LawChangeAlert({ areaCd }) {
  const [changes, setChanges] = useState({ loading: true, items: [], error: null })
  const [notices, setNotices] = useState({ loading: false, items: [], total: 0, period: null, warning: null, error: null })
  const [expandedChanges, setExpandedChanges] = useState(false)
  const [expandedNotices, setExpandedNotices] = useState(false)
  const [seedLoading, setSeedLoading] = useState(false)

  const loadChanges = () => {
    setChanges({ loading: true, items: [], error: null })
    api.lawChanges()
      .then((d) => setChanges({ loading: false, items: d.changes || [], error: null }))
      .catch((e) => setChanges({ loading: false, items: [], error: e.message }))
  }

  const loadNotices = (cd) => {
    if (!cd) return
    setNotices((p) => ({ ...p, loading: true, error: null }))
    api.eumNotices({ areaCd: cd, days: 90 })
      .then((d) => setNotices({
        loading: false,
        items: d.items || [],
        total: d.total_size || 0,
        period: d.period || null,
        warning: d.warning || null,
        error: null,
      }))
      .catch((e) => setNotices((p) => ({ ...p, loading: false, error: e.message })))
  }

  useEffect(() => { loadChanges() }, [])
  useEffect(() => { loadNotices(areaCd) }, [areaCd])

  const seedDemo = async () => {
    setSeedLoading(true)
    try {
      await api.seedDemoChange()
      loadChanges()
    } catch (e) {
      console.error(e)
    } finally {
      setSeedLoading(false)
    }
  }

  // 로딩 중 (양쪽 다)
  if (changes.loading && notices.loading) return null

  const hasChanges = changes.items.length > 0
  const hasNotices = notices.items.length > 0
  const recentChanges = expandedChanges ? changes.items : changes.items.slice(0, 3)
  const recentNotices = expandedNotices ? notices.items : notices.items.slice(0, 5)

  // 아무것도 없으면 합쳐서 작은 안내
  if (!hasChanges && !hasNotices && !changes.error && !notices.error) {
    return (
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-3 flex items-center justify-between">
        <span className="text-xs text-gray-500">
          ✅ 최근 법규/조례 변경 감지 없음
          {areaCd && notices.period && (
            <span className="text-gray-400 ml-1">
              · 행정 고시 0건 (최근 {notices.period.days}일)
            </span>
          )}
        </span>
        <button
          onClick={seedDemo}
          disabled={seedLoading}
          className="text-[10px] text-gray-400 hover:text-gray-600 underline disabled:opacity-40"
        >
          {seedLoading ? '...' : '데모 데이터 삽입'}
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {/* 1) 법제처 조례 본문 변경 (orange) */}
      {(hasChanges || changes.error) && (
        <div className={`rounded-xl border-2 p-4 ${changes.error ? 'border-gray-200 bg-gray-50' : 'border-orange-300 bg-orange-50'}`}>
          {changes.error ? (
            <p className="text-xs text-gray-500">법규 변경 조회 실패: {changes.error}</p>
          ) : (
            <>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-semibold text-orange-800">
                    ⚠️ 법규/조례 변경 감지 ({changes.items.length}건)
                  </p>
                  <p className="text-xs text-orange-600 mt-0.5">
                    진단 결과 신뢰도가 영향받을 수 있습니다. 시니어 확인 권장.
                  </p>
                </div>
                <button
                  onClick={loadChanges}
                  className="text-xs text-orange-600 hover:text-orange-800 underline"
                >
                  새로고침
                </button>
              </div>
              <div className="mt-3 space-y-1.5">
                {recentChanges.map((c, i) => (
                  <ChangeRow key={i} change={c} />
                ))}
              </div>
              {changes.items.length > 3 && (
                <button
                  onClick={() => setExpandedChanges((v) => !v)}
                  className="mt-2 text-xs text-orange-700 hover:underline"
                >
                  {expandedChanges ? '접기' : `더 보기 (+${changes.items.length - 3}건)`}
                </button>
              )}
            </>
          )}
        </div>
      )}

      {/* 2) 토지이음 행정 고시 (blue) — Phase 2 */}
      {areaCd && (hasNotices || notices.error || notices.warning) && (
        <div className={`rounded-xl border-2 p-4 ${
          notices.error || notices.warning
            ? 'border-gray-200 bg-gray-50'
            : 'border-blue-300 bg-blue-50'
        }`}>
          {notices.error ? (
            <p className="text-xs text-gray-500">행정 고시 조회 실패: {notices.error}</p>
          ) : notices.warning ? (
            <p className="text-xs text-gray-500">
              📢 행정 고시 — {notices.warning}
            </p>
          ) : (
            <>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-semibold text-blue-800">
                    📢 행정 고시 ({notices.total}건 · 최근 {notices.period?.days || 90}일)
                  </p>
                  <p className="text-xs text-blue-600 mt-0.5">
                    토지이음 — 해당 시군구 도시계획결정·지정·변경고시.
                    진단에 영향 줄 수 있는 항목은 시니어 확인.
                  </p>
                </div>
                <button
                  onClick={() => loadNotices(areaCd)}
                  className="text-xs text-blue-600 hover:text-blue-800 underline"
                >
                  새로고침
                </button>
              </div>
              <div className="mt-3 space-y-1.5">
                {recentNotices.map((n, i) => (
                  <NoticeRow key={i} notice={n} />
                ))}
              </div>
              {notices.items.length > 5 && (
                <button
                  onClick={() => setExpandedNotices((v) => !v)}
                  className="mt-2 text-xs text-blue-700 hover:underline"
                >
                  {expandedNotices ? '접기' : `더 보기 (+${notices.items.length - 5}건)`}
                </button>
              )}
              {notices.total > notices.items.length && (
                <p className="mt-1 text-[10px] text-blue-600">
                  ※ 전체 {notices.total}건 중 첫 페이지({notices.items.length}건)만 표시 — 토지이음에서 전체 확인
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function ChangeRow({ change }) {
  return (
    <div className="bg-white rounded border border-orange-100 px-2 py-1.5 text-xs">
      <div className="flex items-center justify-between flex-wrap gap-1">
        <span className="font-medium text-gray-700">
          {change.jurisdiction_code} · {change.law_type}
        </span>
        <span className="text-gray-500">
          {formatDate(change.current_at)}
          {change.days_since_change != null && (
            <span className="text-gray-400 ml-1">({change.days_since_change}일 전)</span>
          )}
        </span>
      </div>
      <div className="text-gray-500 mt-0.5 font-mono text-[10px]">
        {change.previous_hash} → <span className="text-orange-700 font-semibold">{change.current_hash}</span>
      </div>
    </div>
  )
}

function NoticeRow({ notice }) {
  const dateStr = formatYmd(notice.ntc_date)
  return (
    <div className="bg-white rounded border border-blue-100 px-2.5 py-1.5 text-xs">
      <div className="flex items-baseline justify-between gap-2 flex-wrap">
        <a
          href={notice.link || '#'}
          target="_blank"
          rel="noreferrer noopener"
          className="font-medium text-gray-800 hover:text-blue-700 hover:underline flex-1 min-w-0 truncate"
          title={notice.title}
        >
          {notice.title || '(제목 없음)'}
        </a>
        <span className="text-gray-500 flex-shrink-0">{dateStr}</span>
      </div>
      {notice.author && (
        <p className="text-[10px] text-gray-500 mt-0.5">{notice.author}</p>
      )}
      {notice.summary && (
        <p className="text-[11px] text-gray-600 mt-0.5 leading-relaxed line-clamp-2">
          {notice.summary}
        </p>
      )}
    </div>
  )
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' })
  } catch {
    return iso.slice(0, 10)
  }
}

function formatYmd(ymd) {
  if (!ymd) return ''
  const s = String(ymd).replace(/\D/g, '')
  if (s.length >= 8) return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
  return ymd
}

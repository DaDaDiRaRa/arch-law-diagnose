import { useEffect, useState } from 'react'
import { api } from '../../utils/api'

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

  if (changes.loading && notices.loading) return null

  const hasChanges = changes.items.length > 0
  const hasNotices = notices.items.length > 0
  const recentChanges = expandedChanges ? changes.items : changes.items.slice(0, 3)
  const recentNotices = expandedNotices ? notices.items : notices.items.slice(0, 5)

  if (!hasChanges && !hasNotices && !changes.error && !notices.error) {
    return (
      <div className="p-3 flex items-center justify-between" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)'}}>
        <span className="text-xs" style={{color:'var(--mute)'}}>
          최근 법규/조례 변경 감지 없음
          {areaCd && notices.period && (
            <span className="ml-1" style={{color:'var(--faint)'}}>
              · 행정 고시 0건 (최근 {notices.period.days}일)
            </span>
          )}
        </span>
        <button
          onClick={seedDemo}
          disabled={seedLoading}
          className="text-[10px] underline disabled:opacity-40"
          style={{color:'var(--faint)'}}
        >
          {seedLoading ? '...' : '데모 데이터 삽입'}
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {/* 1) 법제처 조례 본문 변경 (warn) */}
      {(hasChanges || changes.error) && (
        <div className="p-4" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:`3px solid ${changes.error ? 'var(--hairline)' : 'var(--warn)'}`,backgroundColor:'var(--canvas-elevated)'}}>
          {changes.error ? (
            <p className="text-xs" style={{color:'var(--mute)'}}>법규 변경 조회 실패: {changes.error}</p>
          ) : (
            <>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-semibold" style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}}>
                    법규/조례 변경 감지 ({changes.items.length}건)
                  </p>
                  <p className="text-xs mt-0.5" style={{color:'var(--mute)'}}>
                    진단 결과 신뢰도가 영향받을 수 있습니다. 시니어 확인 권장.
                  </p>
                </div>
                <button onClick={loadChanges} className="text-xs underline" style={{color:'var(--warn-deep)'}}>
                  새로고침
                </button>
              </div>
              <div className="mt-3 space-y-1.5">
                {recentChanges.map((c, i) => <ChangeRow key={i} change={c} />)}
              </div>
              {changes.items.length > 3 && (
                <button onClick={() => setExpandedChanges((v) => !v)} className="mt-2 text-xs underline" style={{color:'var(--warn-deep)'}}>
                  {expandedChanges ? '접기' : `더 보기 (+${changes.items.length - 3}건)`}
                </button>
              )}
            </>
          )}
        </div>
      )}

      {/* 2) 토지이음 행정 고시 (info) */}
      {areaCd && (hasNotices || notices.error || notices.warning) && (
        <div className="p-4" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:`3px solid ${notices.error || notices.warning ? 'var(--hairline)' : 'var(--info)'}`,backgroundColor:'var(--canvas-elevated)'}}>
          {notices.error ? (
            <p className="text-xs" style={{color:'var(--mute)'}}>행정 고시 조회 실패: {notices.error}</p>
          ) : notices.warning ? (
            <p className="text-xs" style={{color:'var(--mute)'}}>행정 고시 — {notices.warning}</p>
          ) : (
            <>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-semibold" style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}}>
                    행정 고시 ({notices.total}건 · 최근 {notices.period?.days || 90}일)
                  </p>
                  <p className="text-xs mt-0.5" style={{color:'var(--mute)'}}>
                    토지이음 — 해당 시군구 도시계획결정·지정·변경고시. 진단에 영향 줄 수 있는 항목은 시니어 확인.
                  </p>
                </div>
                <button onClick={() => loadNotices(areaCd)} className="text-xs underline" style={{color:'var(--info)'}}>
                  새로고침
                </button>
              </div>
              <div className="mt-3 space-y-1.5">
                {recentNotices.map((n, i) => <NoticeRow key={i} notice={n} />)}
              </div>
              {notices.items.length > 5 && (
                <button onClick={() => setExpandedNotices((v) => !v)} className="mt-2 text-xs underline" style={{color:'var(--info)'}}>
                  {expandedNotices ? '접기' : `더 보기 (+${notices.items.length - 5}건)`}
                </button>
              )}
              {notices.total > notices.items.length && (
                <p className="mt-1 text-[10px]" style={{color:'var(--mute)'}}>
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
    <div className="px-2 py-1.5 text-xs" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)'}}>
      <div className="flex items-center justify-between flex-wrap gap-1">
        <span className="font-medium" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>
          {change.jurisdiction_code} · {change.law_type}
        </span>
        <span style={{color:'var(--mute)'}}>
          {formatDate(change.current_at)}
          {change.days_since_change != null && (
            <span className="ml-1" style={{color:'var(--faint)'}}>({change.days_since_change}일 전)</span>
          )}
        </span>
      </div>
      <div className="mt-0.5 text-[10px]" style={{fontFamily:'var(--font-mono)',color:'var(--mute)'}}>
        {change.previous_hash} → <span className="font-semibold" style={{color:'var(--warn-deep)'}}>{change.current_hash}</span>
      </div>
    </div>
  )
}

function NoticeRow({ notice }) {
  const dateStr = formatYmd(notice.ntc_date)
  return (
    <div className="px-2.5 py-1.5 text-xs" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)'}}>
      <div className="flex items-baseline justify-between gap-2 flex-wrap">
        <a
          href={notice.link || '#'}
          target="_blank"
          rel="noreferrer noopener"
          className="font-medium hover:underline flex-1 min-w-0 truncate"
          style={{color:'var(--ink)'}}
          title={notice.title}
        >
          {notice.title || '(제목 없음)'}
        </a>
        <span className="flex-shrink-0" style={{color:'var(--mute)'}}>{dateStr}</span>
      </div>
      {notice.author && (
        <p className="text-[10px] mt-0.5" style={{color:'var(--mute)'}}>{notice.author}</p>
      )}
      {notice.summary && (
        <p className="text-xs mt-0.5 leading-relaxed line-clamp-2" style={{color:'var(--body)'}}>{notice.summary}</p>
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

import { useEffect, useState } from 'react'
import { api } from '../../utils/api'

export default function LawChangeAlert() {
  const [state, setState] = useState({ loading: true, changes: [], error: null })
  const [expanded, setExpanded] = useState(false)
  const [seedLoading, setSeedLoading] = useState(false)

  const load = () => {
    setState({ loading: true, changes: [], error: null })
    api.lawChanges()
      .then((d) => setState({ loading: false, changes: d.changes || [], error: null }))
      .catch((e) => setState({ loading: false, changes: [], error: e.message }))
  }

  useEffect(() => { load() }, [])

  const seedDemo = async () => {
    setSeedLoading(true)
    try {
      await api.seedDemoChange()
      load()
    } catch (e) {
      console.error(e)
    } finally {
      setSeedLoading(false)
    }
  }

  if (state.loading) return null  // 조용히 로딩

  if (state.error) {
    return (
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-3 text-xs text-gray-500">
        법규 변경 조회 실패: {state.error}
      </div>
    )
  }

  if (!state.changes.length) {
    return (
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-3 flex items-center justify-between">
        <span className="text-xs text-gray-500">
          ✅ 최근 법규/조례 변경 감지 없음
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

  const recent = state.changes.slice(0, 3)
  const hasMore = state.changes.length > 3

  return (
    <div className="rounded-xl border-2 border-orange-300 bg-orange-50 p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-semibold text-orange-800">
            ⚠️ 법규/조례 변경 감지 ({state.changes.length}건)
          </p>
          <p className="text-xs text-orange-600 mt-0.5">
            진단 결과 신뢰도가 영향받을 수 있습니다. 시니어 확인 권장.
          </p>
        </div>
        <button
          onClick={load}
          className="text-xs text-orange-600 hover:text-orange-800 underline"
        >
          새로고침
        </button>
      </div>

      <div className="mt-3 space-y-1.5">
        {(expanded ? state.changes : recent).map((c, i) => (
          <ChangeRow key={i} change={c} />
        ))}
      </div>

      {hasMore && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-2 text-xs text-orange-700 hover:underline"
        >
          {expanded ? '접기' : `더 보기 (+${state.changes.length - 3}건)`}
        </button>
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

function formatDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' })
  } catch {
    return iso.slice(0, 10)
  }
}

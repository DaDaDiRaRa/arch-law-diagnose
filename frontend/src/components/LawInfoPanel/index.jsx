import { useState } from 'react'
import { api } from '../../utils/api'

/**
 * 토지이음 법령정보 펼쳐보기 — Phase 1.
 *
 * 사용자가 클릭할 때만 lazy fetch. 진단 응답에는 포함 안 됨 (응답 가벼움).
 */
export default function LawInfoPanel({ areaCd, zoneUse, zoneDistrict }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  const canFetch = !!areaCd && !!zoneUse

  const handleToggle = async () => {
    if (data || error) {
      setOpen(!open)
      return
    }
    if (!canFetch) return
    setLoading(true)
    setError(null)
    try {
      const r = await api.eumLawInfo({ areaCd, zoneUse, zoneDistrict })
      setData(r)
      setOpen(true)
    } catch (e) {
      setError(e.message)
      setOpen(true)
    } finally {
      setLoading(false)
    }
  }

  if (!canFetch) return null

  return (
    <div className="rounded-xl border border-indigo-200 bg-indigo-50/40">
      <button
        onClick={handleToggle}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-indigo-100/40 transition-colors"
      >
        <span className="text-sm font-semibold text-indigo-900">
          📖 토지이용규제 법령 본문 (토지이음)
        </span>
        <span className="text-xs text-indigo-600">
          {loading ? '⟳ 조회 중...' : open ? '▲ 접기' : '▼ 펼쳐보기'}
        </span>
      </button>

      {open && error && (
        <div className="px-4 py-3 border-t border-indigo-200 text-xs text-red-600">
          조회 실패: {error}
        </div>
      )}

      {open && data && !error && (
        <div className="px-4 py-3 border-t border-indigo-200 space-y-4">
          {data.warning && (
            <p className="text-xs text-amber-700 bg-amber-50 px-2.5 py-1.5 rounded">
              ⚠ {data.warning}
            </p>
          )}
          {(data.groups || []).length === 0 && !data.warning && (
            <p className="text-xs text-gray-500">조회된 법령 본문 없음</p>
          )}
          {(data.groups || []).map((g, i) => (
            <LawGroup key={i} group={g} />
          ))}
          <p className="text-[10px] text-indigo-700 leading-relaxed border-t border-indigo-100 pt-2">
            출처: 토지이음 (eum.go.kr) · UCODE {data.ucode_count}개, 조문 {data.total_items}건.
            법령 본문은 토지이음 표준연계 데이터로 실시간 조회되며, 최종 해석은 별도 확인이 필요합니다.
          </p>
        </div>
      )}
    </div>
  )
}

function LawGroup({ group }) {
  const items = group.items || []
  return (
    <div className="bg-white rounded-lg border border-indigo-100 p-3">
      <div className="flex items-baseline justify-between mb-2 gap-2">
        <p className="text-sm font-bold text-gray-900">{group.uname}</p>
        <span className="text-[10px] text-gray-400 font-mono">{group.ucode}</span>
      </div>
      {group.law_nm && (
        <p className="text-xs text-gray-500 mb-2">근거 법령: {group.law_nm}</p>
      )}
      {items.length === 0 ? (
        <p className="text-xs text-gray-400">조문 없음</p>
      ) : (
        <ol className="space-y-1.5">
          {items.map((it, i) => (
            <LawItem key={i} item={it} />
          ))}
        </ol>
      )}
    </div>
  )
}

const LEVEL_PREFIX = { 0: '', 1: '  ', 2: '    ', 3: '      ' }
const LEVEL_LABEL = { 0: '조', 1: '항', 2: '호', 3: '목' }

function LawItem({ item }) {
  const lvl = item.law_level ?? 0
  const indent = LEVEL_PREFIX[lvl] || ''
  const labelCls = lvl === 0
    ? 'text-indigo-700 font-semibold'
    : lvl === 1
    ? 'text-indigo-600'
    : 'text-gray-600'
  return (
    <li className={`text-xs leading-relaxed whitespace-pre-wrap ${labelCls}`} style={{ paddingLeft: `calc(${lvl} * var(--gap-md))` }}>
      <span className="text-[10px] text-gray-400 mr-1">[{LEVEL_LABEL[lvl] || '?'}]</span>
      {indent}
      {item.law_contents}
    </li>
  )
}

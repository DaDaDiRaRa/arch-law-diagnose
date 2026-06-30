import { useState } from 'react'
import { api } from '../../utils/api'

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
    <div style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)'}}>
      <button
        onClick={handleToggle}
        className="w-full px-4 py-3 flex items-center justify-between text-left transition-colors"
      >
        <span className="text-sm font-semibold" style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}}>
          토지이용규제 법령 본문 (토지이음)
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
        <div className="px-4 py-3 space-y-4" style={{borderTop:'1px solid var(--hairline)'}}>
          {data.warning && (
            <p className="text-xs px-2.5 py-1.5" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--warn)',backgroundColor:'var(--canvas-elevated)',color:'var(--warn-deep)'}}>
              {data.warning}
            </p>
          )}
          {(data.groups || []).length === 0 && !data.warning && (
            <p className="text-xs" style={{color:'var(--mute)'}}>조회된 법령 본문 없음</p>
          )}
          {(data.groups || []).map((g, i) => (
            <LawGroup key={i} group={g} />
          ))}
          <p className="text-[10px] leading-relaxed pt-2" style={{color:'var(--faint)',borderTop:'1px solid var(--hairline-soft)',fontFamily:'var(--font-mono)'}}>
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
    <div className="p-3" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas-elevated)'}}>
      <div className="flex items-baseline justify-between mb-2 gap-2">
        <p className="text-sm font-bold" style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}}>{group.uname}</p>
        <span className="text-[10px]" style={{color:'var(--faint)',fontFamily:'var(--font-mono)'}}>{group.ucode}</span>
      </div>
      {group.law_nm && (
        <p className="text-xs mb-2" style={{color:'var(--mute)'}}>근거 법령: {group.law_nm}</p>
      )}
      {items.length === 0 ? (
        <p className="text-xs" style={{color:'var(--faint)'}}>조문 없음</p>
      ) : (
        <ol className="space-y-1.5">
          {items.map((it, i) => <LawItem key={i} item={it} />)}
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
  const color = lvl === 0 ? 'var(--ink)' : lvl === 1 ? 'var(--body)' : 'var(--mute)'
  return (
    <li className="text-xs leading-relaxed whitespace-pre-wrap" style={{color,paddingLeft:`calc(${lvl} * 16px)`}}>
      <span className="text-[10px] mr-1" style={{color:'var(--faint)',fontFamily:'var(--font-mono)'}}>[{LEVEL_LABEL[lvl] || '?'}]</span>
      {indent}
      {item.law_contents}
    </li>
  )
}

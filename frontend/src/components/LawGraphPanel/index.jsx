/**
 * 법규 의미 그래프 탐색기 (Step 11).
 */
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { api } from '../../utils/api'

const GraphCanvas = lazy(() => import('./GraphCanvas'))

const REL_STYLE = {
  근거:   { bg: 'rgba(37,99,235,0.08)',   fg: 'var(--info)' },
  위임:   { bg: 'rgba(124,58,237,0.08)',  fg: 'var(--violet)' },
  완화:   { bg: 'rgba(22,163,74,0.08)',   fg: 'var(--ok)' },
  제외:   { bg: 'rgba(107,114,128,0.1)',  fg: 'var(--mute)' },
  트리거: { bg: 'rgba(217,119,6,0.1)',    fg: 'var(--warn-deep)' },
  참조:   { bg: 'rgba(107,114,128,0.08)', fg: 'var(--mute)' },
}

const KIND_BADGE = {
  카테고리: '진단', 법률: '법', 시행령: '시행령', 시행규칙: '시행규칙',
  고시: '고시', 별표: '별표', 조례: '조례', 심의: '심의',
}

export default function LawGraphPanel({ focus }) {
  const [open, setOpen] = useState(false)
  const [graph, setGraph] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [current, setCurrent] = useState(null)
  const [search, setSearch] = useState('')
  const [viewMode, setViewMode] = useState('explorer')
  const rootRef = useRef(null)

  const ensureLoaded = async () => {
    if (graph !== null) return graph
    setLoading(true)
    try {
      const g = await api.lawGraph()
      setGraph(g)
      const firstCat = (g.nodes || []).find((n) => n.kind === '카테고리')
      setCurrent((c) => c || firstCat?.id || g.nodes?.[0]?.id || null)
      return g
    } catch (e) {
      setError(e.message || '그래프 조회 실패')
      return null
    } finally {
      setLoading(false)
    }
  }

  const toggle = async () => {
    const next = !open
    setOpen(next)
    if (next) await ensureLoaded()
  }

  const curate = async (action, source, target) => {
    const label = action === 'promote' ? '시드로 승격' : '반려(제거)'
    if (!window.confirm(`이 자동수확 관계를 ${label}하시겠어요?\n\n${source}\n→ ${target}`)) return
    try {
      if (action === 'promote') await api.lawGraphPromote({ source, target })
      else await api.lawGraphReject({ source, target })
      setGraph(await api.lawGraph())
    } catch (e) {
      alert(`${label} 실패: ${e.message || e}`)
    }
  }

  useEffect(() => {
    if (!focus?.id) return
    setOpen(true)
    setSearch('')
    ;(async () => {
      await ensureLoaded()
      setCurrent(focus.id)
      rootRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.id, focus?.ts])

  if (!graph) {
    return (
      <Shell open={open} onToggle={toggle} rootRef={rootRef}>
        {loading && <div className="text-[11px] py-1" style={{color:'var(--mute)'}}>그래프 불러오는 중…</div>}
        {error && (
          <div className="text-[11px] px-2 py-1.5" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--error)',backgroundColor:'var(--canvas-elevated)',color:'var(--error)'}}>{error}</div>
        )}
      </Shell>
    )
  }

  const byId = Object.fromEntries(graph.nodes.map((n) => [n.id, n]))
  const node = current ? byId[current] : null
  const categories = graph.nodes.filter((n) => n.kind === '카테고리')

  const out = graph.edges.filter((e) => e.source === current)
  const inc = graph.edges.filter((e) => e.target === current)
  const outByRel = groupByRel(out, (e) => e.target, byId)
  const incByRel = groupByRel(inc, (e) => e.source, byId)

  const searchHits = search.trim()
    ? graph.nodes.filter((n) => {
        const q = search.trim().toLowerCase()
        return `${n.law} ${n.article} ${n.title}`.toLowerCase().includes(q)
      })
    : null

  return (
    <Shell open={open} onToggle={toggle} rootRef={rootRef}>
      {/* 뷰 전환 */}
      <div className="flex gap-1 mb-2 p-0.5 w-fit" style={{borderRadius:'var(--radius-sm)',backgroundColor:'var(--canvas)',border:'1px solid var(--hairline)'}}>
        {[['explorer', '탐색기'], ['canvas', '그래프']].map(([k, label]) => (
          <button
            key={k}
            onClick={() => setViewMode(k)}
            className="text-[10px] font-medium px-2 py-0.5 transition-colors"
            style={viewMode === k
              ? {borderRadius:'var(--radius-sm)',backgroundColor:'var(--canvas-elevated)',color:'var(--brand)',fontFamily:'var(--font-sans)'}
              : {color:'var(--faint)',fontFamily:'var(--font-sans)'}}
          >
            {label}
          </button>
        ))}
      </div>

      {viewMode === 'canvas' ? (
        <Suspense fallback={<div className="text-[11px] py-2" style={{color:'var(--mute)'}}>그래프 렌더링 중…</div>}>
          <GraphCanvas graph={graph} current={current} onPick={setCurrent} />
        </Suspense>
      ) : (
      <>
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="조문·법령명 검색 (예: 용적률, 제56조)"
        className="w-full text-[11px] px-2 py-1 mb-2 focus:outline-none"
        style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius-sm)',backgroundColor:'var(--canvas-elevated)',color:'var(--body)',fontFamily:'var(--font-sans)'}}
      />
      {searchHits ? (
        <div className="space-y-1 mb-2">
          {searchHits.length === 0 && (
            <div className="text-[11px] py-1" style={{color:'var(--mute)'}}>"{search}"에 맞는 조문이 없습니다.</div>
          )}
          {searchHits.map((n) => (
            <NodeChip key={n.id} node={n} onClick={() => { setCurrent(n.id); setSearch('') }} />
          ))}
        </div>
      ) : (
        <>
          <div className="flex flex-wrap gap-1 mb-3">
            {categories.map((c) => (
              <button
                key={c.id}
                onClick={() => setCurrent(c.id)}
                className="text-[10px] px-2 py-0.5 transition-colors"
                style={current === c.id
                  ? {borderRadius:'var(--radius-pill)',backgroundColor:'var(--brand)',color:'#fff',border:'1px solid var(--brand)',fontFamily:'var(--font-sans)'}
                  : {borderRadius:'var(--radius-pill)',border:'1px solid var(--hairline)',color:'var(--mute)',fontFamily:'var(--font-sans)'}}
              >
                {c.title}
              </button>
            ))}
          </div>

          {node && (
            <div className="mb-2 pb-2" style={{borderBottom:'1px solid var(--hairline-soft)'}}>
              <div className="flex items-center gap-1.5">
                <KindBadge kind={node.kind} />
                <span className="text-xs font-semibold" style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}}>
                  {node.law} {node.article}
                </span>
              </div>
              {node.title && <div className="text-[11px] mt-0.5" style={{color:'var(--mute)'}}>{node.title}</div>}
              {node.url && (
                <a href={node.url} target="_blank" rel="noreferrer" className="text-[10px] hover:underline" style={{color:'var(--link)'}}>
                  법령 원문 보기 ↗
                </a>
              )}
            </div>
          )}

          <RelGroups title="이 항목이 가리키는 관계" groups={outByRel} onPick={setCurrent} onCurate={curate} />
          <RelGroups title="이 항목을 가리키는 관계" groups={incByRel} onPick={setCurrent} onCurate={curate} />

          {Object.keys(outByRel).length === 0 && Object.keys(incByRel).length === 0 && (
            <div className="text-[11px] py-1" style={{color:'var(--faint)'}}>연결된 관계가 없습니다.</div>
          )}
        </>
      )}
      </>
      )}

      {graph.meta?.disclaimer && (
        <p className="text-[10px] mt-3 pt-2" style={{color:'var(--faint)',borderTop:'1px solid var(--hairline-soft)'}}>
          {graph.meta.disclaimer}
        </p>
      )}
    </Shell>
  )
}

function groupByRel(edges, otherId, byId) {
  const groups = {}
  for (const e of edges) {
    const other = byId[otherId(e)]
    if (!other) continue
    ;(groups[e.rel] ||= []).push({
      note: e.note, origin: e.origin, source: e.source, target: e.target, node: other,
    })
  }
  return groups
}

function RelGroups({ title, groups, onPick, onCurate }) {
  const rels = Object.keys(groups)
  if (rels.length === 0) return null
  return (
    <div className="mb-2">
      <div className="text-[10px] font-medium mb-1" style={{color:'var(--faint)',fontFamily:'var(--font-mono)',textTransform:'uppercase',letterSpacing:'0.06em'}}>{title}</div>
      <div className="space-y-1.5">
        {rels.map((rel) => (
          <div key={rel} className="flex flex-wrap items-center gap-1">
            <RelTag rel={rel} />
            {groups[rel].map((g, i) => (
              <NodeChip
                key={i}
                node={g.node}
                note={g.note}
                auto={g.origin === 'auto'}
                source={g.source}
                target={g.target}
                onCurate={onCurate}
                onClick={() => onPick(g.node.id)}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

function RelTag({ rel }) {
  const s = REL_STYLE[rel] || REL_STYLE.참조
  return (
    <span className="text-[10px] px-1.5 py-0.5 font-medium" style={{borderRadius:'var(--radius-sm)',backgroundColor:s.bg,color:s.fg,fontFamily:'var(--font-mono)'}}>
      {rel}
    </span>
  )
}

function NodeChip({ node, note, auto, source, target, onCurate, onClick }) {
  const isAuto = auto || node.origin === 'auto'
  const canCurate = isAuto && onCurate && source && target
  return (
    <span className="inline-flex items-center">
      <button
        onClick={onClick}
        title={note ? (isAuto ? `${note} · 자동수확(미검증)` : note) : (isAuto ? '자동수확(미검증)' : '')}
        className="text-[10px] px-2 py-0.5 transition-colors"
        style={isAuto
          ? {borderRadius:'var(--radius-sm)',border:'1px dashed var(--hairline)',backgroundColor:'var(--canvas-elevated)',color:'var(--body)',fontFamily:'var(--font-sans)'}
          : {borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas-elevated)',color:'var(--body)',fontFamily:'var(--font-sans)'}}
      >
        {node.kind !== '카테고리' && <KindBadge kind={node.kind} small />}
        <span className="ml-1">{node.article ? `${node.law} ${node.article}` : node.title}</span>
        {isAuto && <span className="ml-1 text-[8px]" style={{color:'var(--faint)'}}>자동</span>}
      </button>
      {canCurate && (
        <span className="inline-flex items-center ml-0.5">
          <button
            onClick={(e) => { e.stopPropagation(); onCurate('promote', source, target) }}
            title="이 자동수확 관계를 검증된 시드로 승격(영구)"
            className="text-[9px] px-1 py-0.5"
            style={{borderRadius:'var(--radius-sm)',color:'var(--ok)'}}
          >
            승격
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onCurate('reject', source, target) }}
            title="이 자동수확 관계를 반려(제거 + 재수확 차단)"
            className="text-[9px] px-1 py-0.5"
            style={{borderRadius:'var(--radius-sm)',color:'var(--error)'}}
          >
            반려
          </button>
        </span>
      )}
    </span>
  )
}

function KindBadge({ kind, small }) {
  return (
    <span
      className={`${small ? 'text-[9px]' : 'text-[10px]'} px-1`}
      style={{borderRadius:'var(--radius-sm)',backgroundColor:'var(--canvas)',color:'var(--mute)',fontFamily:'var(--font-mono)',border:'1px solid var(--hairline)'}}
    >
      {KIND_BADGE[kind] || kind}
    </span>
  )
}

function Shell({ open, onToggle, children, rootRef }) {
  return (
    <div ref={rootRef} style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)'}}>
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between px-3 py-2.5 text-left"
      >
        <span className="text-xs font-semibold" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>
          법규 관계 그래프
          <span className="text-[10px] font-normal ml-2" style={{color:'var(--faint)',fontFamily:'var(--font-mono)'}}>
            적용·위임·완화·트리거 관계 탐색
          </span>
        </span>
        <span className="text-xs" style={{color:'var(--faint)'}}>{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="px-3 pb-3 pt-3" style={{borderTop:'1px solid var(--hairline)'}}>{children}</div>}
    </div>
  )
}

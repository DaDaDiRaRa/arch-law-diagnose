/**
 * 법규 의미 그래프 탐색기 (Step 11).
 *
 * 진단이 적용하는 조문과 그 관계(근거·위임·완화·제외·트리거·참조)를 탐색.
 * 카테고리/노드 선택 → 인접 조문을 관계별로 묶어 클릭 가능한 칩으로 표시 → 이동(브라우징).
 * 무거운 그래프 캔버스 라이브러리 없이 관계 탐색에 집중(신규 의존성 0).
 */
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { api } from '../../utils/api'

// 무거운 react-flow는 캔버스 뷰를 열 때만 로드(초기 번들 경량화)
const GraphCanvas = lazy(() => import('./GraphCanvas'))

const REL_STYLE = {
  근거: { bg: 'rgba(37,99,235,0.1)', fg: '#2563eb' },
  위임: { bg: 'rgba(124,58,237,0.1)', fg: '#7c3aed' },
  완화: { bg: 'rgba(22,163,74,0.1)', fg: 'var(--color-success)' },
  제외: { bg: 'rgba(107,114,128,0.12)', fg: '#6b7280' },
  트리거: { bg: 'rgba(217,119,6,0.12)', fg: 'var(--color-warning)' },
  참조: { bg: 'rgba(107,114,128,0.1)', fg: '#6b7280' },
}

const KIND_BADGE = {
  카테고리: '진단', 법률: '법', 시행령: '시행령', 시행규칙: '시행규칙',
  고시: '고시', 별표: '별표', 조례: '조례', 심의: '심의',
}

export default function LawGraphPanel({ focus }) {
  const [open, setOpen] = useState(false)
  const [graph, setGraph] = useState(null) // {nodes, edges, meta}
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [current, setCurrent] = useState(null) // 선택 노드 id
  const [search, setSearch] = useState('')
  const [viewMode, setViewMode] = useState('explorer') // 'explorer' | 'canvas'
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

  // 카테고리 카드의 "관계 보기" → 패널 열고 해당 노드로 점프 + 스크롤 (#3)
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
        {loading && <div className="text-[11px] text-gray-500 py-1">그래프 불러오는 중…</div>}
        {error && (
          <div className="text-[11px] text-red-600 bg-red-50 border border-red-200 px-2 py-1.5 rounded">{error}</div>
        )}
      </Shell>
    )
  }

  const byId = Object.fromEntries(graph.nodes.map((n) => [n.id, n]))
  const node = current ? byId[current] : null
  const categories = graph.nodes.filter((n) => n.kind === '카테고리')

  // 선택 노드의 인접 관계 (나가는/들어오는)
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
      {/* 뷰 전환: 탐색기 / 그래프 캔버스 */}
      <div className="flex gap-1 mb-2 bg-gray-100 rounded p-0.5 w-fit">
        {[['explorer', '탐색기'], ['canvas', '그래프']].map(([k, label]) => (
          <button
            key={k}
            onClick={() => setViewMode(k)}
            className="text-[10px] font-medium px-2 py-0.5 rounded transition-colors"
            style={
              viewMode === k
                ? { backgroundColor: 'white', color: 'var(--color-accent)' }
                : { color: '#9ca3af' }
            }
          >
            {label}
          </button>
        ))}
      </div>

      {viewMode === 'canvas' ? (
        <Suspense fallback={<div className="text-[11px] text-gray-500 py-2">그래프 렌더링 중…</div>}>
          <GraphCanvas graph={graph} current={current} onPick={setCurrent} />
        </Suspense>
      ) : (
      <>
      {/* 검색 */}
      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="조문·법령명 검색 (예: 용적률, 제56조)"
        className="w-full text-[11px] border border-gray-200 rounded px-2 py-1 bg-white text-gray-700 mb-2"
      />
      {searchHits ? (
        <div className="space-y-1 mb-2">
          {searchHits.length === 0 && (
            <div className="text-[11px] text-gray-500 py-1">"{search}"에 맞는 조문이 없습니다.</div>
          )}
          {searchHits.map((n) => (
            <NodeChip key={n.id} node={n} onClick={() => { setCurrent(n.id); setSearch('') }} />
          ))}
        </div>
      ) : (
        <>
          {/* 카테고리 빠른 이동 */}
          <div className="flex flex-wrap gap-1 mb-3">
            {categories.map((c) => (
              <button
                key={c.id}
                onClick={() => setCurrent(c.id)}
                className="text-[10px] px-2 py-0.5 rounded-full border transition-colors"
                style={
                  current === c.id
                    ? { backgroundColor: 'var(--color-accent)', color: 'white', borderColor: 'var(--color-accent)' }
                    : { borderColor: '#e5e7eb', color: '#6b7280' }
                }
              >
                {c.title}
              </button>
            ))}
          </div>

          {/* 선택 노드 헤더 */}
          {node && (
            <div className="mb-2 pb-2 border-b border-gray-100">
              <div className="flex items-center gap-1.5">
                <KindBadge kind={node.kind} />
                <span className="text-xs font-semibold text-gray-800">
                  {node.law} {node.article}
                </span>
              </div>
              {node.title && <div className="text-[11px] text-gray-500 mt-0.5">{node.title}</div>}
              {node.url && (
                <a
                  href={node.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[10px] text-blue-600 hover:underline"
                >
                  법령 원문 보기 ↗
                </a>
              )}
            </div>
          )}

          {/* 나가는 관계 */}
          <RelGroups title="이 항목이 가리키는 관계" groups={outByRel} onPick={setCurrent} />
          {/* 들어오는 관계 */}
          <RelGroups title="이 항목을 가리키는 관계" groups={incByRel} onPick={setCurrent} />

          {Object.keys(outByRel).length === 0 && Object.keys(incByRel).length === 0 && (
            <div className="text-[11px] text-gray-400 py-1">연결된 관계가 없습니다.</div>
          )}
        </>
      )}
      </>
      )}

      {graph.meta?.disclaimer && (
        <p className="text-[10px] text-gray-400 mt-3 pt-2 border-t border-gray-100">
          ⚠ {graph.meta.disclaimer}
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
    ;(groups[e.rel] ||= []).push({ note: e.note, origin: e.origin, node: other })
  }
  return groups
}


function RelGroups({ title, groups, onPick }) {
  const rels = Object.keys(groups)
  if (rels.length === 0) return null
  return (
    <div className="mb-2">
      <div className="text-[10px] font-medium text-gray-400 mb-1">{title}</div>
      <div className="space-y-1.5">
        {rels.map((rel) => (
          <div key={rel} className="flex flex-wrap items-center gap-1">
            <RelTag rel={rel} />
            {groups[rel].map((g, i) => (
              <NodeChip key={i} node={g.node} note={g.note} auto={g.origin === 'auto'} onClick={() => onPick(g.node.id)} />
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
    <span className="text-[10px] px-1.5 py-0.5 rounded font-medium" style={{ backgroundColor: s.bg, color: s.fg }}>
      {rel}
    </span>
  )
}

function NodeChip({ node, note, auto, onClick }) {
  const isAuto = auto || node.origin === 'auto'
  return (
    <button
      onClick={onClick}
      title={note ? (isAuto ? `${note} · 자동수확(미검증)` : note) : (isAuto ? '자동수확(미검증)' : '')}
      className="text-[10px] px-2 py-0.5 rounded border bg-white hover:border-gray-400 text-gray-700 transition-colors"
      style={isAuto ? { borderStyle: 'dashed', borderColor: '#cbd5e1' } : { borderColor: '#e5e7eb' }}
    >
      {node.kind !== '카테고리' && <KindBadge kind={node.kind} small />}
      <span className="ml-1">{node.article ? `${node.law} ${node.article}` : node.title}</span>
      {isAuto && <span className="ml-1 text-[8px] text-gray-400">자동</span>}
    </button>
  )
}

function KindBadge({ kind, small }) {
  return (
    <span
      className={`${small ? 'text-[9px]' : 'text-[10px]'} px-1 rounded bg-gray-100 text-gray-500`}
    >
      {KIND_BADGE[kind] || kind}
    </span>
  )
}

function Shell({ open, onToggle, children, rootRef }) {
  return (
    <div ref={rootRef} className="border border-gray-200 rounded-lg bg-gray-50">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between px-3 py-2.5 text-left"
      >
        <span className="text-xs font-semibold text-gray-700">
          🕸 법규 관계 그래프
          <span className="text-[10px] font-normal text-gray-400 ml-2">
            적용·위임·완화·트리거 관계 탐색
          </span>
        </span>
        <span className="text-gray-400 text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && <div className="px-3 pb-3 border-t border-gray-200 pt-3">{children}</div>}
    </div>
  )
}

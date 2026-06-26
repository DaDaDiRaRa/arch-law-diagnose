/**
 * 법규 그래프 캔버스 (react-flow). 무거운 의존성이라 LawGraphPanel에서 lazy-load.
 * 컬럼별(kind) 세로 적층 — 근거/위임 흐름이 좌→우로 읽히는 결정론적 레이아웃.
 */
import { useMemo } from 'react'
import ReactFlow, { Background, Controls, MarkerType, MiniMap } from 'reactflow'
import 'reactflow/dist/style.css'

const KIND_COLUMN = {
  카테고리: 0, 법률: 1, 시행령: 2, 시행규칙: 2, 고시: 3, 별표: 3, 조례: 3, 심의: 4,
}
const KIND_BG = {
  카테고리: '#eff6ff', 법률: '#ffffff', 시행령: '#f5f3ff',
  고시: '#fffbeb', 별표: '#fffbeb', 시행규칙: '#f5f3ff', 조례: '#f0fdf4', 심의: '#fff7ed',
}
// rel → 색 (index.jsx REL_STYLE와 일치 유지)
const REL_COLOR = {
  근거: '#2563eb', 위임: '#7c3aed', 완화: '#16a34a',
  제외: '#6b7280', 트리거: '#d97706', 참조: '#6b7280',
}

export default function GraphCanvas({ graph, current, onPick }) {
  const { nodes, edges } = useMemo(() => {
    const colCount = {}
    const rfNodes = graph.nodes.map((n) => {
      const col = KIND_COLUMN[n.kind] ?? 3
      const row = (colCount[col] = (colCount[col] || 0) + 1) - 1
      const label = n.article ? `${n.law}\n${n.article}` : n.title || n.law
      return {
        id: n.id,
        position: { x: col * 230, y: row * 64 },
        data: { label },
        style: {
          fontSize: 10,
          width: 170,
          padding: 6,
          borderRadius: 8,
          background: KIND_BG[n.kind] || '#fff',
          border: n.id === current ? '2px solid var(--color-accent)' : '1px solid #e5e7eb',
          whiteSpace: 'pre-line',
        },
      }
    })
    const rfEdges = graph.edges.map((e, i) => {
      const color = REL_COLOR[e.rel] || REL_COLOR.참조
      const isAuto = e.origin === 'auto'
      return {
        id: `e${i}`,
        source: e.source,
        target: e.target,
        label: isAuto ? `${e.rel}·자동` : e.rel,
        labelStyle: { fontSize: 9, fill: color },
        style: { stroke: color, strokeWidth: 1.2, strokeDasharray: isAuto ? '4 3' : undefined },
        markerEnd: { type: MarkerType.ArrowClosed, color },
      }
    })
    return { nodes: rfNodes, edges: rfEdges }
  }, [graph, current])

  return (
    <div style={{ height: 460 }} className="border border-gray-200 rounded bg-white">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        minZoom={0.2}
        nodesDraggable={false}
        onNodeClick={(_, n) => onPick(n.id)}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} color="#f1f5f9" />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable nodeStrokeWidth={2} />
      </ReactFlow>
    </div>
  )
}

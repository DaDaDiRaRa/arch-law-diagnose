/**
 * 카테고리별 갭 시각화 — 막대 비교.
 *
 * status 색상:
 *   ok    → green (충족)
 *   over  → red   (초과)
 *   unknown / no_target → gray (회색)
 */
const STATUS_COLOR = {
  ok: 'var(--ok)',
  over: 'var(--error)',
  unknown: 'var(--faint)',
  no_target: 'var(--faint)',
}

const STATUS_BG = {
  ok: 'rgba(22, 163, 74, 0.1)',
  over: 'rgba(220, 38, 38, 0.1)',
  unknown: 'rgba(108, 117, 125, 0.08)',
  no_target: 'rgba(108, 117, 125, 0.08)',
}

const STATUS_LABEL = {
  ok: '충족',
  over: '초과',
  unknown: '확인불가',
  no_target: '요구 없음',
}

export default function GapChart({ categories }) {
  if (!categories || categories.length === 0) {
    return (
      <div
        className="text-xs px-4 py-3"
        style={{
          color: 'var(--mute)',
          background: 'var(--canvas-inset)',
          borderRadius: 'var(--radius-sm)',
        }}
      >
        갭 분석할 카테고리가 없습니다.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {categories.map((cat) => (
        <CategoryBar key={cat.key} cat={cat} />
      ))}
    </div>
  )
}

function CategoryBar({ cat }) {
  const status = cat.gap_analysis?.status || 'unknown'
  const target = cat.competition_target
  const limit = cat.legal_limit
  const maxRelief = cat.max_with_relief

  // 막대 스케일: limit, maxRelief, target 중 최대값을 100%로
  const denom = Math.max(target || 0, limit || 0, maxRelief || 0) || 100
  const targetW = target ? Math.min(100, (target / denom) * 100) : 0
  const limitW = limit ? Math.min(100, (limit / denom) * 100) : 0
  const reliefW = maxRelief ? Math.min(100, (maxRelief / denom) * 100) : 0

  return (
    <div
      className="border p-4"
      style={{
        backgroundColor: STATUS_BG[status],
        borderColor: STATUS_COLOR[status],
        borderRadius: 'var(--radius-sm)',
      }}
    >
      <div className="flex items-baseline justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>{cat.label}</span>
          <span
            className="text-[10px] font-medium px-2 py-0.5"
            style={{
              color: STATUS_COLOR[status],
              background: 'var(--canvas-elevated)',
              border: `1px solid ${STATUS_COLOR[status]}`,
              borderRadius: 'var(--radius-sm)',
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
            }}
          >
            {STATUS_LABEL[status]}
          </span>
        </div>
        <span
          className="text-xs font-medium"
          style={{ color: STATUS_COLOR[status] }}
        >
          {cat.gap_analysis?.gap_text}
        </span>
      </div>

      {/* 막대들 */}
      <div className="space-y-1.5">
        <Bar
          label="공모 요구"
          value={target}
          unit={cat.unit}
          width={targetW}
          color="var(--ink)"
          show={!!target}
        />
        <Bar
          label="법 한계"
          value={limit}
          unit={cat.unit}
          width={limitW}
          color="var(--info)"
          show={limit != null}
        />
        {maxRelief != null && maxRelief !== limit && (
          <Bar
            label="완화 적용 시"
            value={maxRelief}
            unit={cat.unit}
            width={reliefW}
            color="var(--ok)"
            show={true}
          />
        )}
      </div>

      {cat.source && (
        <div
          className="mt-2 text-[10px] pt-2"
          style={{ color: 'var(--mute)', borderTop: '1px solid var(--hairline)' }}
        >
          출처: {cat.source}
        </div>
      )}
    </div>
  )
}

function Bar({ label, value, unit, width, color, show }) {
  if (!show) return null
  return (
    <div>
      <div className="flex justify-between items-center text-[11px] mb-0.5">
        <span style={{ color: 'var(--body)' }}>{label}</span>
        <span className="font-medium" style={{ color: 'var(--ink)' }}>
          {value != null ? `${Number(value).toLocaleString()} ${unit}` : '—'}
        </span>
      </div>
      <div
        className="h-2 rounded overflow-hidden"
        style={{ background: 'var(--canvas-elevated)', border: '1px solid var(--hairline)' }}
      >
        <div
          className="h-full transition-all"
          style={{
            width: `${width}%`,
            backgroundColor: color,
          }}
        />
      </div>
    </div>
  )
}

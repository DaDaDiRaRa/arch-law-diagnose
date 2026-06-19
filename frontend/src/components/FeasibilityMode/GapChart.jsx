/**
 * 카테고리별 갭 시각화 — 막대 비교.
 *
 * status 색상:
 *   ok    → green (충족)
 *   over  → red   (초과)
 *   unknown / no_target → gray (회색)
 */
const STATUS_COLOR = {
  ok: 'var(--color-success)',
  over: 'var(--color-danger)',
  unknown: 'var(--color-text-faint)',
  no_target: 'var(--color-text-faint)',
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
      <div className="text-xs text-gray-500 bg-gray-50 px-4 py-3 rounded">
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
      className="border rounded-lg p-4"
      style={{
        backgroundColor: STATUS_BG[status],
        borderColor: STATUS_COLOR[status],
      }}
    >
      <div className="flex items-baseline justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-800">{cat.label}</span>
          <span
            className="text-[10px] font-medium px-2 py-0.5 rounded"
            style={{
              color: STATUS_COLOR[status],
              backgroundColor: 'white',
              border: `1px solid ${STATUS_COLOR[status]}`,
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
          color="var(--color-text-body)"
          show={!!target}
        />
        <Bar
          label="법 한계"
          value={limit}
          unit={cat.unit}
          width={limitW}
          color="var(--color-info)"
          show={limit != null}
        />
        {maxRelief != null && maxRelief !== limit && (
          <Bar
            label="완화 적용 시"
            value={maxRelief}
            unit={cat.unit}
            width={reliefW}
            color="var(--color-success)"
            show={true}
          />
        )}
      </div>

      {cat.source && (
        <div className="mt-2 text-[10px] text-gray-500 pt-2 border-t border-gray-200">
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
        <span className="text-gray-600">{label}</span>
        <span className="font-medium text-gray-800">
          {value != null ? `${Number(value).toLocaleString()} ${unit}` : '—'}
        </span>
      </div>
      <div className="h-2 bg-white rounded overflow-hidden border border-gray-200">
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

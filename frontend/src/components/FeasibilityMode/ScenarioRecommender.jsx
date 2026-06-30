/**
 * 완화 시나리오 추천 카드 — over 상태인 카테고리의 scenarios 배열을 표시.
 */
export default function ScenarioRecommender({ categories }) {
  const withScenarios = categories.filter((c) => c.scenarios && c.scenarios.length > 0)
  if (withScenarios.length === 0) return null

  return (
    <div className="space-y-4">
      {withScenarios.map((cat) => (
        <div
          key={cat.key}
          className="border p-4"
          style={{
            borderColor: 'var(--hairline)',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--canvas-elevated)',
          }}
        >
          <div className="flex items-baseline justify-between mb-2">
            <h4 className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>
              {cat.label} — 완화 시나리오
            </h4>
            <span className="text-xs" style={{ color: 'var(--mute)' }}>
              공모 요구: {Number(cat.competition_target).toLocaleString()} {cat.unit}
            </span>
          </div>

          <div className="space-y-2">
            {cat.scenarios.map((s, idx) => (
              <ScenarioRow key={idx} scenario={s} unit={cat.unit} />
            ))}
          </div>

          {cat.max_with_relief && (
            <div
              className="mt-3 text-[11px] pt-2"
              style={{ color: 'var(--mute)', borderTop: '1px solid var(--hairline)' }}
            >
              모든 완화 합산 최대: {Number(cat.max_with_relief).toLocaleString()} {cat.unit}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function ScenarioRow({ scenario, unit }) {
  const covers = scenario.covers_target
  const color = covers ? 'var(--ok)' : 'var(--warn-deep)'

  return (
    <div
      className="flex items-center gap-3 px-3 py-2 rounded border"
      style={{
        borderColor: covers ? 'rgba(22, 163, 74, 0.3)' : 'rgba(202, 138, 4, 0.3)',
        backgroundColor: covers ? 'rgba(22, 163, 74, 0.05)' : 'rgba(202, 138, 4, 0.05)',
      }}
    >
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium truncate" style={{ color: 'var(--ink)' }}>
          {scenario.label}
        </div>
        {scenario.basis && (
          <div className="text-[10px] truncate" style={{ color: 'var(--mute)' }}>{scenario.basis}</div>
        )}
      </div>
      <div className="text-right">
        <div className="text-xs font-semibold" style={{ color }}>
          {scenario.result_pct != null ? `→ ${scenario.result_pct} ${unit}` : '—'}
        </div>
        {scenario.delta_pct != null && (
          <div className="text-[10px]" style={{ color: 'var(--mute)' }}>+{scenario.delta_pct} {unit}</div>
        )}
      </div>
      <div className="text-[10px] font-medium" style={{ color }}>
        {covers ? '충족' : '부족'}
      </div>
    </div>
  )
}

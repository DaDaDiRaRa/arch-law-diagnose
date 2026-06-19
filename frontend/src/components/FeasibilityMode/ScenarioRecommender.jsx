/**
 * 완화 시나리오 추천 카드 — over 상태인 카테고리의 scenarios 배열을 표시.
 */
export default function ScenarioRecommender({ categories }) {
  const withScenarios = categories.filter((c) => c.scenarios && c.scenarios.length > 0)
  if (withScenarios.length === 0) return null

  return (
    <div className="space-y-4">
      {withScenarios.map((cat) => (
        <div key={cat.key} className="border border-gray-200 rounded-lg p-4 bg-white">
          <div className="flex items-baseline justify-between mb-2">
            <h4 className="text-sm font-semibold text-gray-800">
              {cat.label} — 완화 시나리오
            </h4>
            <span className="text-xs text-gray-500">
              공모 요구: {Number(cat.competition_target).toLocaleString()} {cat.unit}
            </span>
          </div>

          <div className="space-y-2">
            {cat.scenarios.map((s, idx) => (
              <ScenarioRow key={idx} scenario={s} unit={cat.unit} />
            ))}
          </div>

          {cat.max_with_relief && (
            <div className="mt-3 text-[11px] text-gray-500 pt-2 border-t border-gray-200">
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
  const color = covers ? 'var(--color-success)' : 'var(--color-warning)'

  return (
    <div
      className="flex items-center gap-3 px-3 py-2 rounded border"
      style={{
        borderColor: covers ? 'rgba(22, 163, 74, 0.3)' : 'rgba(202, 138, 4, 0.3)',
        backgroundColor: covers ? 'rgba(22, 163, 74, 0.05)' : 'rgba(202, 138, 4, 0.05)',
      }}
    >
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium text-gray-800 truncate">
          {scenario.label}
        </div>
        {scenario.basis && (
          <div className="text-[10px] text-gray-500 truncate">{scenario.basis}</div>
        )}
      </div>
      <div className="text-right">
        <div className="text-xs font-semibold" style={{ color }}>
          {scenario.result_pct != null ? `→ ${scenario.result_pct} ${unit}` : '—'}
        </div>
        {scenario.delta_pct != null && (
          <div className="text-[10px] text-gray-500">+{scenario.delta_pct} {unit}</div>
        )}
      </div>
      <div className="text-[10px] font-medium" style={{ color }}>
        {covers ? '충족' : '부족'}
      </div>
    </div>
  )
}

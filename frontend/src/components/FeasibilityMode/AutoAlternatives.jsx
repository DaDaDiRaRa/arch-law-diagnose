/**
 * 자동 제안 대안 — 시스템이 통과 가능한 완화 조합을 자동으로 돌려 만든 "안"들을 카드로 제시.
 *
 * 사용자가 What-If 슬라이더를 직접 돌리지 않아도, 이 대지에서 가능한 대안(기본/친환경/최대)을
 * 연면적 최대순으로 보여준다. "이 안으로"를 누르면 그 조합이 What-If에 시드되어 미세조정 가능.
 */
import { useFeasibilityStore } from '../../stores/feasibilityStore'

const fmt = (v, d = 0) =>
  v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: d })

const BURDEN = {
  low: { icon: '✅', label: '부담 낮음', color: 'var(--color-success)' },
  mid: { icon: '⚠', label: '부담 보통', color: 'var(--color-warning)' },
  high: { icon: '🔺', label: '부담 높음', color: 'var(--color-danger)' },
}

export default function AutoAlternatives({ alternatives }) {
  const { applyAlternative, selectedAltKey } = useFeasibilityStore()
  if (!alternatives || alternatives.length === 0) return null

  return (
    <section>
      <div className="flex items-baseline justify-between mb-1">
        <h3 className="text-sm font-semibold text-gray-800">
          이 대지에서 가능한 대안 (자동 제안)
        </h3>
        <span className="text-[10px] text-gray-400">연면적 큰 순</span>
      </div>
      <p className="text-[11px] text-gray-500 mb-3">
        통과 가능한 완화 조합을 자동으로 계산했습니다. 마음에 드는 안을 고르면 더 세밀하게 조정할 수 있습니다.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {alternatives.map((a) => {
          const b = BURDEN[a.burden_level] || BURDEN.mid
          const selected = selectedAltKey === a.key
          const delta = a.delta_floor_area_sqm
          return (
            <div
              key={a.key}
              className="border-2 rounded-xl p-3.5 bg-white flex flex-col"
              style={{ borderColor: selected ? 'var(--color-accent)' : 'var(--color-border, #e5e7eb)' }}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-bold text-gray-900">{a.label}</span>
                {selected && (
                  <span
                    className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
                    style={{ backgroundColor: 'var(--color-accent)', color: '#fff' }}
                  >
                    선택됨
                  </span>
                )}
              </div>
              <p className="text-[10px] text-gray-500 mb-2.5 leading-tight">{a.tagline}</p>

              <div className="grid grid-cols-2 gap-x-2 gap-y-1.5 mb-2.5">
                <Metric label="건폐율" v={a.building_coverage_pct} unit="%" d={1} />
                <Metric label="용적률" v={a.far_pct} unit="%" d={1} />
                <Metric
                  label="가능 연면적"
                  v={a.max_floor_area_sqm}
                  unit="㎡"
                  d={0}
                  sub={
                    delta && delta > 0
                      ? `+${fmt(delta, 0)}㎡`
                      : null
                  }
                />
                <Metric label="권장 주차" v={a.recommended_parking_spaces} unit="대" d={0} />
              </div>

              {/* 적용 완화 배지 */}
              {a.applied_relief_items?.length > 0 ? (
                <div className="flex flex-wrap gap-1 mb-2">
                  {a.applied_relief_items.map((it, i) => (
                    <span
                      key={i}
                      className="text-[10px] px-1.5 py-0.5 rounded-full"
                      style={{ backgroundColor: 'rgba(22,163,74,0.1)', color: 'var(--color-success)' }}
                    >
                      {it.label || it.kind}
                    </span>
                  ))}
                </div>
              ) : (
                <div className="text-[10px] text-gray-400 mb-2">완화 적용 없음</div>
              )}

              {/* 부담 표시 */}
              <div className="flex items-center gap-2 text-[11px] mb-3 mt-auto">
                <span style={{ color: b.color }}>
                  {b.icon} 심의 {a.review_count_required ?? 0}건
                </span>
                <span className="text-gray-400">·</span>
                <span style={{ color: b.color }}>{b.label}</span>
                {a.review_count_maybe > 0 && (
                  <span className="text-gray-400">(조건부 {a.review_count_maybe})</span>
                )}
              </div>

              <button
                onClick={() => applyAlternative(a)}
                className="w-full text-xs font-semibold py-2 rounded-lg transition-colors"
                style={
                  selected
                    ? { backgroundColor: 'var(--color-accent)', color: '#fff' }
                    : { border: '1px solid var(--color-accent)', color: 'var(--color-accent)' }
                }
              >
                {selected ? '✓ 이 안 선택됨' : '이 안으로 →'}
              </button>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function Metric({ label, v, unit, d = 0, sub = null }) {
  return (
    <div>
      <div className="text-[10px] text-gray-500">{label}</div>
      <div className="text-sm font-bold text-gray-800 leading-tight">
        {fmt(v, d)}
        {v != null && <span className="text-[11px] font-normal text-gray-500 ml-0.5">{unit}</span>}
        {sub && (
          <span className="text-[10px] font-semibold ml-1" style={{ color: 'var(--color-success)' }}>
            {sub}
          </span>
        )}
      </div>
    </div>
  )
}

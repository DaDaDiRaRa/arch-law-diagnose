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
  low: { label: '부담 낮음', color: 'var(--ok)' },
  mid: { label: '부담 보통', color: 'var(--warn-deep)' },
  high: { label: '부담 높음', color: 'var(--error)' },
}

export default function AutoAlternatives({ alternatives }) {
  const { applyAlternative, selectedAltKey } = useFeasibilityStore()
  if (!alternatives || alternatives.length === 0) return null

  return (
    <section>
      <div className="flex items-baseline justify-between mb-1">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>
          이 대지에서 가능한 대안 (자동 제안)
        </h3>
        <span className="text-[10px]" style={{ color: 'var(--faint)' }}>연면적 큰 순</span>
      </div>
      <p className="text-[11px] mb-3" style={{ color: 'var(--mute)' }}>
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
              className="border-2 p-3.5 flex flex-col"
              style={{
                borderColor: selected ? 'var(--brand)' : 'var(--hairline)',
                borderRadius: 'var(--radius)',
                background: 'var(--canvas-elevated)',
              }}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-bold" style={{ color: 'var(--ink)' }}>{a.label}</span>
                {selected && (
                  <span
                    className="text-[10px] font-semibold px-1.5 py-0.5"
                    style={{
                      backgroundColor: 'var(--brand)',
                      color: '#fff',
                      borderRadius: 'var(--radius-sm)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '10px',
                    }}
                  >
                    선택됨
                  </span>
                )}
              </div>
              <p className="text-[10px] mb-2.5 leading-tight" style={{ color: 'var(--mute)' }}>{a.tagline}</p>

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
                      className="text-[10px] px-1.5 py-0.5"
                      style={{
                        backgroundColor: 'rgba(22,163,74,0.1)',
                        color: 'var(--ok)',
                        borderRadius: 'var(--radius-pill)',
                        border: '1px solid var(--hairline)',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '10px',
                      }}
                    >
                      {it.label || it.kind}
                    </span>
                  ))}
                </div>
              ) : (
                <div className="text-[10px] mb-2" style={{ color: 'var(--faint)' }}>완화 적용 없음</div>
              )}

              {/* 부담 표시 */}
              <div className="flex items-center gap-2 text-[11px] mb-3 mt-auto">
                <span style={{ color: b.color }}>
                  심의 {a.review_count_required ?? 0}건
                </span>
                <span style={{ color: 'var(--faint)' }}>·</span>
                <span style={{ color: b.color }}>{b.label}</span>
                {a.review_count_maybe > 0 && (
                  <span style={{ color: 'var(--faint)' }}>(조건부 {a.review_count_maybe})</span>
                )}
              </div>

              {/* 산정 근거 · 심의 상세 — 펼침 */}
              <AltDetails alt={a} />

              <button
                onClick={() => applyAlternative(a)}
                className="w-full text-xs font-semibold py-2 transition-colors mt-2"
                style={
                  selected
                    ? { backgroundColor: 'var(--brand)', color: '#fff', borderRadius: 'var(--radius-sm)' }
                    : { border: '1px solid var(--brand)', color: 'var(--brand)', borderRadius: 'var(--radius-sm)' }
                }
              >
                {selected ? '이 안 선택됨' : '이 안으로 →'}
              </button>
            </div>
          )
        })}
      </div>
      <p className="text-[10px] mt-3" style={{ color: 'var(--faint)' }}>
        용적률·완화·심의 수치는 시행령·조례·고시 원문 기준 자동 산정값입니다. 「산정 근거」에서
        적용 법조문과 계산식을 확인하세요. 실제 인허가 한도는 도시계획·건축 심의로 변동될 수 있습니다.
      </p>
    </section>
  )
}

function AltDetails({ alt }) {
  const d = alt.derivation || {}
  const breakdown = d.relief_breakdown || []
  const site = d.site_area_sqm
  const baseFar = d.base_far_pct
  const finalFar = d.final_far_pct
  const cov = alt.building_coverage_pct
  const floor = alt.max_floor_area_sqm
  const buildingArea = alt.max_building_area_sqm
  const reqs = alt.review_required || []
  const maybes = alt.review_maybe || []

  return (
    <details className="mt-1 group">
      <summary
        className="text-[11px] cursor-pointer select-none list-none flex items-center gap-1"
        style={{ color: 'var(--mute)' }}
      >
        <span className="group-open:rotate-90 transition-transform inline-block">▸</span>
        산정 근거 · 심의 상세
      </summary>
      <div
        className="mt-2 space-y-2.5 text-[10px] leading-relaxed pt-2"
        style={{ borderTop: '1px solid var(--hairline)' }}
      >
        {/* 용적률 산정식 */}
        <div>
          <div className="font-semibold mb-1" style={{ color: 'var(--body)' }}>용적률 산정</div>
          <div style={{ color: 'var(--body)' }}>
            기본 한도 <b>{fmt(baseFar, 1)}%</b>
            {d.far_source && <span style={{ color: 'var(--mute)' }}> ({d.far_source})</span>}
          </div>
          {breakdown.length > 0 ? (
            <ul className="mt-0.5 space-y-0.5">
              {breakdown.map((b, i) => (
                <li key={i} className="flex gap-1.5" style={{ color: 'var(--body)' }}>
                  <span style={{ color: 'var(--ok)' }} className="font-semibold whitespace-nowrap">
                    +{fmt(b.relief_pct, 1)}%
                  </span>
                  <span>
                    {b.label}
                    {b.basis && <span style={{ color: 'var(--mute)' }}> · {b.basis}</span>}
                    {b.note && <span style={{ color: 'var(--mute)' }}> · {b.note}</span>}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="mt-0.5" style={{ color: 'var(--faint)' }}>완화 적용 없음 (기본 한도)</div>
          )}
          {d.cap_note && (
            <div className="mt-0.5" style={{ color: 'var(--mute)' }}>{d.cap_note}</div>
          )}
          <div className="font-semibold mt-1" style={{ color: 'var(--ink)' }}>
            → 최종 용적률 {fmt(finalFar, 1)}%
          </div>
        </div>

        {/* 면적 환산식 */}
        {site != null && (
          <div>
            <div className="font-semibold mb-1" style={{ color: 'var(--body)' }}>면적 환산</div>
            {finalFar != null && floor != null && (
              <div style={{ color: 'var(--body)' }}>
                연면적 = {fmt(site, 0)}㎡ × {fmt(finalFar, 1)}% ={' '}
                <b>{fmt(floor, 0)}㎡</b>
              </div>
            )}
            {cov != null && buildingArea != null && (
              <div style={{ color: 'var(--body)' }}>
                건축면적 = {fmt(site, 0)}㎡ × {fmt(cov, 1)}% = <b>{fmt(buildingArea, 0)}㎡</b>
                {d.cov_source && <span style={{ color: 'var(--mute)' }}> ({d.cov_source})</span>}
              </div>
            )}
          </div>
        )}

        {/* 심의·평가 필요 항목 */}
        <div>
          <div className="font-semibold mb-1" style={{ color: 'var(--body)' }}>
            심의·평가 필요 ({reqs.length})
          </div>
          {reqs.length > 0 ? (
            <ul className="space-y-0.5">
              {reqs.map((r, i) => (
                <li key={i} style={{ color: 'var(--body)' }}>
                  • {r.name}
                  {r.reason && <span style={{ color: 'var(--mute)' }}> — {r.reason}</span>}
                  {r.law_ref && <span style={{ color: 'var(--faint)' }}> 「{r.law_ref}」</span>}
                </li>
              ))}
            </ul>
          ) : (
            <div style={{ color: 'var(--faint)' }}>필수 심의 없음</div>
          )}
          {maybes.length > 0 && (
            <div className="mt-1">
              <span style={{ color: 'var(--mute)' }}>조건부 ({maybes.length}): </span>
              <span style={{ color: 'var(--faint)' }}>
                {maybes.map((m) => m.name).filter(Boolean).join(', ')}
              </span>
            </div>
          )}
        </div>
      </div>
    </details>
  )
}

function Metric({ label, v, unit, d = 0, sub = null }) {
  return (
    <div>
      <div className="text-[10px]" style={{ color: 'var(--mute)' }}>{label}</div>
      <div className="text-sm font-bold leading-tight" style={{ color: 'var(--ink)' }}>
        {fmt(v, d)}
        {v != null && <span className="text-[11px] font-normal ml-0.5" style={{ color: 'var(--mute)' }}>{unit}</span>}
        {sub && (
          <span className="text-[10px] font-semibold ml-1" style={{ color: 'var(--ok)' }}>
            {sub}
          </span>
        )}
      </div>
    </div>
  )
}

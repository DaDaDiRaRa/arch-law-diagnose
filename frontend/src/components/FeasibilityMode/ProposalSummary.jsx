/**
 * 제안 우선 요약 — 공모 요구치(target)와 무관하게 이 대지의 가능 범위를 먼저 제시.
 *
 * target을 안 넣어도 "최대 건폐율·용적률·가능 연면적·권장 주차대수"를 카드로 표시.
 */
const fmt = (v, digits = 0) =>
  v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: digits })

export default function ProposalSummary({ proposal }) {
  if (!proposal) return null

  const {
    max_building_coverage_pct,
    max_building_area_sqm,
    base_far_pct,
    max_far_pct_relief,
    max_floor_area_sqm,
    max_floor_area_relief_sqm,
    recommended_parking_spaces,
    parking_basis_floor_area_sqm,
  } = proposal

  const hasFarRelief =
    max_far_pct_relief != null &&
    base_far_pct != null &&
    max_far_pct_relief > base_far_pct

  return (
    <section>
      <h3 className="text-sm font-semibold text-gray-800 mb-1">
        이 대지에 지을 수 있는 범위
      </h3>
      <p className="text-[11px] text-gray-500 mb-3">
        공모 요구치 입력과 무관하게, 법규상 가능한 최대치와 권장값을 먼저 보여줍니다.
      </p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card
          title="최대 건폐율"
          main={max_building_coverage_pct != null ? `${fmt(max_building_coverage_pct, 1)}%` : '확인 불가'}
          sub={
            max_building_area_sqm != null
              ? `최대 건축면적 ${fmt(max_building_area_sqm)}㎡`
              : '용도지역 한도 미확인'
          }
        />
        <Card
          title="최대 용적률"
          main={base_far_pct != null ? `${fmt(base_far_pct, 1)}%` : '확인 불가'}
          sub={
            hasFarRelief
              ? `완화 적용 시 최대 ${fmt(max_far_pct_relief, 1)}%`
              : '완화 여지 없음 / 미확인'
          }
          accent={hasFarRelief ? 'var(--color-success)' : undefined}
        />
        <Card
          title="가능 연면적"
          main={max_floor_area_sqm != null ? `${fmt(max_floor_area_sqm)}㎡` : '확인 불가'}
          sub={
            max_floor_area_relief_sqm != null && max_floor_area_relief_sqm > (max_floor_area_sqm || 0)
              ? `완화 시 ${fmt(max_floor_area_relief_sqm)}㎡`
              : '용적률 한도 기준'
          }
          accent={
            max_floor_area_relief_sqm != null && max_floor_area_relief_sqm > (max_floor_area_sqm || 0)
              ? 'var(--color-success)'
              : undefined
          }
        />
        <Card
          title="권장 주차대수"
          main={recommended_parking_spaces != null ? `${fmt(recommended_parking_spaces)}대` : '확인 필요'}
          sub={
            parking_basis_floor_area_sqm != null
              ? `최대 연면적 ${fmt(parking_basis_floor_area_sqm)}㎡ 기준`
              : '연면적 산정 필요'
          }
        />
      </div>
    </section>
  )
}

function Card({ title, main, sub, accent }) {
  return (
    <div className="border border-gray-200 rounded-lg p-3 bg-white">
      <div className="text-[10px] uppercase text-gray-500 font-medium mb-1">
        {title}
      </div>
      <div
        className="text-lg font-bold"
        style={{ color: accent || 'var(--color-text-body)' }}
      >
        {main}
      </div>
      <div className="text-[10px] text-gray-500 mt-0.5 leading-tight">{sub}</div>
    </div>
  )
}

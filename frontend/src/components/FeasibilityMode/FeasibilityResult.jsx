import { useFeasibilityStore } from '../../stores/feasibilityStore'
import GapChart from './GapChart'
import ScenarioRecommender from './ScenarioRecommender'
import ReviewBurdenCard from './ReviewBurdenCard'

const VERDICT_COLOR = {
  '참여 권장': 'var(--color-success)',
  '협상 필요': 'var(--color-warning)',
  '패스 권장': 'var(--color-danger)',
  '정보 부족': 'var(--color-text-faint)',
}

const VERDICT_BG = {
  '참여 권장': 'rgba(22, 163, 74, 0.08)',
  '협상 필요': 'rgba(202, 138, 4, 0.08)',
  '패스 권장': 'rgba(220, 38, 38, 0.08)',
  '정보 부족': 'rgba(108, 117, 125, 0.08)',
}

export default function FeasibilityResult() {
  const { result, reset } = useFeasibilityStore()
  if (!result) return null

  const verdict = result.overall_recommendation?.verdict || '정보 부족'
  const reason = result.overall_recommendation?.reason || ''
  const color = VERDICT_COLOR[verdict] || VERDICT_COLOR['정보 부족']
  const bg = VERDICT_BG[verdict] || VERDICT_BG['정보 부족']

  const hasOverCategories = result.categories?.some(
    (c) => c.gap_analysis?.status === 'over'
  )

  return (
    <div className="space-y-5">
      {/* 종합 판단 배너 */}
      <div
        className="rounded-xl p-5 border-2"
        style={{ borderColor: color, backgroundColor: bg }}
      >
        <div className="flex items-baseline justify-between mb-2">
          <div>
            <div className="text-[10px] uppercase font-bold tracking-wider text-gray-500 mb-1">
              종합 판단
            </div>
            <h2 className="text-xl font-bold" style={{ color }}>
              {verdict}
            </h2>
          </div>
          <button
            onClick={reset}
            className="text-xs text-gray-600 hover:text-gray-900 border border-gray-300 rounded px-3 py-1.5 hover:bg-white transition-colors"
          >
            ↺ 새 검토
          </button>
        </div>
        <p className="text-sm text-gray-700">{reason}</p>
      </div>

      {/* 대지 정보 요약 */}
      <div className="border border-gray-200 rounded-lg p-4 bg-white">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">대지 정보</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <Fact label="주소" value={result.address} span={4} />
          <Fact label="용도지역" value={result.land_facts?.zone_use || '미확인'} />
          <Fact label="지역지구" value={result.land_facts?.zone_district || '—'} />
          <Fact
            label="대지면적"
            value={
              result.site_area_used
                ? `${Number(result.site_area_used).toLocaleString()}㎡`
                : '—'
            }
          />
          <Fact
            label="조회"
            value={
              result.site_area_source === 'auto'
                ? '자동'
                : result.site_area_source === 'user_override'
                ? '수동'
                : '기본값(1000㎡)'
            }
          />
        </div>
      </div>

      {/* 갭 분석 */}
      <section>
        <h3 className="text-sm font-semibold text-gray-800 mb-3">
          갭 분석 — 공모 요구 vs 법적 가능
        </h3>
        <GapChart categories={result.categories || []} />
      </section>

      {/* 완화 시나리오 — over 카테고리 있을 때만 */}
      {hasOverCategories && (
        <section>
          <h3 className="text-sm font-semibold text-gray-800 mb-3">
            완화 시나리오 추천
          </h3>
          <ScenarioRecommender categories={result.categories || []} />
        </section>
      )}

      {/* 심의 부담 */}
      <section>
        <ReviewBurdenCard reviewBurden={result.review_burden} />
      </section>

      {/* 데이터 품질 */}
      {result.data_quality?.issues?.length > 0 && (
        <section>
          <details className="border border-gray-200 rounded-lg p-3 bg-gray-50">
            <summary className="text-xs font-medium text-gray-700 cursor-pointer">
              데이터 품질 알림 ({result.data_quality.issues.length})
            </summary>
            <ul className="mt-2 space-y-1 text-[11px] text-gray-600">
              {result.data_quality.issues.map((iss, idx) => (
                <li key={idx} className="flex gap-2">
                  <span className="font-mono text-gray-400">[{iss.level}]</span>
                  <span>{iss.msg}</span>
                </li>
              ))}
            </ul>
          </details>
        </section>
      )}

      <div className="text-[10px] text-gray-400 text-center pt-4 border-t border-gray-200">
        사전 사업성 검토는 참여 판단 보조용입니다. 실제 인허가 가능성은 시니어 검토가 필수입니다.
      </div>
    </div>
  )
}

function Fact({ label, value, span = 1 }) {
  return (
    <div className={span > 1 ? `col-span-${span}` : ''}>
      <div className="text-[10px] uppercase text-gray-500 font-medium mb-0.5">
        {label}
      </div>
      <div className="text-xs text-gray-800">{value}</div>
    </div>
  )
}

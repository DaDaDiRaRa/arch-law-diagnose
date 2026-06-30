import { useState } from 'react'
import { api } from '../../utils/api'
import { useFeasibilityStore } from '../../stores/feasibilityStore'
import ProposalSummary from './ProposalSummary'
import AutoAlternatives from './AutoAlternatives'
import FeasibilityWhatIf from './FeasibilityWhatIf'
import GapChart from './GapChart'
import ScenarioRecommender from './ScenarioRecommender'
import ReviewBurdenCard from './ReviewBurdenCard'

const VERDICT_COLOR = {
  '참여 권장': 'var(--ok)',
  '협상 필요': 'var(--warn-deep)',
  '패스 권장': 'var(--error)',
  '정보 부족': 'var(--mute)',
}

export default function FeasibilityResult() {
  const { result, reset, whatifOpen, openWhatif, formData, briefApplied } =
    useFeasibilityStore()
  const [exporting, setExporting] = useState(null)
  if (!result) return null

  const exportPayload = () => ({
    result,
    form_data: formData,
    project_name: briefApplied?.competition_name || '',
  })

  const handleExport = async (format) => {
    setExporting(format)
    try {
      if (format === 'html') {
        await api.openFeasibilityHtml(exportPayload())
      } else {
        await api.downloadFeasibilityExport(format, exportPayload())
      }
    } catch (e) {
      alert(`다운로드 실패: ${e.message || e}`)
    } finally {
      setExporting(null)
    }
  }

  const verdict = result.overall_recommendation?.verdict || '정보 부족'
  const reason = result.overall_recommendation?.reason || ''
  const color = VERDICT_COLOR[verdict] || VERDICT_COLOR['정보 부족']

  const hasOverCategories = result.categories?.some(
    (c) => c.gap_analysis?.status === 'over'
  )
  const hasAnyTarget = result.categories?.some(
    (c) => c.gap_analysis?.has_target
  )

  return (
    <div className="space-y-5">
      {/* 종합 판단 배너 */}
      <div className="p-5" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:`4px solid ${color}`,backgroundColor:'var(--canvas-elevated)'}}>
        <div className="flex items-baseline justify-between mb-2">
          <div>
            <div className="text-[10px] uppercase font-bold mb-1" style={{color:'var(--mute)',fontFamily:'var(--font-mono)',letterSpacing:'0.08em'}}>
              종합 판단
            </div>
            <h2 className="text-xl font-semibold" style={{color,fontFamily:'var(--font-sans)',letterSpacing:'-0.02em'}}>
              {verdict}
            </h2>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => handleExport('html')}
              disabled={!!exporting}
              className="text-xs px-3 py-1.5 transition-colors disabled:opacity-50"
              style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--body)',backgroundColor:'var(--canvas)',fontFamily:'var(--font-sans)'}}
            >
              {exporting === 'html' ? '…' : 'HTML'}
            </button>
            <button
              onClick={() => handleExport('md')}
              disabled={!!exporting}
              className="text-xs px-3 py-1.5 transition-colors disabled:opacity-50"
              style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--body)',backgroundColor:'var(--canvas)',fontFamily:'var(--font-sans)'}}
            >
              {exporting === 'md' ? '…' : 'MD'}
            </button>
            <button
              onClick={() => handleExport('xlsx')}
              disabled={!!exporting}
              className="text-xs px-3 py-1.5 transition-colors disabled:opacity-50"
              style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--body)',backgroundColor:'var(--canvas)',fontFamily:'var(--font-sans)'}}
            >
              {exporting === 'xlsx' ? '…' : 'Excel'}
            </button>
            <button
              onClick={reset}
              className="text-xs px-3 py-1.5 transition-colors"
              style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--body)',backgroundColor:'var(--canvas)',fontFamily:'var(--font-sans)'}}
            >
              ↺ 새 검토
            </button>
          </div>
        </div>
        <p className="text-sm" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>{reason}</p>
      </div>

      {/* 대지 정보 요약 */}
      <div className="p-4" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas-elevated)'}}>
        <h3 className="text-sm font-semibold mb-3" style={{color:'var(--ink)',fontFamily:'var(--font-sans)',letterSpacing:'-0.02em'}}>대지 정보</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <Fact label="주소" value={result.address} span={4} />
          <Fact label="용도지역" value={result.land_facts?.zone_use || '미확인'} />
          <Fact label="지역지구" value={result.land_facts?.zone_district || '—'} />
          <Fact
            label="대지면적"
            value={result.site_area_used ? `${Number(result.site_area_used).toLocaleString()}㎡` : '—'}
          />
          <Fact
            label="조회"
            value={result.site_area_source === 'auto' ? '자동' : result.site_area_source === 'user_override' ? '수동' : '기본값(1000㎡)'}
          />
        </div>
      </div>

      {/* 제안 우선 */}
      <ProposalSummary proposal={result.proposal} />

      {/* 자동 제안 대안 */}
      <AutoAlternatives alternatives={result.auto_alternatives} />

      {/* What-If 진입 */}
      {!whatifOpen && (
        <button
          onClick={openWhatif}
          className="w-full text-xs font-semibold py-2.5 transition-colors"
          style={{borderRadius:'var(--radius-sm)',border:`2px dashed var(--brand)`,color:'var(--brand)',backgroundColor:'transparent',fontFamily:'var(--font-sans)'}}
        >
          직접 조정하기 — 완화·용도를 손수 바꿔 비교(What-If)
        </button>
      )}
      <FeasibilityWhatIf />

      {/* 갭 분석 */}
      {hasAnyTarget ? (
        <section>
          <h3 className="text-sm font-semibold mb-3" style={{color:'var(--ink)',fontFamily:'var(--font-sans)',letterSpacing:'-0.02em'}}>
            갭 분석 — 공모 요구 vs 법적 가능
          </h3>
          <GapChart categories={result.categories || []} />
        </section>
      ) : (
        <div className="text-[11px] px-4 py-3" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)',color:'var(--mute)'}}>
          공모 요구치(연면적·용적률·주차 등)를 입력하면 위 가능 범위와 자동 비교한 갭 분석이 표시됩니다.
        </div>
      )}

      {/* 완화 시나리오 */}
      {hasOverCategories && (
        <section>
          <h3 className="text-sm font-semibold mb-3" style={{color:'var(--ink)',fontFamily:'var(--font-sans)',letterSpacing:'-0.02em'}}>
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
          <details className="p-3" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)'}}>
            <summary className="text-xs font-medium cursor-pointer" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>
              데이터 품질 알림 ({result.data_quality.issues.length})
            </summary>
            <ul className="mt-2 space-y-1 text-[11px]" style={{color:'var(--body)'}}>
              {result.data_quality.issues.map((iss, idx) => (
                <li key={idx} className="flex gap-2">
                  <span style={{fontFamily:'var(--font-mono)',color:'var(--mute)'}}>[{iss.level}]</span>
                  <span>{iss.msg}</span>
                </li>
              ))}
            </ul>
          </details>
        </section>
      )}

      <div className="text-[10px] text-center pt-4" style={{color:'var(--faint)',borderTop:'1px solid var(--hairline)',fontFamily:'var(--font-mono)'}}>
        사전 사업성 검토는 참여 판단 보조용입니다. 실제 인허가 가능성은 시니어 검토가 필수입니다.
      </div>
    </div>
  )
}

function Fact({ label, value, span = 1 }) {
  return (
    <div className={span > 1 ? `col-span-${span}` : ''}>
      <div className="text-[10px] uppercase font-medium mb-0.5" style={{color:'var(--mute)',fontFamily:'var(--font-mono)',letterSpacing:'0.06em'}}>
        {label}
      </div>
      <div className="text-xs" style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}}>{value}</div>
    </div>
  )
}

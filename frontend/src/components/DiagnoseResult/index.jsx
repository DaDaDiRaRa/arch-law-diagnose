import { useState } from 'react'
import { useDiagnoseStore } from '../../stores/diagnoseStore'
import { api } from '../../utils/api'
import { graphSearchUrl } from '../../utils/graphLink'
import DataQualityBanner from '../DataQualityBanner'
import DevTrendPanel from '../DevTrendPanel'
import LawChangeAlert from '../LawChangeAlert'
import LawGraphPanel from '../LawGraphPanel'
import LawInfoPanel from '../LawInfoPanel'
import LegalReviewReport from '../LegalReviewReport'
import ReviewRequestButton from '../ReviewRequestButton'
import WhatIfPanel from '../WhatIfPanel'
import WhatIfErrorBoundary from '../WhatIfPanel/ErrorBoundary'

const CATEGORY_LABELS = {
  행위제한: '행위제한 적합성',
  도시계획시설: '도시계획시설 저촉',
  건폐율: '건폐율',
  용적률: '용적률',
  높이_일조: '높이·일조',
  주차: '주차',
  조경: '조경',
  설비_소방: '설비·소방',
  공공시설_의무인증: '공공시설 의무 인증',
  BF_인증: 'BF 인증 (무장애)',
  범죄예방_건축기준: '범죄예방 건축기준',
  다중이용건축물: '다중이용건축물 분류',
  중첩지구_구역: '중첩 지구·구역',
  철도보호지구: '철도보호지구 (30m)',
}

// 진단 카테고리 → 법규 그래프 노드 id (있는 것만 "관계" 버튼 노출)
const CATEGORY_NODE = {
  행위제한: 'cat_landuse',
  도시계획시설: 'cat_urban',
  건폐율: 'cat_bcr',
  용적률: 'cat_far',
  높이_일조: 'cat_height',
  주차: 'cat_parking',
  조경: 'cat_landscape',
  설비_소방: 'cat_fire',
  BF_인증: 'cat_bf',
  범죄예방_건축기준: 'cat_crime',
}

const CONFIDENCE_STARS = (n) => {
  if (n === null || n === undefined) return '★☆☆☆☆'
  const filled = '★'.repeat(Math.min(n, 5))
  const empty = '☆'.repeat(Math.max(0, 5 - n))
  return filled + empty
}

const SIGNAL_CONFIG = {
  GREEN:  { dotColor: 'var(--ok)',    statusColor: 'var(--ok)',    label: '적합' },
  YELLOW: { dotColor: 'var(--warn)',  statusColor: 'var(--warn)',  label: '주의 필요' },
  RED:    { dotColor: 'var(--error)', statusColor: 'var(--error)', label: '부적합' },
}

export default function DiagnoseResult() {
  const { result: rawResult, error, loading, reset, formData } = useDiagnoseStore()
  const [reportOpen, setReportOpen] = useState(false)
  const [downloading, setDownloading] = useState(null)  // 'md' | 'xlsx' | null
  const [graphFocus, setGraphFocus] = useState(null)    // 카테고리 → 법규 그래프 점프 (#3)
  const showGraph = (nodeId) => setGraphFocus({ id: nodeId, ts: Date.now() })

  const handleDownload = async (format) => {
    if (downloading || !rawResult) return
    setDownloading(format)
    try {
      await api.downloadDiagnoseExport(format, {
        result: rawResult,
        form_data: formData || {},
        project_name: '',
        company: '',
        author: '',
      })
    } catch (e) {
      alert(`${format.toUpperCase()} 다운로드 실패: ${e.message}`)
    } finally {
      setDownloading(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center space-y-3">
          <div style={{width:24,height:24,border:'3px solid var(--hairline)',borderTopColor:'var(--brand)',borderRadius:'50%',animation:'spin 0.8s linear infinite',margin:'0 auto'}} />
          <p className="text-sm" style={{color:'var(--mute)'}}>법규 데이터 조회 중...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-5" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--error)',backgroundColor:'var(--canvas-elevated)'}}>
        <p className="font-semibold mb-1" style={{color:'var(--error)'}}>오류 발생</p>
        <p className="text-sm whitespace-pre-line" style={{color:'var(--body)'}}>{error}</p>
        <button onClick={reset} className="mt-3 text-xs underline" style={{color:'var(--mute)'}}>다시 시도</button>
      </div>
    )
  }

  if (!rawResult) return null

  // 합필 모드면 내부 result 를 펼쳐서 사용, 단일 모드면 그대로 사용
  const isMulti = rawResult.mode === 'multi_parcel'
  const result = isMulti ? rawResult.result : rawResult
  const multiInfo = isMulti
    ? { parcels: rawResult.parcels, aggregate: rawResult.aggregate }
    : null

  const sig = SIGNAL_CONFIG[result.signal] || SIGNAL_CONFIG.YELLOW
  const categories = Object.entries(result.results || {})

  // ReviewRequestButton 에 전달할 공통 컨텍스트
  const reviewBase = {
    address: result.address || formData?.address || '',
    building_info: buildBuildingInfo(formData),
    signal: result.signal,
    overall_score: result.overall_score,
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[295px_minmax(0,1fr)] gap-5 items-start">
      {/* ── 좌측: 종합진단 + What-if (sticky) ──────────────── */}
      <div className="space-y-5 xl:sticky xl:top-4">
      {/* Phase 4 — 법규 변경 배너 + Phase 2 — 토지이음 행정 고시 (최상단) */}
      <LawChangeAlert areaCd={(result.land_info?.pnu || '').slice(0, 5)} />

      {/* 데이터 품질 배너 */}
      <DataQualityBanner dataQuality={result.data_quality} />

      {/* 합필 진단 — 필지별 내역 + 합산 정보 */}
      {multiInfo && <MultiParcelSummary info={multiInfo} />}

      {/* 종합 판정 */}
      <div className="p-5" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:`4px solid ${sig.statusColor}`,backgroundColor:'var(--canvas-elevated)',boxShadow:'var(--shadow-sm)'}}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div style={{width:8,height:8,borderRadius:'50%',backgroundColor:sig.dotColor,flexShrink:0}} />
            <div>
              <p className="text-xs mb-0.5" style={{color:'var(--mute)',fontFamily:'var(--font-mono)',textTransform:'uppercase',letterSpacing:'0.06em'}}>종합 진단</p>
              <p className="text-xl font-semibold" style={{color:sig.statusColor,fontFamily:'var(--font-sans)',letterSpacing:'-0.02em'}}>
                {sig.label}
              </p>
            </div>
          </div>
          {result.overall_score !== null && result.overall_score !== undefined && (
            <div className="text-right">
              <p className="text-xs mb-0.5" style={{color:'var(--mute)'}}>종합 점수</p>
              <p className="text-3xl font-semibold" style={{color:sig.statusColor,fontFamily:'var(--font-sans)'}}>
                {result.overall_score.toFixed(1)}
                <span className="text-base font-normal" style={{color:'var(--faint)'}}>/10</span>
              </p>
            </div>
          )}
        </div>
        <div className="mt-3 pt-3 space-y-2" style={{borderTop:'1px solid var(--hairline)'}}>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setReportOpen(true)}
              className="text-xs font-medium px-3 py-1.5 transition-colors"
              style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--body)',backgroundColor:'var(--canvas-elevated)',fontFamily:'var(--font-sans)'}}
            >
              법규 검토서
            </button>
            <button
              onClick={() => handleDownload('md')}
              disabled={downloading === 'md'}
              className="text-xs font-medium px-3 py-1.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--body)',backgroundColor:'var(--canvas-elevated)',fontFamily:'var(--font-sans)'}}
            >
              {downloading === 'md' ? '생성중...' : 'MD'}
            </button>
            <button
              onClick={() => handleDownload('xlsx')}
              disabled={downloading === 'xlsx'}
              className="text-xs font-medium px-3 py-1.5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--body)',backgroundColor:'var(--canvas-elevated)',fontFamily:'var(--font-sans)'}}
            >
              {downloading === 'xlsx' ? '생성중...' : 'Excel'}
            </button>
          </div>
          <p className="text-xs" style={{color:'var(--faint)'}}>
            검토서: 브라우저 인쇄로 PDF · MD/Excel: 진단 결과 텍스트 다운로드
          </p>
        </div>
      </div>

      {/* What-if 시나리오 — 종합 판정 바로 아래에 배치해 즉시 발견 가능 */}
      {!isMulti && (
        <WhatIfErrorBoundary>
          <WhatIfPanel />
        </WhatIfErrorBoundary>
      )}

      {/* 법규 검토서 모달 */}
      {reportOpen && (
        <LegalReviewReport
          rawResult={rawResult}
          formData={formData}
          onClose={() => setReportOpen(false)}
        />
      )}
      </div>

      {/* ── 우측: 상세 정보 — 내부에서 다시 2-col 분할 ──────── */}
      <div className="grid grid-cols-1 2xl:grid-cols-2 gap-5 items-start">

        {/* 우측-A: 액션 필요한 카드 (심의·위험·검토필요·수동검토) */}
        <div className="space-y-5">
          {/* 8개 심의 자동 트리거 */}
          {result.applicable_reviews?.items?.length > 0 && (
            <ApplicableReviewsCard reviews={result.applicable_reviews} />
          )}

          {/* 위험 항목 + 시니어 검토 요청 버튼 */}
          {result.risks && result.risks.length > 0 && (
            <div className="p-4 space-y-3" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--error)',backgroundColor:'var(--canvas-elevated)'}}>
              <p className="text-xs font-semibold" style={{color:'var(--error)',fontFamily:'var(--font-mono)',textTransform:'uppercase',letterSpacing:'0.06em'}}>위험 항목 ({result.risks.length}건)</p>
              {result.risks.map((r, i) => (
                <div key={i} className="pl-3" style={{borderLeft:'2px solid var(--error)'}}>
                  <div className="text-sm" style={{color:'var(--body)'}}>
                    <span className="font-medium" style={{color:'var(--ink)'}}>{r.category}:</span> {r.reason}
                  </div>
                  <ReviewRequestButton
                    context={{
                      ...reviewBase,
                      risk_category: r.category,
                      risk_reason: r.reason,
                    }}
                  />
                </div>
              ))}
            </div>
          )}

          {/* 주의 항목 */}
          {result.warnings && result.warnings.length > 0 && (
            <div className="p-4 space-y-2" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--warn)',backgroundColor:'var(--canvas-elevated)'}}>
              <p className="text-xs font-semibold" style={{color:'var(--warn-deep)',fontFamily:'var(--font-mono)',textTransform:'uppercase',letterSpacing:'0.06em'}}>검토 필요 ({result.warnings.length}건)</p>
              {result.warnings.map((w, i) => (
                <div key={i} className="text-sm" style={{color:'var(--body)'}}>
                  <span className="font-medium" style={{color:'var(--ink)'}}>{w.category}:</span> {w.reason}
                </div>
              ))}
            </div>
          )}

          {/* 필수 수동검토 항목 (높이·일조 등) */}
          {(() => {
            const manualItems = Object.entries(result.results || {})
              .filter(([_, c]) => c.needs_manual_review)
            if (manualItems.length === 0) return null
            return (
              <div className="p-4 space-y-2" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--warn)',backgroundColor:'var(--canvas-elevated)'}}>
                <p className="text-xs font-semibold" style={{color:'var(--warn-deep)',fontFamily:'var(--font-mono)',textTransform:'uppercase',letterSpacing:'0.06em'}}>
                  필수 수동검토 ({manualItems.length}건) — 입력값 부족으로 자동 판정 불가
                </p>
                {manualItems.map(([key, c]) => (
                  <div key={key} className="text-xs pl-2" style={{borderLeft:'2px solid var(--warn)',color:'var(--body)'}}>
                    <span className="font-medium" style={{color:'var(--ink)'}}>{CATEGORY_LABELS[key] || key}:</span> {c.notes}
                  </div>
                ))}
                <p className="text-[10px] leading-relaxed mt-1" style={{color:'var(--mute)'}}>
                  입력 폼의 "높이·일조 판정" 섹션에 정북 이격거리 등을 입력하면 자동 판정됩니다.
                </p>
              </div>
            )
          })()}
        </div>

        {/* 우측-B: 참고 정보 (토지정보·법령본문·카테고리 상세·케이스) */}
        <div className="space-y-5">
          {/* 토지 정보 */}
          {result.land_info && (
            <LandInfoCard info={result.land_info} />
          )}

          {/* 토지이음 법령 본문 (Phase 1) */}
          {result.land_info?.zone_use && (
            <LawInfoPanel
              areaCd={(result.land_info?.pnu || '').slice(0, 5)}
              zoneUse={result.land_info?.zone_use}
              zoneDistrict={result.land_info?.zone_district}
            />
          )}

          {/* 주변 개발 인허가 동향 (Phase 3) */}
          {result.land_info?.pnu && (
            <DevTrendPanel areaCd={(result.land_info?.pnu || '').slice(0, 5)} />
          )}

          {/* 대지면적 자동 보정 (도시계획시설 저촉) */}
          {result.site_correction?.applied && (
            <SiteCorrectionCard correction={result.site_correction} />
          )}

          {/* 카테고리별 상세 */}
          <div>
            <p className="text-xs font-semibold mb-3 uppercase" style={{color:'var(--mute)',fontFamily:'var(--font-mono)',letterSpacing:'0.06em'}}>카테고리별 상세</p>
            <div className="grid grid-cols-1 2xl:grid-cols-2 gap-3">
              {categories.map(([key, cat]) => {
                const reliefSuffix = cat.relief_info?.applied ? ' (완화)' : ''
                return (
                  <CategoryCard
                    key={key}
                    label={(CATEGORY_LABELS[key] || key) + reliefSuffix}
                    cat={cat}
                    nodeId={CATEGORY_NODE[key]}
                    onShowGraph={showGraph}
                  />
                )
              })}
            </div>
          </div>

          {/* 법규 관계 그래프 (Step 11) */}
          <LawGraphPanel focus={graphFocus} />

        </div>
      </div>
    </div>
  )
}

function buildBuildingInfo(fd) {
  if (!fd) return undefined
  const above = parseFloat(fd.floor_area_above) || 0
  const below = parseFloat(fd.floor_area_below) || 0
  const parking = parseFloat(fd.floor_area_parking_above) || 0
  const refuge = parseFloat(fd.floor_area_refuge) || 0
  const atticRefuge = parseFloat(fd.floor_area_attic_refuge) || 0
  const totalFloor = above + below
  let yearArea = ''
  if (totalFloor > 0) {
    yearArea = below > 0 ? `${totalFloor}㎡ (지상 ${above}㎡ + 지하 ${below}㎡)` : `${totalFloor}㎡`
  }
  const obj = {
    용도: fd.building_use,
    대지면적: fd.site_area && `${fd.site_area}㎡`,
    건축면적: fd.building_area && `${fd.building_area}㎡`,
    연면적: yearArea,
    지상주차장: parking > 0 ? `${parking}㎡ (용적률 제외)` : '',
    피난안전구역: refuge > 0 ? `${refuge}㎡ (용적률 제외)` : '',
    경사지붕대피공간: atticRefuge > 0 ? `${atticRefuge}㎡ (용적률 제외)` : '',
    층수: fd.floors_above && `지상${fd.floors_above}/지하${fd.floors_below || 0}`,
    높이: fd.height && `${fd.height}m`,
  }
  return Object.fromEntries(Object.entries(obj).filter(([_, v]) => v))
}

function SiteCorrectionCard({ correction }) {
  const {
    source, original_m2, excluded_m2, effective_m2,
    note, by_facility = [], overlap_info,
  } = correction
  const isManual = source === 'manual'
  const pct = original_m2 ? ((excluded_m2 / original_m2) * 100).toFixed(1) : '0.0'

  return (
    <div className="p-4 space-y-2" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--info)',backgroundColor:'var(--canvas-elevated)'}}>
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase" style={{color:'var(--ink)',fontFamily:'var(--font-mono)',letterSpacing:'0.06em'}}>
          대지면적 자동 보정 (도시계획시설 저촉)
        </p>
        <span className="text-[10px] px-2 py-0.5 font-medium" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--body)',fontFamily:'var(--font-mono)'}}>
          {isManual ? '수동 지정' : '자동 (VWorld×SHP)'}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="p-2" style={{backgroundColor:'var(--canvas)',borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)'}}>
          <p style={{color:'var(--mute)'}}>입력 대지면적</p>
          <p className="font-semibold text-sm mt-0.5" style={{color:'var(--ink)'}}>{original_m2?.toLocaleString()}㎡</p>
        </div>
        <div className="p-2" style={{backgroundColor:'var(--canvas)',borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)'}}>
          <p style={{color:'var(--mute)'}}>시설부지 제외</p>
          <p className="font-semibold text-sm mt-0.5" style={{color:'var(--error)'}}>-{excluded_m2?.toLocaleString()}㎡ ({pct}%)</p>
        </div>
        <div className="p-2" style={{backgroundColor:'var(--canvas)',borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)'}}>
          <p style={{color:'var(--mute)'}}>유효 대지면적</p>
          <p className="font-semibold text-sm mt-0.5" style={{color:'var(--ok)'}}>{effective_m2?.toLocaleString()}㎡</p>
        </div>
      </div>
      <p className="text-xs leading-relaxed" style={{color:'var(--body)'}}>{note}</p>
      {by_facility.length > 0 && (
        <details className="text-xs" style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius-sm)'}}>
          <summary className="cursor-pointer px-2 py-1.5" style={{color:'var(--body)'}}>
            저촉 시설 내역 ({by_facility.length}건) ▾
          </summary>
          <ul className="px-2 pb-2 space-y-0.5">
            {by_facility.slice(0, 8).map((f, i) => (
              <li key={i} className="flex justify-between gap-2" style={{color:'var(--body)'}}>
                <span className="truncate">{f.category}{f.facility_name ? ` — ${f.facility_name}` : ''}</span>
                <span className="flex-shrink-0" style={{color:'var(--mute)'}}>{f.area_m2?.toLocaleString()}㎡</span>
              </li>
            ))}
            {by_facility.length > 8 && <li style={{color:'var(--mute)'}}>외 {by_facility.length - 8}건</li>}
          </ul>
        </details>
      )}
      <p className="text-[10px] leading-relaxed" style={{color:'var(--faint)'}}>
        자동 보정은 추정이며, 실제 도면(지적도·도시계획시설 결정고시)에서 확인 후 시설부지 면적을 직접 입력하시면 재산정됩니다.
      </p>
    </div>
  )
}

const REVIEW_SEVERITY_STYLE = {
  REQUIRED: { dotColor: 'var(--error)', badge: '필요' },
  MAYBE:    { dotColor: 'var(--warn)',  badge: '검토' },
  NONE:     { dotColor: 'var(--faint)', badge: '해당없음' },
}

function ApplicableReviewsCard({ reviews }) {
  const { items = [], required_count = 0, maybe_count = 0 } = reviews
  return (
    <div className="p-4 space-y-3" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--info)',backgroundColor:'var(--canvas-elevated)'}}>
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase" style={{color:'var(--ink)',fontFamily:'var(--font-mono)',letterSpacing:'0.06em'}}>
          인허가 심의 트리거 (8개 검사)
        </p>
        <div className="flex gap-2 text-xs">
          {required_count > 0 && (
            <span className="px-2 py-0.5 font-medium" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--error)',fontFamily:'var(--font-mono)',fontSize:'11px'}}>
              필요 {required_count}건
            </span>
          )}
          {maybe_count > 0 && (
            <span className="px-2 py-0.5 font-medium" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--warn-deep)',fontFamily:'var(--font-mono)',fontSize:'11px'}}>
              검토 {maybe_count}건
            </span>
          )}
          {required_count === 0 && maybe_count === 0 && (
            <span className="px-2 py-0.5 font-medium" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--ok)',fontFamily:'var(--font-mono)',fontSize:'11px'}}>
              모두 해당없음
            </span>
          )}
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {items.map((it, i) => {
          const s = REVIEW_SEVERITY_STYLE[it.severity] || REVIEW_SEVERITY_STYLE.NONE
          return (
            <div key={i} className="p-2.5 text-xs space-y-1" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:`3px solid ${s.dotColor}`,backgroundColor:'var(--canvas)'}}>
              <div className="flex items-center justify-between">
                <span className="font-semibold" style={{color:'var(--ink)'}}>
                  {it.name}
                </span>
                <span className="px-1.5 py-0.5 font-medium" style={{fontSize:'10px',borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--body)',fontFamily:'var(--font-mono)'}}>
                  {s.badge}
                </span>
              </div>
              {it.triggered_reasons?.length > 0 && (
                <ul className="pl-3 space-y-0.5" style={{color:'var(--body)'}}>
                  {it.triggered_reasons.map((r, j) => (
                    <li key={j} className="list-disc">{r}</li>
                  ))}
                </ul>
              )}
              {it.note && (
                <p className="leading-relaxed" style={{color:'var(--mute)',fontSize:'11px'}}>{it.note}</p>
              )}
              {it.law_ref && (
                <a
                  href={it.law_ref_url || '#'}
                  target="_blank"
                  rel="noreferrer"
                  className="hover:underline inline-block"
                  style={{fontSize:'10px',color:'var(--link)'}}
                >
                  {it.law_ref}
                </a>
              )}
            </div>
          )
        })}
      </div>
      <p className="text-[10px] leading-relaxed" style={{color:'var(--mute)'}}>
        트리거 룰은 일반 기준이며, 지자체 조례·세부 조건에 따라 추가 심의가 있을 수 있습니다.
        교육환경·문화재는 좌표 기반 정밀 판정 미지원 — 토지이음 및 교육청·국가유산청 확인 권장.
      </p>
    </div>
  )
}

const CALC_MODE_BADGE = {
  same_zone:  '동일 용도지역',
  small_part: '소규모 예외',
  weighted:   '면적 안분 (가중평균)',
}

function MultiParcelSummary({ info }) {
  const { parcels = [], aggregate = {} } = info
  const mode = aggregate.calc_mode || 'same_zone'
  const modeLabel = CALC_MODE_BADGE[mode] || mode
  const breakdown = aggregate.zone_breakdown || []
  const isMixed = mode !== 'same_zone'

  return (
    <div className="p-4 space-y-3" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--info)',backgroundColor:'var(--canvas-elevated)'}}>
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase" style={{color:'var(--ink)',fontFamily:'var(--font-mono)',letterSpacing:'0.06em'}}>
          합필 진단 ({aggregate.parcel_count || parcels.length}개 필지)
        </p>
        <span className="text-[10px] px-2 py-0.5 font-medium" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--body)',fontFamily:'var(--font-mono)'}}>
          {modeLabel}
        </span>
      </div>

      {/* 시·도 다름 경고 */}
      {aggregate.cross_jurisdiction && (
        <div className="text-xs p-2 leading-relaxed" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--error)',backgroundColor:'var(--canvas)'}}>
          <b style={{color:'var(--error)'}}>시·도가 다른 필지가 포함되어 있습니다</b> ({aggregate.jurisdictions?.join(' / ')}).
          실제 법적 합필은 불가능하며, 본 결과는 <b>사업성 시뮬레이션 목적</b>으로만 사용하세요.
        </div>
      )}

      {/* 상단 요약 3칸 */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        {[
          { label: '합산 대지면적', value: `${aggregate.total_site_area?.toLocaleString()}㎡` },
          { label: isMixed ? '대표 용도지역' : '용도지역', value: aggregate.primary_zone || aggregate.common_zone_use || '-' },
          { label: '산정 방식', value: aggregate.calc_method },
        ].map((item) => (
          <div key={item.label} className="p-2" style={{backgroundColor:'var(--canvas)',borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)'}}>
            <p style={{color:'var(--mute)'}}>{item.label}</p>
            <p className="font-semibold text-sm mt-0.5" style={{color:'var(--ink)'}}>{item.value}</p>
          </div>
        ))}
      </div>

      {/* 임계치 적용 근거 */}
      {isMixed && aggregate.threshold_m2 && (
        <div className="p-2.5 text-xs leading-relaxed" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)'}}>
          <p className="font-semibold mb-0.5" style={{color:'var(--ink)'}}>소규모 임계치 {aggregate.threshold_m2.toLocaleString()}㎡ 적용</p>
          <p style={{color:'var(--body)'}}>{aggregate.threshold_basis}</p>
        </div>
      )}

      {/* 가중평균 한도 */}
      {mode === 'weighted' && (
        <div className="p-2.5 text-xs" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)'}}>
          <p className="font-semibold mb-1.5" style={{color:'var(--ink)'}}>가중평균 한도 (면적 안분)</p>
          <div className="grid grid-cols-2 gap-2">
            <div><span style={{color:'var(--mute)'}}>건폐율 한도: </span><span className="font-semibold" style={{color:'var(--ink)'}}>{aggregate.weighted_coverage_limit ?? '-'}%</span></div>
            <div><span style={{color:'var(--mute)'}}>용적률 한도: </span><span className="font-semibold" style={{color:'var(--ink)'}}>{aggregate.weighted_far_limit ?? '-'}%</span></div>
          </div>
        </div>
      )}

      {/* zone별 한도 내역 */}
      {isMixed && breakdown.length > 1 && (
        <div className="text-xs">
          <p className="font-semibold mb-1" style={{color:'var(--mute)'}}>용도지역별 한도</p>
          <div style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',overflow:'hidden'}}>
            {breakdown.map((b, i) => (
              <div key={i} className="flex items-center justify-between px-2 py-1.5" style={{borderTop: i>0 ? '1px solid var(--hairline-soft)' : undefined}}>
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <span className="font-medium truncate" style={{color:'var(--ink)'}}>{b.zone}</span>
                  <span style={{color:'var(--mute)'}}>{b.area?.toLocaleString()}㎡ ({(b.area_ratio * 100).toFixed(1)}%)</span>
                </div>
                <div className="flex gap-3 text-xs flex-shrink-0" style={{color:'var(--body)',fontFamily:'var(--font-mono)'}}>
                  <span>건폐 {b.coverage_limit ?? '?'}%</span>
                  <span>용적 {b.far_limit ?? '?'}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 필지별 내역 */}
      <div className="space-y-1.5">
        <p className="text-xs font-semibold" style={{color:'var(--mute)'}}>필지별 내역</p>
        {parcels.map((p, i) => (
          <div key={i} className="flex items-center justify-between text-xs px-2 py-1.5" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)'}}>
            <div className="flex-1 min-w-0">
              <span className="font-medium mr-2" style={{color:'var(--mute)'}}>{i + 1}.</span>
              <span className="truncate" style={{color:'var(--ink)'}}>{p.address}</span>
              {p.jurisdiction_name && <span className="ml-1" style={{color:'var(--faint)'}}>· {p.jurisdiction_name}</span>}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0 ml-2">
              <span style={{color:'var(--body)'}}>{p.site_area?.toLocaleString()}㎡</span>
              <span className="font-medium" style={{color:'var(--link)',fontFamily:'var(--font-mono)',fontSize:'11px'}}>{p.zone_use}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function LandInfoCard({ info }) {
  if (!info.zone_use) return null
  return (
    <div className="p-4" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas-elevated)'}}>
      <p className="text-xs font-semibold mb-2 uppercase" style={{color:'var(--mute)',fontFamily:'var(--font-mono)',letterSpacing:'0.06em'}}>토지이용계획 (자동 조회)</p>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <InfoRow label="용도지역" value={info.zone_use} />
        {info.zone_district && <InfoRow label="용도지구" value={info.zone_district} />}
        {info.zone_area && <InfoRow label="용도구역" value={info.zone_area} />}
        {info.land_category && <InfoRow label="지목" value={info.land_category} />}
        {info.official_price && (
          <InfoRow label="공시지가" value={`${info.official_price.toLocaleString()}원/㎡`} />
        )}
      </div>
      {info.cache_hit && !info.cache_stale && (
        <p className="mt-2 text-xs" style={{color:'var(--faint)'}}>캐시 데이터 ({info.cache_age_days}일 전)</p>
      )}
      {info.cache_stale && (
        <div className="mt-2 px-2.5 py-1.5 text-xs" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--warn)',color:'var(--warn-deep)'}}>
          {info.cache_age_days}일 전 캐시 — VWorld 재조회 실패. 용도지역·지목 등이 변경됐을 수 있습니다.
        </div>
      )}
    </div>
  )
}

function CategoryCard({ label, cat, nodeId, onShowGraph }) {
  const passed = cat.pass
  const statusColor =
    passed === false ? 'var(--error)' :
    passed === true  ? 'var(--ok)' :
    'var(--warn)'
  const badgeLabel =
    passed === false ? '초과' :
    passed === true  ? '적합' :
    '확인필요'

  // 핵심 수치 — 헤더 한 줄에 같이 노출 (펼침 없이도 빠르게 파악)
  const headlineFigures = [
    cat.classification ? cat.classification : null,
    cat.actual_pct != null && cat.limit_pct != null
      ? `${cat.actual_pct}% / ${cat.limit_pct}%`
      : cat.actual_pct != null
      ? `${cat.actual_pct}%`
      : cat.required_pct != null
      ? `의무 ${cat.required_pct}%`
      : null,
    cat.actual_height_m != null ? `높이 ${cat.actual_height_m}m` : null,
    cat.provided_spaces != null && cat.required_spaces != null
      ? `${cat.provided_spaces}/${cat.required_spaces}대`
      : null,
    cat.excess_pct > 0 ? `초과 ${cat.excess_pct}%p` : null,
    cat.deficit_m2 > 0 ? `부족 ${cat.deficit_m2}㎡` : null,
    cat.exempt === true ? '면제' : null,
    cat.required_level ? `의무: ${cat.required_level}` : null,
  ].filter(Boolean)

  // 위험·확인필요는 기본 펼침, 적합은 기본 접힘
  const [open, setOpen] = useState(false)

  const hasDetail =
    cat.notes ||
    (cat.items && cat.items.length > 0) ||
    (cat.warnings && cat.warnings.length > 0) ||
    (cat.checks && cat.checks.length > 0) ||
    (cat.implications && cat.implications.length > 0) ||
    (cat.guidelines && Object.keys(cat.guidelines).length > 0) ||
    cat.provenance ||
    cat.source ||
    (cat.law_refs && cat.law_refs.length > 0)

  return (
    <div style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:`3px solid ${statusColor}`,backgroundColor:'var(--canvas-elevated)'}}>
      <button
        type="button"
        onClick={() => hasDetail && setOpen((v) => !v)}
        className={`w-full text-left p-3 transition-colors`}
        style={{borderRadius:'var(--radius)',cursor:hasDetail?'pointer':'default'}}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <span className="font-semibold text-sm truncate" style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}}>{label}</span>
            <span className="text-[10px] px-1.5 py-0.5 font-medium flex-shrink-0" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:statusColor,fontFamily:'var(--font-mono)'}}>
              {badgeLabel}
            </span>
            {headlineFigures.length > 0 && (
              <span className="text-xs truncate" style={{color:'var(--mute)',fontFamily:'var(--font-mono)'}}>
                {headlineFigures.join(' · ')}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {cat.score != null ? (
              <span className="text-lg font-semibold" style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}}>
                {cat.score}
                <span className="text-xs font-normal" style={{color:'var(--faint)'}}>/10</span>
              </span>
            ) : (
              <span className="text-sm" style={{color:'var(--faint)'}}>–/10</span>
            )}
            <span className="text-xs" style={{color:'var(--warn)'}}>{CONFIDENCE_STARS(cat.confidence)}</span>
            {hasDetail && (
              <span className="text-xs" style={{color:'var(--faint)'}}>{open ? '▴' : '▾'}</span>
            )}
          </div>
        </div>
      </button>

      {nodeId && onShowGraph && (
        <div className="px-3 pb-2 -mt-1">
          <button
            type="button"
            onClick={() => onShowGraph(nodeId)}
            className="text-[10px] hover:underline"
            style={{color:'var(--link)'}}
          >
            이 항목의 법규 관계 보기
          </button>
        </div>
      )}

      {open && hasDetail && (
        <div className="px-3 pb-3 pt-1 space-y-2" style={{borderTop:'1px solid var(--hairline-soft)'}}>
          {cat.notes && (
            <p className="text-xs leading-relaxed" style={{color:'var(--body)'}}>{cat.notes}</p>
          )}
          {cat.items && cat.items.length > 0 && (
            cat.items[0]?.matched_zones != null
              ? <ZoneOverlapItems items={cat.items} />
              : cat.items[0]?.required_level != null
              ? <CertItems items={cat.items} />
              : <FireSafetyItems items={cat.items} />
          )}
          {cat.implications && cat.implications.length > 0 && (
            <div>
              <p className="text-xs font-medium mb-1" style={{color:'var(--mute)'}}>적용 기준</p>
              <ul className="text-xs list-disc list-inside space-y-0.5" style={{color:'var(--body)'}}>
                {cat.implications.map((impl, i) => <li key={i}>{impl}</li>)}
              </ul>
            </div>
          )}
          {cat.checks && cat.checks.length > 0 && (
            <div>
              <p className="text-xs font-medium mb-1" style={{color:'var(--mute)'}}>검토 항목</p>
              <ul className="text-xs list-disc list-inside space-y-0.5" style={{color:'var(--body)'}}>
                {cat.checks.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}
          {cat.guidelines && Object.keys(cat.guidelines).length > 0 && (
            <div>
              <p className="text-xs font-medium mb-1" style={{color:'var(--mute)'}}>적용 가이드라인</p>
              <ul className="text-xs space-y-0.5" style={{color:'var(--body)'}}>
                {Object.entries(cat.guidelines).map(([k, v]) => (
                  <li key={k}><span className="font-medium" style={{color:'var(--ink)'}}>{k}:</span> {v}</li>
                ))}
              </ul>
            </div>
          )}
          {cat.warnings && cat.warnings.length > 0 && (
            <ul className="text-xs list-disc list-inside space-y-0.5" style={{color:'var(--warn-deep)'}}>
              {cat.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}
          {cat.provenance && <ProvenanceBlock prov={cat.provenance} />}
          <SourceBadge source={cat.source} />
          {cat.law_refs && cat.law_refs.length > 0 && (
            <LawRefs refs={cat.law_refs} />
          )}
        </div>
      )}
    </div>
  )
}

function InfoRow({ label, value }) {
  return (
    <div>
      <span style={{color:'var(--mute)'}}>{label}: </span>
      <span className="font-medium" style={{color:'var(--ink)'}}>{value}</span>
    </div>
  )
}

const STATUS_STYLE = {
  required:     { label: '의무',     color: 'var(--info)' },
  not_required: { label: '면제',     color: 'var(--mute)' },
  needs_review: { label: '검토필요', color: 'var(--warn-deep)' },
}

function FireSafetyItems({ items }) {
  return (
    <div className="mt-2 space-y-1.5">
      {items.map((it, i) => {
        const sty = STATUS_STYLE[it.status] || { label: '미정', color: 'var(--mute)' }
        return (
          <div key={i} className="text-xs pl-2" style={{borderLeft:'2px solid var(--hairline)'}}>
            <div className="flex items-center gap-2">
              <span className="font-medium" style={{color:'var(--ink)'}}>{it.name}</span>
              <span className="px-1.5 py-0.5 font-medium" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:sty.color,fontFamily:'var(--font-mono)',fontSize:'10px'}}>
                {sty.label}
              </span>
            </div>
            {it.note && <p className="mt-0.5" style={{color:'var(--mute)'}}>{it.note}</p>}
            {it.basis && <p className="mt-0.5" style={{color:'var(--faint)'}}>{it.basis}</p>}
          </div>
        )
      })}
    </div>
  )
}

function ZoneOverlapItems({ items }) {
  return (
    <div className="mt-2 space-y-2.5">
      {items.map((it, i) => (
        <div key={i} className="text-xs pl-2 space-y-1" style={{borderLeft:'2px solid var(--warn)'}}>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold" style={{color:'var(--ink)'}}>{it.display_name}</span>
            {it.matched_zones?.length > 0 && (
              <span className="text-[10px] px-1.5 py-0.5 font-medium" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--body)',fontFamily:'var(--font-mono)'}}>
                {it.matched_zones.join(', ')}
              </span>
            )}
          </div>
          <p className="leading-relaxed" style={{color:'var(--body)'}}>{it.restriction_summary}</p>
          {it.law && (
            it.url
              ? <a href={it.url} target="_blank" rel="noreferrer" className="underline block" style={{color:'var(--link)'}}>{it.law}</a>
              : <p style={{color:'var(--faint)'}}>{it.law}</p>
          )}
        </div>
      ))}
      <p className="text-[10px] leading-relaxed pt-1" style={{color:'var(--mute)'}}>
        위 지구·구역의 세부 행위 제한 기준은 허가권자(시·군·구청) 확인이 필수입니다.
      </p>
    </div>
  )
}

function CertItems({ items }) {
  return (
    <div className="mt-2 space-y-1.5">
      {items.map((it, i) => (
        <div key={i} className="text-xs pl-2" style={{borderLeft:'2px solid var(--info)'}}>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium" style={{color:'var(--ink)'}}>{it.name}</span>
            <span className="px-1.5 py-0.5 font-medium" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--info)',fontFamily:'var(--font-mono)',fontSize:'10px'}}>
              {it.required_level}
            </span>
          </div>
          {it.law && (
            it.url
              ? <a href={it.url} target="_blank" rel="noreferrer" className="underline mt-0.5 block" style={{color:'var(--link)'}}>{it.law}</a>
              : <p className="mt-0.5" style={{color:'var(--faint)'}}>{it.law}</p>
          )}
        </div>
      ))}
    </div>
  )
}

// 산정 근거(provenance) 키 → 한글 라벨. 미정의 키는 원문 그대로 노출.
const PROV_LABELS = {
  building_area: '건축면적',
  site_area_used: '대지면적(유효)',
  floor_area_for_far: '용적률 산정 연면적',
  excluded_parking_m2: '제외 부속주차',
  excluded_refuge_m2: '제외 피난안전구역',
  excluded_attic_refuge_m2: '제외 경사지붕 대피공간',
  floors_below_excluded: '제외 지하층 수',
  height_m: '건물 높이',
  floors_above: '지상 층수',
  zone_use: '용도지역',
  road_width_m: '전면도로 폭',
  north_setback_m: '정북 이격거리',
  street_block_max_height_m: '가로구역 최고높이',
  road_20m_adjacent: '20m 도로 접함',
  adjacent_zone_north: '정북 인접 용도지역',
  building_use: '건물 용도',
  total_floor_area: '연면적',
  units: '세대수',
  unit_exclusive_area: '세대 전용면적',
  capacity: '정원/홀/타석',
  actual_pct: '산정값(%)',
  limit_pct: '한도(%)',
  excess_pct: '초과(%p)',
  shadow_applies: '정북 일조 적용',
  shadow_min_setback_m: '필요 이격(m)',
  exemptions: '적용 제외',
  pass: '판정',
  required_spaces: '법정 주차대수',
  provided_spaces: '계획 주차대수',
}

function _provVal(v) {
  if (v === null || v === undefined || v === '') return '–'
  if (Array.isArray(v)) return v.length ? v.join(', ') : '없음'
  if (typeof v === 'boolean') return v ? '예' : '아니오'
  return String(v)
}

// 산정 근거 — 계산기가 자기 입력값·산식·산출을 스스로 기술한 블록 (백엔드 provenance)
function ProvenanceBlock({ prov }) {
  if (!prov) return null
  const inputs = prov.inputs || {}
  const computed = prov.computed || {}
  const Rows = ({ obj }) => (
    <ul className="space-y-0.5">
      {Object.entries(obj).map(([k, v]) => (
        <li key={k} className="flex justify-between gap-2">
          <span className="text-gray-500">{PROV_LABELS[k] || k}</span>
          <span className="text-gray-700 font-medium text-right">{_provVal(v)}</span>
        </li>
      ))}
    </ul>
  )
  return (
    <details className="text-xs mt-1.5" style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius-sm)'}}>
      <summary className="cursor-pointer font-medium px-2 py-1.5" style={{color:'var(--body)'}}>
        산정 근거 ▾
      </summary>
      <div className="mt-1.5 space-y-1.5 pl-2 px-2 pb-2" style={{borderLeft:'2px solid var(--hairline-soft)'}}>
        {prov.formula && (
          <p className="leading-relaxed" style={{color:'var(--body)'}}>
            <span style={{color:'var(--mute)'}}>산식: </span>{prov.formula}
          </p>
        )}
        {Object.keys(inputs).length > 0 && (
          <div>
            <p className="mb-0.5" style={{color:'var(--mute)'}}>입력값</p>
            <Rows obj={inputs} />
          </div>
        )}
        {Object.keys(computed).length > 0 && (
          <div>
            <p className="mb-0.5" style={{color:'var(--mute)'}}>산출</p>
            <Rows obj={computed} />
          </div>
        )}
        {prov.basis && (
          <p className="text-[10px]" style={{color:'var(--faint)'}}>근거: {prov.basis}</p>
        )}
      </div>
    </details>
  )
}

function SourceBadge({ source }) {
  if (!source) return null
  return (
    <p className="mt-1.5 text-xs">
      <span className="inline-flex items-center px-1.5 py-0.5 font-medium" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--mute)',fontFamily:'var(--font-mono)',fontSize:'10px'}}>
        {source}
      </span>
    </p>
  )
}

function LawRefs({ refs }) {
  return (
    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
      {refs.map((r, i) => {
        const graphUrl = graphSearchUrl(r.name)
        return (
          <span key={i} className="inline-flex items-center gap-1">
            <a
              href={r.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs hover:underline inline-flex items-center gap-0.5"
              style={{color:'var(--link)'}}
              title={r.url}
            >
              {r.name}
            </a>
            {graphUrl && (
              <a
                href={graphUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline"
                style={{fontSize:'10px',color:'var(--faint)'}}
                title="법령 그래프에서 조문 원문·인용관계·지자체 비교 보기"
              >
                원문↗
              </a>
            )}
          </span>
        )
      })}
    </div>
  )
}

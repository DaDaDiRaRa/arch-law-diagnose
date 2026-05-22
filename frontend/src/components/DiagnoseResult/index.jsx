import { useState } from 'react'
import { useDiagnoseStore } from '../../stores/diagnoseStore'
import CaseReference from '../CaseReference'
import DataQualityBanner from '../DataQualityBanner'
import DevTrendPanel from '../DevTrendPanel'
import LawChangeAlert from '../LawChangeAlert'
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

const CONFIDENCE_STARS = (n) => {
  if (n === null || n === undefined) return '★☆☆☆☆'
  const filled = '★'.repeat(Math.min(n, 5))
  const empty = '☆'.repeat(Math.max(0, 5 - n))
  return filled + empty
}

const SIGNAL_CONFIG = {
  GREEN: { bg: 'bg-green-50', border: 'border-green-400', text: 'text-green-700', label: '적합', dot: '🟢' },
  YELLOW: { bg: 'bg-yellow-50', border: 'border-yellow-400', text: 'text-yellow-700', label: '주의 필요', dot: '🟡' },
  RED: { bg: 'bg-red-50', border: 'border-red-400', text: 'text-red-700', label: '부적합', dot: '🔴' },
}

export default function DiagnoseResult() {
  const { result: rawResult, error, loading, reset, formData } = useDiagnoseStore()
  const [reportOpen, setReportOpen] = useState(false)

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center space-y-3">
          <div className="text-4xl animate-spin">⟳</div>
          <p className="text-gray-500 text-sm">법규 데이터 조회 중...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-5">
        <p className="font-semibold text-red-700 mb-1">오류 발생</p>
        <p className="text-sm text-red-600 whitespace-pre-line">{error}</p>
        <button onClick={reset} className="mt-3 text-xs text-red-500 underline">다시 시도</button>
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

  // CaseReference 에 전달할 인자
  const jurisdiction = inferJurisdiction(result.address)
  const siteAreaNum = formData?.site_area ? parseFloat(formData.site_area) : undefined

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
      <div className={`rounded-xl border-2 ${sig.border} ${sig.bg} p-5`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-gray-500 mb-0.5">종합 진단</p>
            <p className={`text-2xl font-bold ${sig.text}`}>
              {sig.dot} {sig.label}
            </p>
          </div>
          {result.overall_score !== null && result.overall_score !== undefined && (
            <div className="text-right">
              <p className="text-xs text-gray-500">종합 점수</p>
              <p className={`text-3xl font-bold ${sig.text}`}>
                {result.overall_score.toFixed(1)}
                <span className="text-base font-normal text-gray-400">/10</span>
              </p>
            </div>
          )}
        </div>
        <div className="mt-3 pt-3 border-t border-current/10">
          <button
            onClick={() => setReportOpen(true)}
            className="text-sm font-medium px-3 py-1.5 rounded-md bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 inline-flex items-center gap-1.5"
          >
            📄 법규 검토서 열기
          </button>
          <span className="ml-2 text-xs text-gray-500">표준 양식 · 브라우저 인쇄로 PDF 저장</span>
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
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 space-y-3">
              <p className="text-sm font-semibold text-red-700">위험 항목 ({result.risks.length}건)</p>
              {result.risks.map((r, i) => (
                <div key={i} className="border-l-2 border-red-300 pl-3">
                  <div className="text-sm text-red-600">
                    <span className="font-medium">{r.category}:</span> {r.reason}
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
            <div className="rounded-xl border border-yellow-200 bg-yellow-50 p-4 space-y-2">
              <p className="text-sm font-semibold text-yellow-700">검토 필요 ({result.warnings.length}건)</p>
              {result.warnings.map((w, i) => (
                <div key={i} className="text-sm text-yellow-700">
                  <span className="font-medium">{w.category}:</span> {w.reason}
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
              <div className="rounded-xl border-2 border-amber-300 bg-amber-50 p-4 space-y-2">
                <p className="text-sm font-semibold text-amber-800">
                  📐 필수 수동검토 ({manualItems.length}건) — 입력값 부족으로 자동 판정 불가
                </p>
                {manualItems.map(([key, c]) => (
                  <div key={key} className="text-xs text-amber-800 border-l-2 border-amber-300 pl-2">
                    <span className="font-medium">{CATEGORY_LABELS[key] || key}:</span> {c.notes}
                  </div>
                ))}
                <p className="text-[var(--font-size-2xs)] text-amber-700 leading-relaxed mt-1">
                  상단 입력 폼의 "☀ 높이·일조 자동 판정 입력" 섹션에 정북 이격거리 등을 입력하면 자동 판정됩니다.
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
            <p className="text-sm font-semibold text-gray-700 mb-3">카테고리별 상세</p>
            <div className="grid grid-cols-1 2xl:grid-cols-2 gap-3">
              {categories.map(([key, cat]) => {
                const reliefSuffix = cat.relief_info?.applied ? ' (완화)' : ''
                return (
                  <CategoryCard
                    key={key}
                    label={(CATEGORY_LABELS[key] || key) + reliefSuffix}
                    cat={cat}
                  />
                )
              })}
            </div>
          </div>

          {/* Phase 4 — 유사 사내 케이스 */}
          <CaseReference
            buildingUse={formData?.building_use}
            zoneUse={result.land_info?.zone_use}
            siteArea={siteAreaNum}
            jurisdiction={jurisdiction}
          />
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
    <div className="rounded-xl border-2 border-sky-300 bg-sky-50/60 p-4 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm font-bold text-sky-900">
          🗺 대지면적 자동 보정 (도시계획시설 저촉)
        </p>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
          isManual ? 'bg-gray-200 text-gray-700' : 'bg-sky-200 text-sky-800'
        }`}>
          {isManual ? '✋ 사용자 수동 지정' : '⚙ 자동 (VWorld×SHP 교차)'}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="bg-white rounded p-2 border border-sky-200">
          <p className="text-gray-500">입력 대지면적</p>
          <p className="font-bold text-gray-900 text-sm">
            {original_m2?.toLocaleString()}㎡
          </p>
        </div>
        <div className="bg-white rounded p-2 border border-red-200">
          <p className="text-gray-500">시설부지 제외</p>
          <p className="font-bold text-red-700 text-sm">
            -{excluded_m2?.toLocaleString()}㎡ ({pct}%)
          </p>
        </div>
        <div className="bg-white rounded p-2 border border-green-300">
          <p className="text-gray-500">유효 대지면적</p>
          <p className="font-bold text-green-700 text-sm">
            {effective_m2?.toLocaleString()}㎡
          </p>
        </div>
      </div>
      <p className="text-xs text-sky-800 leading-relaxed">{note}</p>
      {by_facility.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-gray-600 hover:text-gray-900">
            저촉 시설 내역 ({by_facility.length}건) ▾
          </summary>
          <ul className="mt-1 space-y-0.5 pl-4">
            {by_facility.slice(0, 8).map((f, i) => (
              <li key={i} className="flex justify-between gap-2 text-gray-700">
                <span className="truncate">
                  {f.category}
                  {f.facility_name ? ` — ${f.facility_name}` : ''}
                </span>
                <span className="text-gray-500 flex-shrink-0">
                  {f.area_m2?.toLocaleString()}㎡
                </span>
              </li>
            ))}
            {by_facility.length > 8 && (
              <li className="text-gray-500">외 {by_facility.length - 8}건</li>
            )}
          </ul>
        </details>
      )}
      <p className="text-[var(--font-size-2xs)] text-gray-500 leading-relaxed">
        ⚠ 자동 보정은 추정이며, 실제 도면(지적도·도시계획시설 결정고시)에서 확인 후
        시설부지 면적을 직접 입력하시면 그 값으로 재산정됩니다.
      </p>
    </div>
  )
}

const REVIEW_SEVERITY_STYLE = {
  REQUIRED: { icon: '🔴', cls: 'border-red-300 bg-red-50', textCls: 'text-red-700', badge: '필요', badgeCls: 'bg-red-100 text-red-700' },
  MAYBE:    { icon: '🟡', cls: 'border-yellow-300 bg-yellow-50', textCls: 'text-yellow-800', badge: '검토', badgeCls: 'bg-yellow-100 text-yellow-700' },
  NONE:     { icon: '⚪', cls: 'border-gray-200 bg-gray-50', textCls: 'text-gray-500', badge: '해당없음', badgeCls: 'bg-gray-100 text-gray-500' },
}

function ApplicableReviewsCard({ reviews }) {
  const { items = [], required_count = 0, maybe_count = 0 } = reviews
  return (
    <div className="rounded-xl border-2 border-indigo-300 bg-indigo-50/50 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-bold text-indigo-900">
          📋 인허가 심의 트리거 (8개 검사)
        </p>
        <div className="flex gap-2 text-xs">
          {required_count > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-medium">
              필요 {required_count}건
            </span>
          )}
          {maybe_count > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-800 font-medium">
              검토 {maybe_count}건
            </span>
          )}
          {required_count === 0 && maybe_count === 0 && (
            <span className="px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">
              모두 해당없음
            </span>
          )}
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {items.map((it, i) => {
          const s = REVIEW_SEVERITY_STYLE[it.severity] || REVIEW_SEVERITY_STYLE.NONE
          return (
            <div key={i} className={`border rounded-lg p-2.5 ${s.cls} text-xs space-y-1`}>
              <div className="flex items-center justify-between">
                <span className={`font-semibold ${s.textCls}`}>
                  {s.icon} {it.name}
                </span>
                <span className={`text-[var(--font-size-2xs)] px-1.5 py-0.5 rounded font-medium ${s.badgeCls}`}>
                  {s.badge}
                </span>
              </div>
              {it.triggered_reasons?.length > 0 && (
                <ul className="text-gray-700 pl-3 space-y-0.5">
                  {it.triggered_reasons.map((r, j) => (
                    <li key={j} className="list-disc">{r}</li>
                  ))}
                </ul>
              )}
              {it.note && (
                <p className="text-gray-600 text-[var(--font-size-xs)] leading-relaxed">{it.note}</p>
              )}
              {it.law_ref && (
                <a
                  href={it.law_ref_url || '#'}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[var(--font-size-2xs)] text-indigo-600 hover:underline inline-block"
                >
                  📜 {it.law_ref}
                </a>
              )}
            </div>
          )
        })}
      </div>
      <p className="text-[var(--font-size-2xs)] text-indigo-700 leading-relaxed">
        ⚠ 트리거 룰은 일반 기준이며, 지자체 조례·세부 조건에 따라 추가 심의가 있을 수 있습니다.
        교육환경·문화재는 좌표 기반 정밀 판정 미지원 — 토지이음 및 교육청·국가유산청 확인 권장.
      </p>
    </div>
  )
}

function inferJurisdiction(address) {
  if (!address) return undefined
  // "서울특별시 영등포구 ..." → "영등포구" 추출
  const m = address.match(/\s([가-힣]+(?:구|군|시))(?:\s|$)/)
  return m ? m[1] : undefined
}

const CALC_MODE_BADGE = {
  same_zone: { label: '동일 용도지역', cls: 'bg-green-100 text-green-700' },
  small_part: { label: '소규모 예외', cls: 'bg-purple-100 text-purple-700' },
  weighted: { label: '면적 안분 (가중평균)', cls: 'bg-amber-100 text-amber-700' },
}

function MultiParcelSummary({ info }) {
  const { parcels = [], aggregate = {} } = info
  const mode = aggregate.calc_mode || 'same_zone'
  const modeBadge = CALC_MODE_BADGE[mode] || CALC_MODE_BADGE.same_zone
  const breakdown = aggregate.zone_breakdown || []
  const isMixed = mode !== 'same_zone'

  return (
    <div className="rounded-xl border-2 border-blue-300 bg-blue-50/50 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-bold text-blue-900">
          🔗 합필 진단 ({aggregate.parcel_count || parcels.length}개 필지)
        </p>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${modeBadge.cls}`}>
          {modeBadge.label}
        </span>
      </div>

      {/* 시·도 다름 경고 */}
      {aggregate.cross_jurisdiction && (
        <div className="text-xs bg-red-50 border border-red-200 rounded p-2 leading-relaxed">
          ⚠️ <b>시·도가 다른 필지가 포함되어 있습니다</b> ({aggregate.jurisdictions?.join(' / ')}).
          실제 법적 합필은 불가능하며, 본 결과는 <b>사업성 시뮬레이션 목적</b>으로만 사용하세요.
        </div>
      )}

      {/* 상단 요약 3칸 */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="bg-white rounded p-2 border border-blue-200">
          <p className="text-gray-500">합산 대지면적</p>
          <p className="font-bold text-gray-900 text-sm">
            {aggregate.total_site_area?.toLocaleString()}㎡
          </p>
        </div>
        <div className="bg-white rounded p-2 border border-blue-200">
          <p className="text-gray-500">{isMixed ? '대표 용도지역' : '용도지역'}</p>
          <p className="font-bold text-gray-900 text-sm">
            {aggregate.primary_zone || aggregate.common_zone_use || '-'}
          </p>
          {mode === 'small_part' && aggregate.small_part_zone && (
            <p className="text-xs text-purple-700 mt-0.5">
              소규모: {aggregate.small_part_zone}
            </p>
          )}
        </div>
        <div className="bg-white rounded p-2 border border-blue-200">
          <p className="text-gray-500">산정 방식</p>
          <p className="font-medium text-gray-700 text-xs leading-tight">
            {aggregate.calc_method}
          </p>
        </div>
      </div>

      {/* 임계치 적용 근거 (small_part / weighted 모드일 때) */}
      {isMixed && aggregate.threshold_m2 && (
        <div className="bg-indigo-50 border border-indigo-200 rounded p-2.5 text-xs leading-relaxed">
          <p className="font-semibold text-indigo-900 mb-0.5">
            📐 소규모 임계치 {aggregate.threshold_m2.toLocaleString()}㎡ 적용
          </p>
          <p className="text-indigo-700">
            {aggregate.threshold_basis}
          </p>
        </div>
      )}

      {/* 가중평균 한도 (weighted 모드일 때) */}
      {mode === 'weighted' && (
        <div className="bg-amber-50 border border-amber-300 rounded p-2.5 text-xs">
          <p className="font-semibold text-amber-900 mb-1.5">가중평균 한도 (면적 안분)</p>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="text-gray-600">건폐율 한도: </span>
              <span className="font-bold text-amber-800">
                {aggregate.weighted_coverage_limit ?? '-'}%
              </span>
            </div>
            <div>
              <span className="text-gray-600">용적률 한도: </span>
              <span className="font-bold text-amber-800">
                {aggregate.weighted_far_limit ?? '-'}%
              </span>
            </div>
          </div>
        </div>
      )}

      {/* zone별 한도 내역 (mixed 모드일 때) */}
      {isMixed && breakdown.length > 1 && (
        <div className="text-xs">
          <p className="font-semibold text-gray-600 mb-1">용도지역별 한도</p>
          <div className="bg-white rounded border border-gray-200 divide-y divide-gray-100">
            {breakdown.map((b, i) => (
              <div key={i} className="flex items-center justify-between px-2 py-1.5">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <span className="font-medium text-gray-800 truncate">{b.zone}</span>
                  <span className="text-gray-500">
                    {b.area?.toLocaleString()}㎡ ({(b.area_ratio * 100).toFixed(1)}%)
                  </span>
                </div>
                <div className="flex gap-3 text-xs text-gray-600 flex-shrink-0">
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
        <p className="text-xs font-semibold text-gray-600">필지별 내역</p>
        {parcels.map((p, i) => (
          <div
            key={i}
            className="flex items-center justify-between text-xs bg-white rounded px-2 py-1.5 border border-gray-200"
          >
            <div className="flex-1 min-w-0">
              <span className="font-medium text-gray-700 mr-2">{i + 1}.</span>
              <span className="text-gray-800 truncate">{p.address}</span>
              {p.jurisdiction_name && (
                <span className="ml-1 text-gray-400">· {p.jurisdiction_name}</span>
              )}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0 ml-2">
              <span className="text-gray-600">{p.site_area?.toLocaleString()}㎡</span>
              <span className="text-blue-700 font-medium">{p.zone_use}</span>
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
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <p className="text-xs font-semibold text-gray-500 mb-2">토지이용계획 (자동 조회)</p>
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
        <p className="mt-2 text-xs text-gray-400">캐시 데이터 ({info.cache_age_days}일 전)</p>
      )}
      {info.cache_stale && (
        <div className="mt-2 rounded bg-orange-50 border border-orange-200 px-2.5 py-1.5 text-xs text-orange-700">
          ⚠ {info.cache_age_days}일 전 캐시 — VWorld 재조회 실패. 용도지역·지목 등이 변경됐을 수 있습니다.
        </div>
      )}
    </div>
  )
}

function CategoryCard({ label, cat }) {
  const passed = cat.pass
  const borderCls =
    passed === false ? 'border-red-300' :
    passed === true ? 'border-green-300' :
    'border-yellow-300'
  const badgeCls =
    passed === false ? 'bg-red-100 text-red-700' :
    passed === true ? 'bg-green-100 text-green-700' :
    'bg-yellow-100 text-yellow-700'
  const badgeLabel =
    passed === false ? '✗ 초과' :
    passed === true ? '✓ 적합' :
    '? 확인필요'

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
    cat.source ||
    (cat.law_refs && cat.law_refs.length > 0)

  return (
    <div className={`rounded-xl border ${borderCls} bg-white`}>
      <button
        type="button"
        onClick={() => hasDetail && setOpen((v) => !v)}
        className={`w-full text-left p-3 ${hasDetail ? 'hover:bg-gray-50' : 'cursor-default'} transition-colors rounded-xl`}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <span className="font-semibold text-gray-800 text-sm truncate">{label}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badgeCls} flex-shrink-0`}>
              {badgeLabel}
            </span>
            {headlineFigures.length > 0 && (
              <span className="text-xs text-gray-500 truncate">
                {headlineFigures.join(' · ')}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {cat.score != null ? (
              <span className="text-lg font-bold text-gray-800">
                {cat.score}
                <span className="text-xs text-gray-400">/10</span>
              </span>
            ) : (
              <span className="text-sm text-gray-400">–/10</span>
            )}
            <span className="text-xs text-yellow-500">{CONFIDENCE_STARS(cat.confidence)}</span>
            {hasDetail && (
              <span className="text-gray-400 text-xs">{open ? '▴' : '▾'}</span>
            )}
          </div>
        </div>
      </button>

      {open && hasDetail && (
        <div className="px-3 pb-3 pt-1 border-t border-gray-100 space-y-2">
          {cat.notes && (
            <p className="text-xs text-gray-600 leading-relaxed">{cat.notes}</p>
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
              <p className="text-xs font-medium text-gray-600 mb-1">적용 기준</p>
              <ul className="text-xs text-gray-600 list-disc list-inside space-y-0.5">
                {cat.implications.map((impl, i) => <li key={i}>{impl}</li>)}
              </ul>
            </div>
          )}
          {cat.checks && cat.checks.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-600 mb-1">검토 항목</p>
              <ul className="text-xs text-gray-600 list-disc list-inside space-y-0.5">
                {cat.checks.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}
          {cat.guidelines && Object.keys(cat.guidelines).length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-600 mb-1">적용 가이드라인</p>
              <ul className="text-xs text-gray-600 space-y-0.5">
                {Object.entries(cat.guidelines).map(([k, v]) => (
                  <li key={k}><span className="font-medium">{k}:</span> {v}</li>
                ))}
              </ul>
            </div>
          )}
          {cat.warnings && cat.warnings.length > 0 && (
            <ul className="text-xs text-yellow-700 list-disc list-inside space-y-0.5">
              {cat.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}
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
      <span className="text-gray-500">{label}: </span>
      <span className="font-medium text-gray-800">{value}</span>
    </div>
  )
}

const STATUS_STYLE = {
  required:     { label: '의무',     cls: 'bg-blue-100 text-blue-700' },
  not_required: { label: '면제',     cls: 'bg-gray-100 text-gray-600' },
  needs_review: { label: '검토필요', cls: 'bg-yellow-100 text-yellow-700' },
}

function FireSafetyItems({ items }) {
  return (
    <div className="mt-2 space-y-1.5">
      {items.map((it, i) => {
        const sty = STATUS_STYLE[it.status] || { label: '미정', cls: 'bg-gray-100 text-gray-600' }
        return (
          <div key={i} className="text-xs border-l-2 border-gray-200 pl-2">
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-700">{it.name}</span>
              <span className={`px-1.5 py-0.5 rounded ${sty.cls} font-medium`}>
                {sty.label}
              </span>
            </div>
            {it.note && <p className="text-gray-500 mt-0.5">{it.note}</p>}
            {it.basis && <p className="text-gray-400 mt-0.5">{it.basis}</p>}
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
        <div key={i} className="text-xs border-l-2 border-amber-300 pl-2 space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-amber-800">{it.display_name}</span>
            {it.matched_zones?.length > 0 && (
              <span className="text-[var(--font-size-2xs)] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 font-medium">
                {it.matched_zones.join(', ')}
              </span>
            )}
          </div>
          <p className="text-gray-600 leading-relaxed">{it.restriction_summary}</p>
          {it.law && (
            it.url
              ? <a href={it.url} target="_blank" rel="noreferrer" className="text-blue-500 underline block">{it.law}</a>
              : <p className="text-gray-400">{it.law}</p>
          )}
        </div>
      ))}
      <p className="text-[var(--font-size-2xs)] text-amber-700 leading-relaxed pt-1">
        ⚠ 위 지구·구역의 세부 행위 제한 기준은 허가권자(시·군·구청) 확인이 필수입니다.
      </p>
    </div>
  )
}

function CertItems({ items }) {
  return (
    <div className="mt-2 space-y-1.5">
      {items.map((it, i) => (
        <div key={i} className="text-xs border-l-2 border-blue-200 pl-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-gray-700">{it.name}</span>
            <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-medium">
              {it.required_level}
            </span>
          </div>
          {it.law && (
            it.url
              ? <a href={it.url} target="_blank" rel="noreferrer" className="text-blue-500 underline mt-0.5 block">{it.law}</a>
              : <p className="text-gray-400 mt-0.5">{it.law}</p>
          )}
        </div>
      ))}
    </div>
  )
}

function SourceBadge({ source }) {
  if (!source) return null
  const isOrdinance = source.includes('조례')
  return (
    <p className="mt-1.5 text-xs">
      <span className={[
        'inline-flex items-center gap-1 px-1.5 py-0.5 rounded font-medium',
        isOrdinance
          ? 'bg-blue-50 text-blue-700 border border-blue-200'
          : 'bg-gray-100 text-gray-500 border border-gray-200',
      ].join(' ')}>
        {source}
      </span>
    </p>
  )
}

function LawRefs({ refs }) {
  return (
    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
      {refs.map((r, i) => (
        <a
          key={i}
          href={r.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-600 hover:text-blue-800 hover:underline inline-flex items-center gap-0.5"
          title={r.url}
        >
          📖 {r.name}
        </a>
      ))}
    </div>
  )
}

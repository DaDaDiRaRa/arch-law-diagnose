import { useDiagnoseStore } from '../../stores/diagnoseStore'
import CaseReference from '../CaseReference'
import LawChangeAlert from '../LawChangeAlert'
import ReviewRequestButton from '../ReviewRequestButton'

const CATEGORY_LABELS = {
  건폐율: '건폐율',
  용적률: '용적률',
  높이_일조: '높이·일조',
  주차: '주차',
  조경: '조경',
  설비_소방: '설비·소방',
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
  const { result, error, loading, reset, formData } = useDiagnoseStore()

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
        <p className="text-sm text-red-600">{error}</p>
        <button onClick={reset} className="mt-3 text-xs text-red-500 underline">다시 시도</button>
      </div>
    )
  }

  if (!result) return null

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
    <div className="space-y-5">
      {/* Phase 4 — 법규 변경 배너 (최상단) */}
      <LawChangeAlert />

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
      </div>

      {/* 토지 정보 */}
      {result.land_info && (
        <LandInfoCard info={result.land_info} />
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

      {/* 카테고리별 상세 */}
      <div className="space-y-3">
        <p className="text-sm font-semibold text-gray-700">카테고리별 상세</p>
        {categories.map(([key, cat]) => (
          <CategoryCard key={key} label={CATEGORY_LABELS[key] || key} cat={cat} />
        ))}
      </div>

      {/* Phase 4 — 유사 사내 케이스 */}
      <CaseReference
        buildingUse={formData?.building_use}
        zoneUse={result.land_info?.zone_use}
        siteArea={siteAreaNum}
        jurisdiction={jurisdiction}
      />
    </div>
  )
}

function buildBuildingInfo(fd) {
  if (!fd) return undefined
  const obj = {
    용도: fd.building_use,
    대지면적: fd.site_area && `${fd.site_area}㎡`,
    건축면적: fd.building_area && `${fd.building_area}㎡`,
    연면적: fd.total_floor_area && `${fd.total_floor_area}㎡`,
    층수: fd.floors_above && `지상${fd.floors_above}/지하${fd.floors_below || 0}`,
    높이: fd.height && `${fd.height}m`,
  }
  return Object.fromEntries(Object.entries(obj).filter(([_, v]) => v))
}

function inferJurisdiction(address) {
  if (!address) return undefined
  // "서울특별시 영등포구 ..." → "영등포구" 추출
  const m = address.match(/\s([가-힣]+(?:구|군|시))(?:\s|$)/)
  return m ? m[1] : undefined
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
      {info.cache_hit && (
        <p className="mt-2 text-xs text-gray-400">
          캐시 데이터 ({info.cache_age_days}일 전)
          {info.cache_stale && ' · 오래된 데이터'}
        </p>
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

  return (
    <div className={`rounded-xl border ${borderCls} bg-white p-4`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-gray-800 text-sm">{label}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badgeCls}`}>
              {badgeLabel}
            </span>
          </div>

          {/* 수치 행 */}
          <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-600 mb-2">
            {cat.actual_pct !== undefined && cat.actual_pct !== null && (
              <span>실적: <b>{cat.actual_pct}%</b></span>
            )}
            {cat.limit_pct !== undefined && cat.limit_pct !== null && (
              <span>한도: <b>{cat.limit_pct}%</b></span>
            )}
            {cat.required_pct !== undefined && cat.required_pct !== null && (
              <span>의무: <b>{cat.required_pct}%</b></span>
            )}
            {cat.excess_pct > 0 && (
              <span className="text-red-600">초과: <b>{cat.excess_pct}%p</b></span>
            )}
            {cat.deficit_m2 > 0 && (
              <span className="text-red-600">부족: <b>{cat.deficit_m2}㎡</b></span>
            )}
            {cat.actual_height_m !== undefined && (
              <span>높이: <b>{cat.actual_height_m}m</b></span>
            )}
            {cat.road_height_limit_m && (
              <span>도로제한: <b>{cat.road_height_limit_m}m</b></span>
            )}
            {cat.required_spaces !== undefined && (
              <span>법정: <b>{cat.required_spaces}대</b></span>
            )}
            {cat.provided_spaces !== undefined && cat.provided_spaces !== null && (
              <span>계획: <b>{cat.provided_spaces}대</b></span>
            )}
            {cat.exempt === true && (
              <span className="text-gray-500 italic">면제 대상</span>
            )}
          </div>

          <p className="text-xs text-gray-500 leading-relaxed">{cat.notes}</p>

          {/* 설비_소방 — AI 판단 항목 리스트 */}
          {cat.items && cat.items.length > 0 && (
            <FireSafetyItems items={cat.items} />
          )}

          {/* 경고(주의) — 설비_소방 등 */}
          {cat.warnings && cat.warnings.length > 0 && (
            <ul className="mt-2 text-xs text-yellow-700 list-disc list-inside space-y-0.5">
              {cat.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}

          <p className="mt-1.5 text-xs text-gray-400">근거: {cat.source}</p>

          {/* 법조문 링크 */}
          {cat.law_refs && cat.law_refs.length > 0 && (
            <LawRefs refs={cat.law_refs} />
          )}
        </div>

        {/* 점수 + 확신도 */}
        <div className="text-right flex-shrink-0">
          {cat.score !== null && cat.score !== undefined ? (
            <p className="text-xl font-bold text-gray-800">
              {cat.score}
              <span className="text-xs text-gray-400">/10</span>
            </p>
          ) : (
            <p className="text-sm text-gray-400">–/10</p>
          )}
          <p className="text-xs text-yellow-500">{CONFIDENCE_STARS(cat.confidence)}</p>
        </div>
      </div>
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

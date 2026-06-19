import { useEffect, useState } from 'react'
import { api } from '../../utils/api'

/**
 * 법규 검토서 자동 출력 — 새 창에 단독 표시 + 인쇄 친화.
 *
 * 양식: 사용자가 보내준 사진 기반 표준 양식
 *   항목 / 법규 및 조항 / 법정기준·설계내용 / 적법여부
 *
 * 사용: <LegalReviewReport rawResult={...} formData={...} onClose={...} />
 * 또는 별도 라우트로 표시.
 */

const CATEGORY_LABELS = {
  행위제한: '행위제한 적합성',
  도시계획시설: '도시계획시설 저촉',
  건폐율: '건폐율',
  용적률: '용적률',
  높이_일조: '높이·일조',
  주차: '주차',
  조경: '조경',
  설비_소방: '설비·소방',
}

const COMPLIANCE_LABEL = {
  true:  { label: '적법함', cls: 'compliant' },
  false: { label: '부적법', cls: 'non-compliant' },
  null:  { label: '확인필요', cls: 'review-needed' },
}

export default function LegalReviewReport({ rawResult, formData, onClose }) {
  const [projectName, setProjectName] = useState('')
  const [author, setAuthor] = useState('')
  const [company, setCompany] = useState('')
  const [downloading, setDownloading] = useState(null)  // 'md' | 'xlsx' | null

  const handleDownload = async (format) => {
    if (downloading) return
    setDownloading(format)
    try {
      await api.downloadDiagnoseExport(format, {
        result: rawResult,
        form_data: formData || {},
        project_name: projectName,
        company,
        author,
      })
    } catch (e) {
      alert(`${format.toUpperCase()} 다운로드 실패: ${e.message}`)
    } finally {
      setDownloading(null)
    }
  }

  useEffect(() => {
    // Esc 로 닫기
    const onKey = (e) => e.key === 'Escape' && onClose?.()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!rawResult) return null

  const isMulti = rawResult.mode === 'multi_parcel'
  const result = isMulti ? rawResult.result : rawResult
  const multi = isMulti ? { parcels: rawResult.parcels, aggregate: rawResult.aggregate } : null

  const today = new Date().toISOString().slice(0, 10)
  const signal = result.signal
  const signalText = signal === 'GREEN' ? '🟢 적합' : signal === 'RED' ? '🔴 부적합' : '🟡 주의 필요'

  const categories = Object.entries(result.results || {})

  return (
    <div className="lr-overlay">
      {/* 화면 표시용 툴바 (인쇄 시 숨김) */}
      <div className="lr-toolbar no-print">
        <div className="lr-meta-inputs">
          <input
            type="text" placeholder="프로젝트명"
            value={projectName} onChange={(e) => setProjectName(e.target.value)}
            className="lr-input"
          />
          <input
            type="text" placeholder="회사명 (선택)"
            value={company} onChange={(e) => setCompany(e.target.value)}
            className="lr-input"
          />
          <input
            type="text" placeholder="작성자 (선택)"
            value={author} onChange={(e) => setAuthor(e.target.value)}
            className="lr-input"
          />
        </div>
        <div className="lr-buttons">
          <button onClick={() => window.print()} className="lr-btn primary">
            📄 인쇄 / PDF 저장
          </button>
          <button
            onClick={() => handleDownload('md')}
            disabled={downloading === 'md'}
            className="lr-btn"
          >
            {downloading === 'md' ? '⏳ 생성중...' : '📝 MD 다운로드'}
          </button>
          <button
            onClick={() => handleDownload('xlsx')}
            disabled={downloading === 'xlsx'}
            className="lr-btn"
          >
            {downloading === 'xlsx' ? '⏳ 생성중...' : '📊 Excel 다운로드'}
          </button>
          <button onClick={onClose} className="lr-btn">닫기 (Esc)</button>
        </div>
      </div>

      {/* 실제 검토서 본문 */}
      <div className="lr-page">
        <h1 className="lr-title">법 규 검 토 서</h1>

        {/* 헤더 정보 */}
        <table className="lr-header-table">
          <tbody>
            <tr>
              <th>프로젝트명</th>
              <td>{projectName || '—'}</td>
              <th>작성일</th>
              <td>{today}</td>
            </tr>
            <tr>
              <th>대지 주소</th>
              <td colSpan={3}>{result.address || formData?.address || '—'}</td>
            </tr>
            <tr>
              <th>건축물 용도</th>
              <td colSpan={3}>
                {formData?.building_use || '—'}
                {formData?.building_use_detail && (
                  <div className="lr-note-sm">{formData.building_use_detail}</div>
                )}
              </td>
            </tr>
            <tr>
              <th>용도지역</th>
              <td>{result.land_info?.zone_use || '—'}</td>
              <th>지역지구</th>
              <td>{result.land_info?.zone_district || formData?.zone_district || '—'}</td>
            </tr>
            <tr>
              <th>대지면적</th>
              <td>
                {isMulti
                  ? `${multi.aggregate.total_site_area?.toLocaleString()}㎡ (합산)`
                  : (() => {
                      const sc = result.site_correction
                      if (sc?.applied) {
                        return (
                          <>
                            {sc.effective_m2?.toLocaleString()}㎡
                            <span className="lr-note" style={{ fontSize: 'var(--font-size-xs)' }}>
                              {' '}(입력 {sc.original_m2?.toLocaleString()}㎡ - 시설부지 {sc.excluded_m2?.toLocaleString()}㎡, 시행령 §3)
                            </span>
                          </>
                        )
                      }
                      return `${formData?.site_area || '—'}㎡`
                    })()}
              </td>
              <th>종합 판정</th>
              <td className={`lr-signal-${signal}`}>
                <strong>{signalText}</strong>
                {result.overall_score != null && (
                  <span> · {result.overall_score.toFixed(1)}/10</span>
                )}
              </td>
            </tr>
          </tbody>
        </table>

        {/* 대지면적 자동 보정 — 도시계획시설 저촉 (해당 시) */}
        {result.site_correction?.applied && (
          <section className="lr-section">
            <h2>대지면적 보정 내역 (도시계획시설 저촉)</h2>
            <p className="lr-note">
              산정 근거:{' '}
              <strong>
                {result.site_correction.source === 'manual'
                  ? '사용자 수동 지정'
                  : '자동 추정 (VWorld 지적도 × 도시계획시설 SHP 공간 교차)'}
              </strong>
              {' — '}
              {result.site_correction.note}
            </p>
            {result.site_correction.by_facility?.length > 0 && (
              <table className="lr-table">
                <thead>
                  <tr>
                    <th>구분</th>
                    <th>시설명</th>
                    <th>저촉 면적(㎡)</th>
                  </tr>
                </thead>
                <tbody>
                  {result.site_correction.by_facility.slice(0, 10).map((f, i) => (
                    <tr key={i}>
                      <td>{f.category}</td>
                      <td>{f.facility_name || '—'}</td>
                      <td className="right">{f.area_m2?.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="lr-note" style={{ fontSize: 'var(--font-size-xs)' }}>
              ※ 건축법 시행령 §3에 따라 도시·군계획시설 부지에 포함되는 면적은
              대지면적에서 제외하여 건폐율·용적률 등을 산정합니다.
              자동 추정 결과는 실제 도면 확인이 필요하며, 입력 폼에 직접
              수정값을 넣을 수 있습니다.
            </p>
          </section>
        )}

        {/* 인허가 심의 트리거 (해당 시) */}
        {result.applicable_reviews?.items?.length > 0 && (
          <section className="lr-section">
            <h2>인허가 심의 트리거 ({result.applicable_reviews.required_count}건 필요)</h2>
            <table className="lr-table">
              <thead>
                <tr>
                  <th>심의명</th>
                  <th>판정</th>
                  <th>트리거 사유</th>
                  <th>근거법령</th>
                </tr>
              </thead>
              <tbody>
                {result.applicable_reviews.items.map((it, i) => {
                  const label = it.severity === 'REQUIRED' ? '필요' : it.severity === 'MAYBE' ? '검토' : '해당없음'
                  const cls = it.severity === 'REQUIRED' ? 'lr-signal-RED' : it.severity === 'MAYBE' ? 'lr-signal-YELLOW' : ''
                  return (
                    <tr key={i}>
                      <td>{it.name}</td>
                      <td className={cls}><strong>{label}</strong></td>
                      <td style={{ fontSize: 'var(--font-size-sm)' }}>
                        {it.triggered_reasons?.length > 0
                          ? it.triggered_reasons.join('; ')
                          : '—'}
                      </td>
                      <td style={{ fontSize: 'var(--font-size-xs)' }}>{it.law_ref}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <p className="lr-note" style={{ fontSize: 'var(--font-size-xs)' }}>
              ※ 일반 기준 자동 판정 결과이며, 지자체별 조례·특수 조건에 따라 변동 가능.
              교육환경·문화재 관련 심의는 좌표 기반 정밀 판정 미지원으로 별도 확인 필요.
            </p>
          </section>
        )}

        {/* 합필 정보 (해당 시) */}
        {multi && (
          <section className="lr-section">
            <h2>합필 진단 내역</h2>
            <p className="lr-note">
              산정 방식: <strong>{multi.aggregate.calc_method}</strong>
              {multi.aggregate.cross_jurisdiction && (
                <span className="lr-warn">
                  {' '}⚠ 시·도가 다른 필지 포함 — 사업성 시뮬레이션 목적
                </span>
              )}
            </p>
            {multi.aggregate.threshold_m2 && (
              <p className="lr-note">
                소규모 임계치:{' '}
                <strong>{multi.aggregate.threshold_m2.toLocaleString()}㎡</strong>
                {' — '}
                {multi.aggregate.threshold_basis}
              </p>
            )}
            <table className="lr-table">
              <thead>
                <tr>
                  <th>No.</th>
                  <th>주소</th>
                  <th>면적(㎡)</th>
                  <th>용도지역</th>
                  <th>관할</th>
                </tr>
              </thead>
              <tbody>
                {multi.parcels.map((p, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td>{p.address}</td>
                    <td className="right">{p.site_area?.toLocaleString()}</td>
                    <td>{p.zone_use}</td>
                    <td>{p.jurisdiction_name || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {/* 건축 개요 */}
        <section className="lr-section">
          <h2>건축 개요</h2>
          <table className="lr-table">
            <tbody>
              <BuildingInfoRow formData={formData} />
            </tbody>
          </table>
        </section>

        {/* 법규 검토 결과 — 메인 표 */}
        <section className="lr-section">
          <h2>법규 검토 결과</h2>
          <table className="lr-main-table">
            <thead>
              <tr>
                <th style={{ width: '14%' }}>항목</th>
                <th style={{ width: '24%' }}>법규 및 조항</th>
                <th style={{ width: '40%' }}>법정기준 / 설계내용</th>
                <th style={{ width: '12%' }}>적법여부</th>
                <th style={{ width: '10%' }}>점수</th>
              </tr>
            </thead>
            <tbody>
              {categories.map(([key, cat]) => {
                const reliefSuffix = cat.relief_info?.applied ? ' (완화)' : ''
                return (
                  <CategoryRow
                    key={key}
                    label={(CATEGORY_LABELS[key] || key) + reliefSuffix}
                    cat={cat}
                  />
                )
              })}
            </tbody>
          </table>
        </section>

        {/* 필수 수동검토 — 자동 판정 불가 항목 */}
        {(() => {
          const manual = categories.filter(([_, c]) => c.needs_manual_review)
          if (manual.length === 0) return null
          return (
            <section className="lr-section">
              <h2>필수 수동검토 항목 ({manual.length}건)</h2>
              <p className="lr-note">
                아래 항목은 입력값 부족으로 자동 pass/fail 판정이 불가합니다.
                설계 도면을 확인하여 수동 검토가 필요합니다.
              </p>
              <table className="lr-table">
                <thead>
                  <tr>
                    <th style={{ width: '20%' }}>항목</th>
                    <th>검토 사유 / 필요 입력값</th>
                  </tr>
                </thead>
                <tbody>
                  {manual.map(([key, c]) => (
                    <tr key={key}>
                      <td><strong>{CATEGORY_LABELS[key] || key}</strong></td>
                      <td style={{ fontSize: 'var(--font-size-sm)' }}>{c.notes}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )
        })()}

        {/* 데이터 품질·출처 */}
        {result.data_quality && (
          <DataQualitySection dq={result.data_quality} />
        )}

        {/* 위험·주의 요약 */}
        {(result.risks?.length > 0 || result.warnings?.length > 0) && (
          <section className="lr-section">
            <h2>검토 의견</h2>
            {result.risks?.length > 0 && (
              <div className="lr-risks">
                <h3>위험 항목 ({result.risks.length}건)</h3>
                <ul>
                  {result.risks.map((r, i) => (
                    <li key={i}><strong>{r.category}:</strong> {r.reason}</li>
                  ))}
                </ul>
              </div>
            )}
            {result.warnings?.length > 0 && (
              <div className="lr-warnings">
                <h3>검토 필요 ({result.warnings.length}건)</h3>
                <ul>
                  {result.warnings.map((w, i) => (
                    <li key={i}><strong>{w.category}:</strong> {w.reason}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}

        {/* 푸터 — 작성자/회사/면책 */}
        <section className="lr-footer">
          <table className="lr-sign-table">
            <tbody>
              <tr>
                <th>회사명</th>
                <td>{company || '—'}</td>
                <th>작성자</th>
                <td>{author || '—'}</td>
              </tr>
            </tbody>
          </table>
          <p className="lr-disclaimer">
            ※ 본 검토서는 arch-law-diagnose 자동 진단 시스템에 의해 작성되었으며,
            최종 법규 해석은 반드시 시니어 검토자/설계자가 확인해야 합니다.
            자동 진단 일자: {today}
          </p>
        </section>
      </div>

      <style>{styles}</style>
    </div>
  )
}

function BuildingInfoRow({ formData }) {
  const fd = formData || {}
  const site = parseFloat(fd.site_area) || 0
  const above = parseFloat(fd.floor_area_above) || 0
  const below = parseFloat(fd.floor_area_below) || 0
  const parking = parseFloat(fd.floor_area_parking_above) || 0
  const refuge = parseFloat(fd.floor_area_refuge) || 0
  const attic = parseFloat(fd.floor_area_attic_refuge) || 0
  const landscape = parseFloat(fd.landscape_area) || 0
  const publicOpen = parseFloat(fd.public_open_space_area) || 0
  const providedParking = fd.provided_parking_spaces
  const total = above + below
  const farArea = Math.max(0, above - parking - refuge - attic)
  const excluded = []
  if (below > 0) excluded.push(`지하 ${below.toLocaleString()}㎡`)
  if (parking > 0) excluded.push(`지상 주차장 ${parking.toLocaleString()}㎡`)
  if (refuge > 0) excluded.push(`피난안전구역 ${refuge.toLocaleString()}㎡`)
  if (attic > 0) excluded.push(`경사지붕 대피공간 ${attic.toLocaleString()}㎡`)

  const ratio = (a) => (site > 0 && a > 0 ? `(대지의 ${((a / site) * 100).toFixed(2)}%)` : '')

  return (
    <>
      <tr>
        <th>건축면적</th>
        <td>{fd.building_area ? `${parseFloat(fd.building_area).toLocaleString()}㎡` : '—'}</td>
        <th>연면적 (지상+지하)</th>
        <td>{total > 0 ? `${total.toLocaleString()}㎡` : '—'}</td>
      </tr>
      <tr>
        <th>지상 연면적</th>
        <td>{above > 0 ? `${above.toLocaleString()}㎡` : '—'}</td>
        <th>지하 연면적</th>
        <td>{below > 0 ? `${below.toLocaleString()}㎡` : '—'}</td>
      </tr>
      <tr>
        <th>용적률 산정 면적</th>
        <td colSpan={3}>
          <strong>{farArea.toLocaleString()}㎡</strong>
          {excluded.length > 0 && (
            <span className="lr-note-sm"> · 제외: {excluded.join(', ')} (건축법 시행령 제119조)</span>
          )}
        </td>
      </tr>
      <tr>
        <th>층수 / 높이</th>
        <td colSpan={3}>
          지상 {fd.floors_above || '—'}층 / 지하 {fd.floors_below || 0}층 / 높이 {fd.height || '—'}m
        </td>
      </tr>
      {(publicOpen > 0 || landscape > 0) && (
        <tr>
          <th>공개공지</th>
          <td>
            {publicOpen > 0 ? `${publicOpen.toLocaleString()}㎡` : '—'}
            {publicOpen > 0 && <span className="lr-note-sm"> {ratio(publicOpen)}</span>}
          </td>
          <th>조경면적</th>
          <td>
            {landscape > 0 ? `${landscape.toLocaleString()}㎡` : '—'}
            {landscape > 0 && <span className="lr-note-sm"> {ratio(landscape)}</span>}
          </td>
        </tr>
      )}
      {providedParking && (
        <tr>
          <th>계획 주차대수</th>
          <td colSpan={3}>{providedParking}대</td>
        </tr>
      )}
    </>
  )
}

function CategoryRow({ label, cat }) {
  const compliance = COMPLIANCE_LABEL[cat.pass] || COMPLIANCE_LABEL.null

  // 법규 인용 — law_refs 우선, 없으면 source
  let lawRefs = ''
  if (cat.law_refs && cat.law_refs.length > 0) {
    lawRefs = cat.law_refs.map((r) => r.name).join('\n')
  } else if (cat.source) {
    lawRefs = cat.source
  }

  // 법정기준 / 설계내용
  const standardDesign = buildStandardDesign(cat)

  // 설비·소방 — items 별 상세
  const fireSafetyItems = cat.items && cat.items.length > 0 ? cat.items : null

  return (
    <tr>
      <td><strong>{label}</strong></td>
      <td className="lr-law-cell">{lawRefs}</td>
      <td className="lr-standard-cell">
        {standardDesign}
        {fireSafetyItems && (
          <div className="lr-fire-items">
            {fireSafetyItems.map((it, i) => {
              const statusLabel =
                it.status === 'required' ? '의무'
                : it.status === 'not_required' ? '면제'
                : it.status === 'needs_review' ? '검토필요' : '미정'
              return (
                <div key={i} className="lr-fire-item">
                  <strong>· {it.name}</strong> [{statusLabel}]
                  {it.basis && <span className="lr-note-sm"> {it.basis}</span>}
                  {it.note && <div className="lr-note-sm">  {it.note}</div>}
                </div>
              )
            })}
          </div>
        )}
      </td>
      <td className={`lr-compliance ${compliance.cls}`}>{compliance.label}</td>
      <td className="right">
        {cat.score != null ? `${cat.score}/10` : '—'}
      </td>
    </tr>
  )
}

function DataQualitySection({ dq }) {
  const issues = dq.issues || []
  const sources = []
  if (dq.zone_use_source === 'user') sources.push('용도지역: 사용자 직접 지정')
  else if (dq.zone_use_source === 'vworld') sources.push('용도지역: VWorld 자동 조회')
  else sources.push('용도지역: 미확인')
  sources.push(dq.ordinance_used ? '조례: 실제 조례값' : '조례: 시행령 기본값(fallback)')
  sources.push(dq.luris_used ? 'LURIS: 활성' : 'LURIS: 비활성')
  sources.push(dq.llm_used ? 'AI(Claude): 활성' : 'AI(Claude): 비활성')
  if (dq.land_cache_stale) {
    sources.push(`토지정보 캐시: ${dq.land_cache_age_days}일 전 (stale)`)
  }
  return (
    <section className="lr-section">
      <h2>데이터 품질·출처</h2>
      <table className="lr-table">
        <tbody>
          <tr>
            <th style={{ width: '20%' }}>데이터 출처</th>
            <td style={{ fontSize: 'var(--font-size-sm)' }}>{sources.join(' · ')}</td>
          </tr>
        </tbody>
      </table>
      {issues.length > 0 && (
        <table className="lr-table" style={{ marginTop: 'var(--gap-sm)' }}>
          <thead>
            <tr>
              <th style={{ width: '12%' }}>구분</th>
              <th>주의 사항</th>
            </tr>
          </thead>
          <tbody>
            {issues.map((iss, i) => {
              const lvl = iss.level === 'error' ? '🔴 오류'
                : iss.level === 'warn' ? '⚠ 주의' : 'ℹ 정보'
              return (
                <tr key={i}>
                  <td>{lvl}</td>
                  <td style={{ fontSize: 'var(--font-size-sm)' }}>{iss.msg}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </section>
  )
}

function buildStandardDesign(cat) {
  const lines = []

  if (cat.limit_pct != null) {
    lines.push(`• 법정기준: 한도 ${cat.limit_pct}%`)
    if (cat.actual_pct != null) {
      lines.push(`• 설계내용: 실제 ${cat.actual_pct}%`)
      if (cat.excess_pct > 0) {
        lines.push(`  (${cat.excess_pct}%p 초과)`)
      }
    }
  } else if (cat.required_pct != null) {
    lines.push(`• 법정기준: 의무 ${cat.required_pct}%`)
    if (cat.actual_pct != null) {
      lines.push(`• 설계내용: ${cat.actual_pct}%`)
    }
  } else if (cat.required_spaces != null) {
    lines.push(`• 법정기준: ${cat.required_spaces}대 의무`)
    if (cat.provided_spaces != null) {
      lines.push(`• 설계내용: ${cat.provided_spaces}대 계획`)
    }
  } else if (cat.actual_height_m != null) {
    lines.push(`• 설계내용: 높이 ${cat.actual_height_m}m`)
    if (cat.street_block_max_height_m) {
      lines.push(`• 법정기준 §60: 가로구역 최고 ${cat.street_block_max_height_m}m`)
    }
    if (cat.shadow_min_setback_m) {
      lines.push(`• 법정기준 §86 ①: 정북 이격 ${cat.shadow_min_setback_m}m 이상`)
    }
    if (cat.north_setback_m != null) {
      lines.push(`• 설계내용: 정북 이격 ${cat.north_setback_m}m`)
    }
    if (cat.exemptions && cat.exemptions.length > 0) {
      lines.push(`• 적용 제외: ${cat.exemptions.join(' / ')}`)
    }
    if (cat.parcel_north_depth_m) {
      lines.push(`• 참고: 폴리곤 N-S 깊이 ≈ ${cat.parcel_north_depth_m}m`)
    }
  }

  if (cat.exempt === true) {
    lines.push('• 면제 대상')
  }

  if (cat.notes) {
    lines.push(`• ${cat.notes}`)
  }

  return lines.join('\n')
}

const styles = `
.lr-overlay {
  position: fixed; inset: 0; background: var(--color-print-overlay);
  z-index: 9999; overflow-y: auto;
  font-family: var(--font-primary);
}
.lr-toolbar {
  position: sticky; top: 0; z-index: 10;
  background: var(--color-print-toolbar); color: var(--color-text-on-accent);
  padding: var(--gap-md) var(--layout-content-px); display: flex; gap: 16px;
  justify-content: space-between; align-items: center;
  flex-wrap: wrap;
}
.lr-meta-inputs { display: flex; gap: var(--gap-sm); flex-wrap: wrap; flex: 1; }
.lr-input {
  padding: 6px var(--gap-md); border-radius: var(--card-radius-sm); border: 1px solid var(--color-print-border);
  background: var(--color-print-input); color: var(--color-text-on-accent); font-size: var(--font-size-base);
  min-width: 140px;
}
.lr-input::placeholder { color: var(--color-text-subtle); }
.lr-buttons { display: flex; gap: var(--gap-sm); }
.lr-btn {
  padding: var(--gap-sm) 16px; border-radius: var(--card-radius-sm); border: 1px solid var(--color-print-border);
  background: var(--color-print-input); color: var(--color-text-on-accent); cursor: pointer; font-size: var(--font-size-base);
}
.lr-btn:hover { background: var(--color-print-toolbar-hover); }
.lr-btn.primary { background: var(--color-accent); border-color: var(--color-accent); }
.lr-btn.primary:hover { background: var(--color-accent-hover); }

.lr-page {
  background: var(--color-bg-surface); max-width: 820px; margin: var(--layout-content-px) auto;
  padding: 48px 56px; box-shadow: var(--shadow-lg);
  font-size: 13px; color: var(--color-text-body); line-height: 1.6;
}
.lr-title {
  text-align: center; font-size: var(--font-size-2xl); font-weight: var(--font-weight-bold);
  letter-spacing: 12px; margin: 0 0 var(--gap-xl);
  border-bottom: 3px double var(--color-text-primary); padding-bottom: var(--gap-md);
}
.lr-header-table, .lr-table, .lr-main-table, .lr-sign-table {
  width: 100%; border-collapse: collapse; margin-bottom: 16px;
}
.lr-header-table th, .lr-table th, .lr-main-table th, .lr-sign-table th {
  background: var(--color-bg-input-disabled); font-weight: var(--font-weight-semibold); padding: var(--gap-sm) var(--gap-md);
  border: 1px solid var(--color-text-subtle); text-align: left; vertical-align: middle;
  white-space: nowrap;
}
.lr-header-table td, .lr-table td, .lr-main-table td, .lr-sign-table td {
  padding: var(--gap-sm) var(--gap-md); border: 1px solid var(--color-text-subtle); vertical-align: middle;
}
.lr-header-table th { width: 90px; }
.lr-section { margin-top: var(--layout-content-px); }
.lr-section h2 {
  font-size: var(--font-size-md); font-weight: var(--font-weight-bold); border-left: 4px solid var(--color-accent);
  padding-left: 10px; margin: 16px 0 var(--gap-md);
}
.lr-section h3 { font-size: 13px; font-weight: var(--font-weight-semibold); margin: var(--gap-sm) 0 var(--gap-xs); }
.lr-section ul { margin: var(--gap-xs) 0 var(--gap-sm) var(--gap-lg); padding: 0; }
.lr-section li { margin-bottom: var(--gap-xs); }
.lr-main-table th {
  background: var(--color-border); text-align: center; font-size: var(--font-size-sm);
}
.lr-main-table td { font-size: var(--font-size-sm); vertical-align: top; }
.lr-law-cell { white-space: pre-line; font-size: var(--font-size-xs); color: var(--color-text-muted); }
.lr-standard-cell { white-space: pre-line; font-size: 11.5px; }
.lr-fire-items { margin-top: 6px; padding-top: 6px; border-top: 1px dashed var(--color-border-strong); }
.lr-fire-item { font-size: var(--font-size-xs); margin-bottom: 3px; }
.lr-compliance { text-align: center; font-weight: var(--font-weight-semibold); }
.lr-compliance.compliant { background: var(--color-success-bg); color: var(--color-success); }
.lr-compliance.non-compliant { background: var(--color-danger-bg); color: var(--color-danger); }
.lr-compliance.review-needed { background: var(--color-warning-bg); color: var(--color-warning); }
.right { text-align: right; }
.lr-signal-GREEN { color: var(--color-success); }
.lr-signal-YELLOW { color: var(--color-warning); }
.lr-signal-RED { color: var(--color-danger); }
.lr-risks { border-left: 3px solid var(--color-danger); padding-left: var(--gap-md); margin-bottom: var(--gap-md); }
.lr-risks h3 { color: var(--color-danger); }
.lr-warnings { border-left: 3px solid var(--color-warning); padding-left: var(--gap-md); }
.lr-warnings h3 { color: var(--color-warning); }
.lr-note { font-size: var(--font-size-sm); color: var(--color-text-muted); margin-bottom: var(--gap-sm); }
.lr-note-sm { font-size: var(--font-size-xs); color: var(--color-text-faint); }
.lr-warn { color: var(--color-danger); font-weight: var(--font-weight-semibold); }
.lr-footer { margin-top: 40px; }
.lr-disclaimer {
  margin-top: 16px; font-size: var(--font-size-xs); color: var(--color-text-faint);
  padding: var(--gap-md); background: var(--color-bg-surface-alt); border-radius: var(--gap-xs);
  border-left: 3px solid var(--color-text-subtle);
}

@media print {
  .lr-overlay { background: var(--color-bg-surface); position: static; }
  .no-print { display: none !important; }
  .lr-page {
    box-shadow: none; margin: 0; padding: 20mm 15mm;
    max-width: 100%; font-size: var(--font-size-xs);
  }
  .lr-title { font-size: var(--font-size-xl); margin-bottom: var(--gap-lg); }
  .lr-section { margin-top: 16px; page-break-inside: avoid; }
  .lr-main-table { page-break-inside: auto; }
  .lr-main-table tr { page-break-inside: avoid; page-break-after: auto; }
  @page { size: A4; margin: 0; }
}
`

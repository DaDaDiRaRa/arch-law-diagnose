/**
 * 공모지침 불러오기 — Competition Analyzer가 추출한 _brief.json을 사업성 입력으로 자동 채움.
 *
 * 흐름: 목록 열기 → 공모 선택 → (다부지면) 부지 선택 → target_* 자동 입력.
 * 주소·용도는 brief에 없을 수 있어 사용자가 직접 입력/선택.
 */
import { useState } from 'react'
import { api } from '../../utils/api'
import { useFeasibilityStore } from '../../stores/feasibilityStore'
import BriefList from './BriefList'

const fmt = (v, d = 0) =>
  v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: d })

export default function BriefImportPanel() {
  const { applyBriefSite, briefApplied, loadBriefSitesToMulti, setView } = useFeasibilityStore()
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState(null) // 매핑된 brief
  const [siteLoading, setSiteLoading] = useState(false)
  const [error, setError] = useState(null) // brief 선택(매핑) 단계 오류

  const toggle = () => setOpen((v) => !v)

  const selectBrief = async (fileId) => {
    setSiteLoading(true)
    setError(null)
    try {
      const mapped = await api.getBriefImport(fileId)
      setSelected(mapped)
    } catch (e) {
      setError(e.message || 'brief 불러오기 실패')
    } finally {
      setSiteLoading(false)
    }
  }

  const applySite = (site) => {
    applyBriefSite(site, {
      competition_name: selected.competition_name,
      applicant_type: selected.applicant_type,
      relief: selected.relief,
    })
    setOpen(false)
  }

  // 다부지 공모 → E2 다중 비교로 전체 부지 전송 + 탭 전환
  const compareAllSites = () => {
    loadBriefSitesToMulti(selected)
    setView('multi')
    setOpen(false)
  }

  return (
    <div
      className="border"
      style={{
        borderColor: 'var(--hairline)',
        borderRadius: 'var(--radius-sm)',
        background: 'var(--canvas-inset)',
      }}
    >
      <button
        type="button"
        onClick={toggle}
        className="w-full flex items-center justify-between px-3 py-2.5 text-left"
      >
        <span className="text-xs font-semibold" style={{ color: 'var(--body)' }}>
          공모지침 불러오기
          <span className="text-[10px] font-normal ml-2" style={{ color: 'var(--faint)' }}>
            지침 분석 결과에서 요구치 자동 채움
          </span>
        </span>
        <span className="text-xs" style={{ color: 'var(--faint)' }}>{open ? '▲' : '▼'}</span>
      </button>

      {/* 적용 완료 표시 */}
      {briefApplied && !open && (
        <div className="px-3 pb-2 -mt-1">
          <span
            className="text-[11px] px-2 py-1"
            style={{
              backgroundColor: 'rgba(22,163,74,0.1)',
              color: 'var(--ok)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--hairline)',
            }}
          >
            "{briefApplied.competition_name || '공모'}" {briefApplied.site_id} 적용됨
          </span>
        </div>
      )}

      {open && (
        <div className="px-3 pb-3 pt-3" style={{ borderTop: '1px solid var(--hairline)' }}>
          {error && (
            <div
              className="text-[11px] px-2 py-1.5 rounded mb-2"
              style={{
                color: 'var(--error)',
                background: 'var(--canvas-elevated)',
                border: '1px solid var(--hairline)',
                borderLeft: '3px solid var(--error)',
              }}
            >
              {error}
            </div>
          )}

          {/* 1단계: 공모 목록 (공용 BriefList — 카테고리 필터 + 검색) */}
          {!selected && <BriefList onPick={selectBrief} picking={siteLoading} />}

          {siteLoading && <Note>부지 정보 불러오는 중…</Note>}

          {/* 2단계: 부지 선택 */}
          {selected && (
            <div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="text-[11px] mb-2"
                style={{ color: 'var(--mute)' }}
              >
                ← 다른 공모 선택
              </button>
              <div className="text-xs font-medium mb-1" style={{ color: 'var(--ink)' }}>
                {selected.competition_name}
              </div>
              {/* 자동 채워질 공통 정보 (신청주체·인증 → 완화 레버) */}
              {(selected.applicant_type ||
                selected.relief?.green_grade ||
                selected.relief?.energy_grade ||
                selected.relief?.renewable_pct != null ||
                selected.relief?.bf_grade) && (
                <div className="flex flex-wrap gap-1 mb-2">
                  {selected.applicant_type && (
                    <AutoBadge>신청주체 {selected.applicant_type}</AutoBadge>
                  )}
                  {selected.relief?.green_grade && (
                    <AutoBadge>녹색건축 {selected.relief.green_grade}</AutoBadge>
                  )}
                  {selected.relief?.energy_grade && (
                    <AutoBadge>ZEB {selected.relief.energy_grade}등급</AutoBadge>
                  )}
                  {selected.relief?.renewable_pct != null && (
                    <AutoBadge>신재생 {selected.relief.renewable_pct}%</AutoBadge>
                  )}
                  {selected.relief?.bf_grade && (
                    <AutoBadge>BF {selected.relief.bf_grade}</AutoBadge>
                  )}
                </div>
              )}
              {selected.sites.length > 1 && (
                <div
                  className="mb-2 p-2 rounded"
                  style={{
                    border: '1px dashed var(--hairline)',
                    background: 'var(--canvas-elevated)',
                  }}
                >
                  <p className="text-[10px] mb-1.5" style={{ color: 'var(--mute)' }}>
                    부지가 {selected.sites.length}개입니다. 아래에서 한 곳만 검토하거나,
                    전체를 한 번에 비교할 수 있습니다.
                  </p>
                  <button
                    type="button"
                    onClick={compareAllSites}
                    className="w-full text-[11px] font-semibold text-white rounded px-2.5 py-1.5"
                    style={{ backgroundColor: 'var(--brand)' }}
                  >
                    {selected.sites.length}개 부지 전체 비교 (다중 대지)
                  </button>
                </div>
              )}
              <div className="space-y-2">
                {selected.sites.map((s, i) => (
                  <div
                    key={i}
                    className="border p-2.5"
                    style={{
                      borderColor: 'var(--hairline)',
                      borderRadius: 'var(--radius-sm)',
                      background: 'var(--canvas-elevated)',
                    }}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-semibold" style={{ color: 'var(--ink)' }}>
                        {s.site_id || `부지 ${i + 1}`}
                      </span>
                      <button
                        type="button"
                        onClick={() => applySite(s)}
                        className="text-[11px] font-semibold text-white rounded px-2.5 py-1"
                        style={{ backgroundColor: 'var(--brand)' }}
                      >
                        이 부지로 채우기
                      </button>
                    </div>
                    {s.address && (
                      <div className="text-[10px] mb-1.5" style={{ color: 'var(--body)' }}>
                        {s.address}
                      </div>
                    )}
                    <div className="grid grid-cols-3 gap-x-2 gap-y-1 text-[10px]" style={{ color: 'var(--body)' }}>
                      <Spec label="대지면적" v={s.site_area_sqm} unit="㎡" />
                      <Spec label="연면적" v={s.target_floor_area_sqm} unit="㎡" />
                      <Spec label="건폐율" v={s.target_building_coverage_pct} unit="%" />
                      <Spec label="용적률" v={s.target_far_pct} unit="%" />
                      <Spec label="최고높이" v={s.target_max_height_m} unit="m" />
                      <Spec label="공개공지" v={s.target_open_space_sqm} unit="㎡" />
                      <Spec label="주차" v={s.target_parking_count} unit="대" />
                    </div>
                    {s.limits_determined_by === '심의' && (
                      <div
                        className="text-[10px] mt-1.5 px-1.5 py-1"
                        style={{
                          color: 'var(--warn-deep)',
                          background: 'var(--warn-bg)',
                          borderRadius: 'var(--radius-sm)',
                        }}
                      >
                        위 건폐율·용적률·높이는 <b>심의로 정해진 값</b> — 법정 한도와 다를 수 있고,
                        초과분은 초과가 아니라 심의 전제로 표시됩니다.
                      </div>
                    )}
                    {s.parking_note && (
                      <div className="text-[10px] mt-1" style={{ color: 'var(--mute)' }}>
                        주차 근거: {s.parking_note}
                      </div>
                    )}
                    {(s.facility_hint || s.facility_use || s.facility_use_candidates?.length > 0) && (
                      <div
                        className="text-[10px] mt-1.5 pt-1.5 space-y-0.5"
                        style={{ borderTop: '1px solid var(--hairline)' }}
                      >
                        {s.facility_use ? (
                          <div style={{ color: 'var(--body)' }}>
                            시설 용도 자동 감지:{' '}
                            <span className="font-semibold" style={{ color: 'var(--ok)' }}>
                              {s.facility_use}
                            </span>
                          </div>
                        ) : s.facility_use_candidates?.length > 1 ? (
                          <div style={{ color: 'var(--mute)' }}>
                            용도 후보: {s.facility_use_candidates.join(', ')}{' '}
                            <span style={{ color: 'var(--faint)' }}>(복합 — 직접 선택)</span>
                          </div>
                        ) : null}
                        {s.facility_hint && (
                          <div style={{ color: 'var(--mute)' }}>용도 힌트: {s.facility_hint}</div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              <p className="text-[10px] mt-2" style={{ color: 'var(--faint)' }}>
                주소·신청주체·인증(완화 레버)·용도지역(자동조회)이 채워집니다. <b>시설 용도</b>는
                괄호표기에서 하나로 명확할 때만 자동 채움 — 복합·불명이면 직접 선택하세요.
                주소가 비어 있으면 직접 입력하세요.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Note({ children }) {
  return <div className="text-[11px] py-1" style={{ color: 'var(--mute)' }}>{children}</div>
}

function AutoBadge({ children }) {
  return (
    <span
      className="text-[10px] px-1.5 py-0.5"
      style={{
        backgroundColor: 'rgba(22,163,74,0.1)',
        color: 'var(--ok)',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--hairline)',
        fontFamily: 'var(--font-mono)',
        fontSize: '10px',
      }}
    >
      {children}
    </span>
  )
}

function Spec({ label, v, unit }) {
  return (
    <div>
      <span style={{ color: 'var(--faint)' }}>{label} </span>
      <span className="font-medium" style={{ color: 'var(--body)' }}>
        {v == null ? '—' : `${fmt(v, 1)}${unit}`}
      </span>
    </div>
  )
}

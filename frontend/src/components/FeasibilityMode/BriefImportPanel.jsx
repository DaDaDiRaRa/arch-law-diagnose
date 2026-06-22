/**
 * 공모지침 불러오기 — Competition Analyzer가 추출한 _brief.json을 사업성 입력으로 자동 채움.
 *
 * 흐름: 목록 열기 → 공모 선택 → (다부지면) 부지 선택 → target_* 자동 입력.
 * 주소·용도는 brief에 없을 수 있어 사용자가 직접 입력/선택.
 */
import { useState } from 'react'
import { api } from '../../utils/api'
import { useFeasibilityStore } from '../../stores/feasibilityStore'

const fmt = (v, d = 0) =>
  v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: d })

export default function BriefImportPanel() {
  const { applyBriefSite, briefApplied } = useFeasibilityStore()
  const [open, setOpen] = useState(false)
  const [briefs, setBriefs] = useState(null) // null=미로드, []=없음
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null) // 매핑된 brief
  const [siteLoading, setSiteLoading] = useState(false)

  const toggle = async () => {
    const next = !open
    setOpen(next)
    if (next && briefs === null) {
      setLoading(true)
      setError(null)
      try {
        const res = await api.listBriefs()
        setBriefs(res.briefs || [])
      } catch (e) {
        setError(e.message || '목록 조회 실패')
        setBriefs([])
      } finally {
        setLoading(false)
      }
    }
  }

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

  return (
    <div className="border border-gray-200 rounded-lg bg-gray-50">
      <button
        type="button"
        onClick={toggle}
        className="w-full flex items-center justify-between px-3 py-2.5 text-left"
      >
        <span className="text-xs font-semibold text-gray-700">
          📋 공모지침 불러오기
          <span className="text-[10px] font-normal text-gray-400 ml-2">
            지침 분석 결과에서 요구치 자동 채움
          </span>
        </span>
        <span className="text-gray-400 text-xs">{open ? '▲' : '▼'}</span>
      </button>

      {/* 적용 완료 표시 */}
      {briefApplied && !open && (
        <div className="px-3 pb-2 -mt-1">
          <span
            className="text-[11px] px-2 py-1 rounded"
            style={{ backgroundColor: 'rgba(22,163,74,0.1)', color: 'var(--color-success)' }}
          >
            ✓ "{briefApplied.competition_name || '공모'}" {briefApplied.site_id} 적용됨
          </span>
        </div>
      )}

      {open && (
        <div className="px-3 pb-3 border-t border-gray-200 pt-3">
          {loading && <Note>목록 불러오는 중…</Note>}
          {error && (
            <div className="text-[11px] text-red-600 bg-red-50 border border-red-200 px-2 py-1.5 rounded mb-2">
              {error}
            </div>
          )}

          {!loading && briefs && briefs.length === 0 && !error && (
            <Note>
              불러올 공모지침이 없습니다. (서버의 BRIEF_DIR에 _brief.json 필요 —
              Competition Analyzer의 _briefs 폴더/버킷 연결)
            </Note>
          )}

          {/* 1단계: 공모 목록 */}
          {!selected && briefs && briefs.length > 0 && (
            <div className="space-y-1.5">
              {briefs.map((b) => (
                <button
                  key={b.file_id}
                  type="button"
                  onClick={() => selectBrief(b.file_id)}
                  disabled={siteLoading}
                  className="w-full text-left border border-gray-200 rounded px-3 py-2 bg-white hover:border-gray-400 transition-colors disabled:opacity-50"
                >
                  <div className="text-xs font-medium text-gray-800 truncate">
                    {b.competition_name}
                  </div>
                  <div className="text-[10px] text-gray-500 mt-0.5 flex gap-2">
                    {b.facility_type && (
                      <span className="px-1.5 py-0.5 rounded bg-gray-100">{b.facility_type}</span>
                    )}
                    <span>부지 {b.site_count}개</span>
                    {b.analyzed_at && <span>· {b.analyzed_at.slice(0, 10)}</span>}
                  </div>
                </button>
              ))}
            </div>
          )}

          {siteLoading && <Note>부지 정보 불러오는 중…</Note>}

          {/* 2단계: 부지 선택 */}
          {selected && (
            <div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="text-[11px] text-gray-500 hover:text-gray-700 mb-2"
              >
                ← 다른 공모 선택
              </button>
              <div className="text-xs font-medium text-gray-800 mb-1">
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
                <p className="text-[10px] text-gray-500 mb-2">
                  부지가 {selected.sites.length}개입니다. 검토할 부지를 하나 선택하세요.
                </p>
              )}
              <div className="space-y-2">
                {selected.sites.map((s, i) => (
                  <div key={i} className="border border-gray-200 rounded p-2.5 bg-white">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-semibold text-gray-800">
                        {s.site_id || `부지 ${i + 1}`}
                      </span>
                      <button
                        type="button"
                        onClick={() => applySite(s)}
                        className="text-[11px] font-semibold text-white rounded px-2.5 py-1"
                        style={{ backgroundColor: 'var(--color-accent)' }}
                      >
                        이 부지로 채우기
                      </button>
                    </div>
                    {s.address && (
                      <div className="text-[10px] text-gray-600 mb-1.5">
                        📍 {s.address}
                      </div>
                    )}
                    <div className="grid grid-cols-3 gap-x-2 gap-y-1 text-[10px] text-gray-600">
                      <Spec label="대지면적" v={s.site_area_sqm} unit="㎡" />
                      <Spec label="연면적" v={s.target_floor_area_sqm} unit="㎡" />
                      <Spec label="건폐율" v={s.target_building_coverage_pct} unit="%" />
                      <Spec label="용적률" v={s.target_far_pct} unit="%" />
                      <Spec label="최고높이" v={s.target_max_height_m} unit="m" />
                      <Spec label="공개공지" v={s.target_open_space_sqm} unit="㎡" />
                    </div>
                    {(s.facility_hint || s.facility_use || s.facility_use_candidates?.length > 0) && (
                      <div className="text-[10px] mt-1.5 pt-1.5 border-t border-gray-100 space-y-0.5">
                        {s.facility_use ? (
                          <div className="text-gray-700">
                            시설 용도 자동 감지:{' '}
                            <span className="font-semibold" style={{ color: 'var(--color-success)' }}>
                              {s.facility_use}
                            </span>
                          </div>
                        ) : s.facility_use_candidates?.length > 1 ? (
                          <div className="text-gray-500">
                            용도 후보: {s.facility_use_candidates.join(', ')}{' '}
                            <span className="text-gray-400">(복합 — 직접 선택)</span>
                          </div>
                        ) : null}
                        {s.facility_hint && (
                          <div className="text-gray-500">용도 힌트: {s.facility_hint}</div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-gray-400 mt-2">
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
  return <div className="text-[11px] text-gray-500 py-1">{children}</div>
}

function AutoBadge({ children }) {
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 rounded"
      style={{ backgroundColor: 'rgba(22,163,74,0.1)', color: 'var(--color-success)' }}
    >
      {children}
    </span>
  )
}

function Spec({ label, v, unit }) {
  return (
    <div>
      <span className="text-gray-400">{label} </span>
      <span className="font-medium text-gray-700">
        {v == null ? '—' : `${fmt(v, 1)}${unit}`}
      </span>
    </div>
  )
}

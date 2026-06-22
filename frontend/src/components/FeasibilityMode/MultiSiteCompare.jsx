/**
 * 다중 대지 동시 비교 — 여러 부지의 사업성을 한 번에 계산해 나란히 비교.
 *
 * 흐름: 부지 추가(수동) 또는 공모지침에서 일괄 불러오기 → 각 부지 주소·용도 입력
 *       → 전체 비교 실행 → 매트릭스.
 * brief는 주소가 없으므로(target만 자동) 부지별 주소·용도는 직접 입력해야 함.
 */
import { useState } from 'react'
import { api } from '../../utils/api'
import { useFeasibilityStore } from '../../stores/feasibilityStore'

const FACILITY_USES = [
  '제1종근린생활시설', '제2종근린생활시설', '근린생활시설',
  '공동주택', '단독주택', '업무시설', '공공업무시설', '판매시설',
  '숙박시설', '의료시설', '교육연구시설', '문화및집회시설', '종교시설',
  '운동시설', '노유자시설', '위락시설', '공장', '창고시설', '기타',
]

const fmt = (v, d = 0) =>
  v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: d })

const ROWS = [
  { key: 'zone', label: '용도지역', get: (r) => r?.land_facts?.zone_use || '미확인', text: true },
  { key: 'far', label: '가능 용적률', unit: '%', d: 1, higherBetter: true, get: (r) => r?.proposal?.far_pct },
  { key: 'cov', label: '가능 건폐율', unit: '%', d: 1, higherBetter: true, get: (r) => r?.proposal?.max_building_coverage_pct },
  { key: 'floor', label: '가능 연면적', unit: '㎡', d: 0, higherBetter: true, get: (r) => r?.proposal?.max_floor_area_sqm },
  { key: 'parking', label: '권장 주차', unit: '대', d: 0, higherBetter: false, get: (r) => r?.proposal?.recommended_parking_spaces },
]

const VERDICT_COLOR = {
  '참여 권장': 'var(--color-success)',
  '협상 필요': 'var(--color-warning)',
  '패스 권장': 'var(--color-danger)',
  '정보 부족': 'var(--color-text-faint)',
}

export default function MultiSiteCompare() {
  const {
    multiSites, addMultiSite, updateMultiSite, removeMultiSite, clearMultiSites,
    loadBriefSitesToMulti, runMulti, multiResults, multiLoading, multiError,
  } = useFeasibilityStore()

  return (
    <div className="space-y-5">
      <BriefLoader onLoad={loadBriefSitesToMulti} />

      {/* 부지 엔트리 편집 */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-800">
            비교할 부지 ({multiSites.length})
          </h3>
          <div className="flex gap-2">
            {multiSites.length > 0 && (
              <button
                onClick={clearMultiSites}
                className="text-[11px] text-gray-400 hover:text-gray-600"
              >
                전체 삭제
              </button>
            )}
            <button
              onClick={() => addMultiSite()}
              className="text-[11px] font-medium px-2.5 py-1 rounded border border-gray-300 hover:bg-gray-50"
            >
              + 부지 추가
            </button>
          </div>
        </div>

        {multiSites.length === 0 ? (
          <div className="text-[11px] text-gray-500 bg-gray-50 border border-gray-200 rounded-lg px-4 py-3">
            부지를 추가하거나 위의 "공모지침에서 부지 불러오기"로 시작하세요.
          </div>
        ) : (
          <div className="space-y-2.5">
            {multiSites.map((site, i) => (
              <SiteRow
                key={site.id}
                site={site}
                index={i}
                onUpdate={(patch) => updateMultiSite(site.id, patch)}
                onRemove={() => removeMultiSite(site.id)}
              />
            ))}
          </div>
        )}
      </section>

      {multiError && (
        <div className="text-xs text-red-600 bg-red-50 border border-red-200 px-3 py-2 rounded">
          {multiError}
        </div>
      )}

      {multiSites.length > 0 && (
        <button
          onClick={runMulti}
          disabled={multiLoading}
          className="w-full py-2.5 text-xs font-semibold text-white rounded-lg shadow-sm disabled:opacity-50"
          style={{ backgroundColor: 'var(--color-accent)' }}
        >
          {multiLoading ? '비교 계산 중…' : `전체 비교 실행 (${multiSites.length}개 부지)`}
        </button>
      )}

      {multiResults && <CompareMatrix results={multiResults} />}
    </div>
  )
}

// ── 공모지침 일괄 로더 ──────────────────────────────────────────────────
function BriefLoader({ onLoad }) {
  const [open, setOpen] = useState(false)
  const [briefs, setBriefs] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const toggle = async () => {
    const next = !open
    setOpen(next)
    if (next && briefs === null) {
      setLoading(true)
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

  const pick = async (fileId) => {
    setLoading(true)
    setError(null)
    try {
      const mapped = await api.getBriefImport(fileId)
      onLoad(mapped)
      setOpen(false)
    } catch (e) {
      setError(e.message || 'brief 불러오기 실패')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="border border-gray-200 rounded-lg bg-gray-50">
      <button
        onClick={toggle}
        className="w-full flex items-center justify-between px-3 py-2.5 text-left"
      >
        <span className="text-xs font-semibold text-gray-700">
          📋 공모지침에서 부지 불러오기
          <span className="text-[10px] font-normal text-gray-400 ml-2">
            다부지 공모를 한 번에 비교
          </span>
        </span>
        <span className="text-gray-400 text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 border-t border-gray-200 pt-3">
          {loading && <div className="text-[11px] text-gray-500 py-1">불러오는 중…</div>}
          {error && (
            <div className="text-[11px] text-red-600 bg-red-50 border border-red-200 px-2 py-1.5 rounded mb-2">{error}</div>
          )}
          {!loading && briefs && briefs.length === 0 && (
            <div className="text-[11px] text-gray-500 py-1">불러올 공모지침이 없습니다.</div>
          )}
          {briefs && briefs.length > 0 && (
            <div className="space-y-1.5">
              {briefs.map((b) => (
                <button
                  key={b.file_id}
                  onClick={() => pick(b.file_id)}
                  className="w-full text-left border border-gray-200 rounded px-3 py-2 bg-white hover:border-gray-400"
                >
                  <div className="text-xs font-medium text-gray-800 truncate">{b.competition_name}</div>
                  <div className="text-[10px] text-gray-500 mt-0.5">
                    부지 {b.site_count}개 {b.facility_type && `· ${b.facility_type}`}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── 부지 한 행 (편집) ──────────────────────────────────────────────────
function SiteRow({ site, index, onUpdate, onRemove }) {
  const needAddr = !site.address
  const needUse = !site.facility_use
  return (
    <div className="border border-gray-200 rounded-lg p-3 bg-white">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] text-gray-400 w-5">{index + 1}</span>
        <input
          value={site.site_label}
          onChange={(e) => onUpdate({ site_label: e.target.value })}
          className="flex-1 text-xs font-semibold border border-gray-200 rounded px-2 py-1"
          placeholder="부지 이름"
        />
        <button
          onClick={onRemove}
          className="text-gray-300 hover:text-red-500 px-1"
          title="삭제"
        >
          ×
        </button>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <div className="col-span-2">
          <input
            value={site.address}
            onChange={(e) => onUpdate({ address: e.target.value })}
            placeholder="주소 *"
            className={`w-full text-xs border rounded px-2 py-1 ${needAddr ? 'border-red-300' : 'border-gray-300'}`}
          />
        </div>
        <select
          value={site.facility_use}
          onChange={(e) => onUpdate({ facility_use: e.target.value })}
          className={`text-xs border rounded px-2 py-1 ${needUse ? 'border-red-300' : 'border-gray-300'}`}
        >
          <option value="">용도 선택 *</option>
          {FACILITY_USES.map((u) => (
            <option key={u} value={u}>{u}</option>
          ))}
        </select>
        <input
          type="number"
          value={site.site_area_override}
          onChange={(e) => onUpdate({ site_area_override: e.target.value })}
          placeholder="대지면적 ㎡"
          className="text-xs border border-gray-300 rounded px-2 py-1"
        />
      </div>
      {/* 공모에서 채운 목표치 (참고 표시) */}
      {(site.target_far_pct || site.target_floor_area_sqm) && (
        <div className="text-[10px] text-gray-400 mt-1.5">
          공모 목표: 연면적 {fmt(site.target_floor_area_sqm)}㎡ · 용적률 {fmt(site.target_far_pct, 1)}% · 건폐율 {fmt(site.target_building_coverage_pct, 1)}%
        </div>
      )}
    </div>
  )
}

// ── 비교 매트릭스 ──────────────────────────────────────────────────────
function CompareMatrix({ results }) {
  const ok = results.filter((r) => r.ok).map((r) => r.result)
  const failed = results.filter((r) => !r.ok)

  // 행별 최적값
  const bestByRow = {}
  ROWS.forEach((r) => {
    if (r.text) return
    const vals = ok.map((res) => r.get(res)).filter((v) => v != null)
    if (vals.length) bestByRow[r.key] = r.higherBetter ? Math.max(...vals) : Math.min(...vals)
  })

  return (
    <section>
      <h3 className="text-sm font-semibold text-gray-800 mb-3">비교 결과</h3>
      {ok.length === 0 ? (
        <div className="text-xs text-gray-500">성공한 부지가 없습니다.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr>
                <th className="text-left font-medium text-gray-500 px-2 py-1.5 border-b border-gray-200">항목</th>
                {ok.map((res, i) => (
                  <th key={i} className="px-2 py-1.5 border-b border-gray-200 text-center min-w-[96px] font-semibold text-gray-700">
                    {res.site_label || res.address}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ROWS.map((r) => (
                <tr key={r.key}>
                  <td className="px-2 py-1.5 text-gray-600 border-b border-gray-100">{r.label}</td>
                  {ok.map((res, i) => {
                    const val = r.get(res)
                    if (r.text) {
                      return (
                        <td key={i} className="px-2 py-1.5 text-center border-b border-gray-100 text-gray-700">
                          {val}
                        </td>
                      )
                    }
                    const isBest = val != null && val === bestByRow[r.key] && ok.length > 1
                    return (
                      <td
                        key={i}
                        className="px-2 py-1.5 text-center border-b border-gray-100"
                        style={isBest ? { color: 'var(--color-success)', fontWeight: 700 } : {}}
                      >
                        {fmt(val, r.d)}{val != null ? r.unit : ''}
                      </td>
                    )
                  })}
                </tr>
              ))}
              {/* 종합 판단 */}
              <tr>
                <td className="px-2 py-1.5 text-gray-600 border-b border-gray-100">종합 판단</td>
                {ok.map((res, i) => {
                  const v = res.overall_recommendation?.verdict
                  return (
                    <td key={i} className="px-2 py-1.5 text-center border-b border-gray-100 font-semibold" style={{ color: VERDICT_COLOR[v] || 'inherit' }}>
                      {v || '—'}
                    </td>
                  )
                })}
              </tr>
              {/* 심의 필수 */}
              <tr>
                <td className="px-2 py-1.5 text-gray-600 border-b border-gray-100">심의 필수</td>
                {ok.map((res, i) => (
                  <td key={i} className="px-2 py-1.5 text-center border-b border-gray-100 text-gray-700">
                    {res.review_burden?.count_required != null ? `${res.review_burden.count_required}건` : '—'}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
          <p className="text-[10px] text-gray-400 mt-2">
            초록색 = 항목별 가장 유리한 값 (용적률·건폐율·연면적은 클수록, 주차는 적을수록).
          </p>
        </div>
      )}

      {failed.length > 0 && (
        <div className="mt-3 text-[11px] text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
          실패한 부지 {failed.length}개:
          <ul className="mt-1 space-y-0.5">
            {failed.map((f, i) => (
              <li key={i}>· {f.site_label}: {f.error}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

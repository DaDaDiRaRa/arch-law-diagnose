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
import BriefList from './BriefList'
import { BUILDING_USES as FACILITY_USES } from '../../constants/buildingUses'

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
  '참여 권장': 'var(--ok)',
  '협상 필요': 'var(--warn-deep)',
  '패스 권장': 'var(--error)',
  '정보 부족': 'var(--faint)',
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
          <h3 className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>
            비교할 부지 ({multiSites.length})
          </h3>
          <div className="flex gap-2">
            {multiSites.length > 0 && (
              <button
                onClick={clearMultiSites}
                className="text-[11px]"
                style={{ color: 'var(--faint)' }}
              >
                전체 삭제
              </button>
            )}
            <button
              onClick={() => addMultiSite()}
              className="text-[11px] font-medium px-2.5 py-1 border"
              style={{
                borderColor: 'var(--hairline)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--body)',
              }}
            >
              + 부지 추가
            </button>
          </div>
        </div>

        {multiSites.length === 0 ? (
          <div
            className="text-[11px] border px-4 py-3"
            style={{
              color: 'var(--mute)',
              background: 'var(--canvas-inset)',
              borderColor: 'var(--hairline)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
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
        <div
          className="text-xs px-3 py-2 rounded"
          style={{
            color: 'var(--error)',
            background: 'var(--canvas-elevated)',
            border: '1px solid var(--hairline)',
            borderLeft: '3px solid var(--error)',
          }}
        >
          {multiError}
        </div>
      )}

      {multiSites.length > 0 && (
        <button
          onClick={runMulti}
          disabled={multiLoading}
          className="w-full py-2.5 text-xs font-semibold text-white disabled:opacity-50"
          style={{
            backgroundColor: 'var(--brand)',
            borderRadius: 'var(--radius-sm)',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          {multiLoading ? '비교 계산 중…' : `전체 비교 실행 (${multiSites.length}개 부지)`}
        </button>
      )}

      {multiResults && <CompareMatrix results={multiResults} />}
    </div>
  )
}

// ── 공모지침 일괄 로더 (공용 BriefList 사용 — 카테고리 필터 + 검색) ──────────
function BriefLoader({ onLoad }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

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
    <div
      className="border"
      style={{
        borderColor: 'var(--hairline)',
        borderRadius: 'var(--radius-sm)',
        background: 'var(--canvas-inset)',
      }}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2.5 text-left"
      >
        <span className="text-xs font-semibold" style={{ color: 'var(--body)' }}>
          공모지침에서 부지 불러오기
          <span className="text-[10px] font-normal ml-2" style={{ color: 'var(--faint)' }}>
            다부지 공모를 한 번에 비교
          </span>
        </span>
        <span className="text-xs" style={{ color: 'var(--faint)' }}>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 pt-3" style={{ borderTop: '1px solid var(--hairline)' }}>
          {error && (
            <div
              className="text-[11px] px-2 py-1.5 rounded mb-2"
              style={{
                color: 'var(--error)',
                background: 'var(--canvas-elevated)',
                borderLeft: '3px solid var(--error)',
                border: '1px solid var(--hairline)',
              }}
            >
              {error}
            </div>
          )}
          <BriefList onPick={pick} picking={loading} />
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
    <div
      className="border p-3"
      style={{
        borderColor: 'var(--hairline)',
        borderRadius: 'var(--radius-sm)',
        background: 'var(--canvas-elevated)',
      }}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] w-5" style={{ color: 'var(--faint)' }}>{index + 1}</span>
        <input
          value={site.site_label}
          onChange={(e) => onUpdate({ site_label: e.target.value })}
          className="flex-1 text-xs font-semibold border rounded px-2 py-1"
          style={{ borderColor: 'var(--hairline)' }}
          placeholder="부지 이름"
        />
        <button
          onClick={onRemove}
          className="px-1"
          style={{ color: 'var(--mute)' }}
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
            className="w-full text-xs border rounded px-2 py-1"
            style={{ borderColor: needAddr ? 'var(--error)' : 'var(--hairline)' }}
          />
        </div>
        <select
          value={site.facility_use}
          onChange={(e) => onUpdate({ facility_use: e.target.value })}
          className="text-xs border rounded px-2 py-1"
          style={{ borderColor: needUse ? 'var(--error)' : 'var(--hairline)' }}
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
          className="text-xs border rounded px-2 py-1"
          style={{ borderColor: 'var(--hairline)' }}
        />
      </div>
      {/* 공모에서 채운 목표치 (참고 표시) */}
      {(site.target_far_pct || site.target_floor_area_sqm) && (
        <div className="text-[10px] mt-1.5" style={{ color: 'var(--faint)' }}>
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
      <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--ink)' }}>비교 결과</h3>
      {ok.length === 0 ? (
        <div className="text-xs" style={{ color: 'var(--mute)' }}>성공한 부지가 없습니다.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr>
                <th
                  className="text-left font-medium px-2 py-1.5"
                  style={{ color: 'var(--mute)', borderBottom: '1px solid var(--hairline)' }}
                >
                  항목
                </th>
                {ok.map((res, i) => (
                  <th
                    key={i}
                    className="px-2 py-1.5 text-center min-w-[96px] font-semibold"
                    style={{ color: 'var(--body)', borderBottom: '1px solid var(--hairline)' }}
                  >
                    {res.site_label || res.address}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ROWS.map((r) => (
                <tr key={r.key}>
                  <td
                    className="px-2 py-1.5"
                    style={{ color: 'var(--body)', borderBottom: '1px solid var(--hairline-soft)' }}
                  >
                    {r.label}
                  </td>
                  {ok.map((res, i) => {
                    const val = r.get(res)
                    if (r.text) {
                      return (
                        <td
                          key={i}
                          className="px-2 py-1.5 text-center"
                          style={{ color: 'var(--body)', borderBottom: '1px solid var(--hairline-soft)' }}
                        >
                          {val}
                        </td>
                      )
                    }
                    const isBest = val != null && val === bestByRow[r.key] && ok.length > 1
                    return (
                      <td
                        key={i}
                        className="px-2 py-1.5 text-center"
                        style={
                          isBest
                            ? { color: 'var(--ok)', fontWeight: 700, borderBottom: '1px solid var(--hairline-soft)' }
                            : { borderBottom: '1px solid var(--hairline-soft)' }
                        }
                      >
                        {fmt(val, r.d)}{val != null ? r.unit : ''}
                      </td>
                    )
                  })}
                </tr>
              ))}
              {/* 종합 판단 */}
              <tr>
                <td
                  className="px-2 py-1.5"
                  style={{ color: 'var(--body)', borderBottom: '1px solid var(--hairline-soft)' }}
                >
                  종합 판단
                </td>
                {ok.map((res, i) => {
                  const v = res.overall_recommendation?.verdict
                  return (
                    <td
                      key={i}
                      className="px-2 py-1.5 text-center font-semibold"
                      style={{
                        color: VERDICT_COLOR[v] || 'inherit',
                        borderBottom: '1px solid var(--hairline-soft)',
                      }}
                    >
                      {v || '—'}
                    </td>
                  )
                })}
              </tr>
              {/* 심의 필수 */}
              <tr>
                <td
                  className="px-2 py-1.5"
                  style={{ color: 'var(--body)', borderBottom: '1px solid var(--hairline-soft)' }}
                >
                  심의 필수
                </td>
                {ok.map((res, i) => (
                  <td
                    key={i}
                    className="px-2 py-1.5 text-center"
                    style={{ color: 'var(--body)', borderBottom: '1px solid var(--hairline-soft)' }}
                  >
                    {res.review_burden?.count_required != null ? `${res.review_burden.count_required}건` : '—'}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
          <p className="text-[10px] mt-2" style={{ color: 'var(--faint)' }}>
            초록색 = 항목별 가장 유리한 값 (용적률·건폐율·연면적은 클수록, 주차는 적을수록).
          </p>
        </div>
      )}

      {failed.length > 0 && (
        <div
          className="mt-3 text-[11px] rounded px-3 py-2"
          style={{
            color: 'var(--error)',
            background: 'var(--canvas-elevated)',
            border: '1px solid var(--hairline)',
            borderLeft: '3px solid var(--error)',
          }}
        >
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

import { useFeasibilityStore } from '../../stores/feasibilityStore'
import AddressSearch from '../AddressSearch'
import BriefImportPanel from './BriefImportPanel'

const FACILITY_USES = [
  '제1종근린생활시설', '제2종근린생활시설', '근린생활시설',
  '공동주택', '단독주택',
  '업무시설', '공공업무시설',
  '판매시설',
  '숙박시설', '의료시설', '교육연구시설',
  '문화및집회시설', '종교시설', '운동시설',
  '노유자시설',
  '위락시설', '공장', '창고시설', '기타',
]

const APPLICANT_TYPES = ['개인', '민간법인', '공공기관']

const ZONE_USES = [
  '',
  '제1종전용주거지역', '제2종전용주거지역',
  '제1종일반주거지역', '제2종일반주거지역', '제3종일반주거지역',
  '준주거지역',
  '중심상업지역', '일반상업지역', '근린상업지역', '유통상업지역',
  '전용공업지역', '일반공업지역', '준공업지역',
  '보전녹지지역', '생산녹지지역', '자연녹지지역',
]

export default function FeasibilityInputForm() {
  const {
    formData, setFormData, setSelectedAddress, autoLandInfo, autoLandLoading,
    runFeasibility, loading, error,
  } = useFeasibilityStore()

  const handleChange = (e) => {
    setFormData({ [e.target.name]: e.target.value })
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    runFeasibility()
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* 0. 공모지침 불러오기 */}
      <BriefImportPanel />

      {/* 1. 대지 정보 */}
      <section>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--ink)' }}>
          <span style={{ color: 'var(--info)' }}>①</span> 대지 정보
        </h3>

        <div className="space-y-3">
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--body)' }}>주소 *</label>
            <AddressSearch onSelect={setSelectedAddress} />
            {formData.address && (
              <div className="mt-1 text-xs" style={{ color: 'var(--mute)' }}>{formData.address}</div>
            )}
          </div>

          {autoLandLoading && (
            <div
              className="text-xs px-3 py-2"
              style={{
                color: 'var(--info)',
                background: 'var(--canvas-elevated)',
                borderLeft: '3px solid var(--info)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--hairline)',
              }}
            >
              토지 정보 자동 조회 중...
            </div>
          )}

          {autoLandInfo && !autoLandLoading && (
            <div
              className="text-xs border px-3 py-2 space-y-0.5"
              style={{
                background: 'var(--canvas-inset)',
                borderColor: 'var(--hairline)',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <div className="font-medium" style={{ color: 'var(--body)' }}>자동 조회 결과 (VWorld)</div>
              <div style={{ color: 'var(--body)' }}>
                · 용도지역: {autoLandInfo.zone_use || '미확인'}
              </div>
              {autoLandInfo.zone_district && (
                <div style={{ color: 'var(--body)' }}>· 지역지구: {autoLandInfo.zone_district}</div>
              )}
              {autoLandInfo.parcel_area && (
                <div style={{ color: 'var(--body)' }}>
                  · 대지면적: {Number(autoLandInfo.parcel_area).toLocaleString()}㎡
                </div>
              )}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--body)' }}>
                용도지역 (수동 입력)
              </label>
              <select
                name="zone_use_override"
                value={formData.zone_use_override}
                onChange={handleChange}
                className="w-full text-xs border rounded px-2 py-1.5"
                style={{ borderColor: 'var(--hairline)' }}
              >
                {ZONE_USES.map((z) => (
                  <option key={z} value={z}>{z || '— 자동 조회값 사용 —'}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--body)' }}>
                대지면적 (자동 조회 실패 시)
              </label>
              <input
                type="number"
                step="0.01"
                name="site_area_override"
                value={formData.site_area_override}
                onChange={handleChange}
                placeholder="㎡"
                className="w-full text-xs border rounded px-2 py-1.5"
                style={{ borderColor: 'var(--hairline)' }}
              />
            </div>
          </div>
        </div>
      </section>

      {/* 2. 시설 유형 */}
      <section className="pt-5" style={{ borderTop: '1px solid var(--hairline)' }}>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--ink)' }}>
          <span style={{ color: 'var(--info)' }}>②</span> 시설 유형
        </h3>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--body)' }}>시설 용도 *</label>
            <select
              name="facility_use"
              value={formData.facility_use}
              onChange={handleChange}
              required
              className="w-full text-xs border rounded px-2 py-1.5"
              style={{ borderColor: 'var(--hairline)' }}
            >
              <option value="">— 선택 —</option>
              {FACILITY_USES.map((u) => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs mb-1" style={{ color: 'var(--body)' }}>신청 주체</label>
            <select
              name="applicant_type"
              value={formData.applicant_type}
              onChange={handleChange}
              className="w-full text-xs border rounded px-2 py-1.5"
              style={{ borderColor: 'var(--hairline)' }}
            >
              {APPLICANT_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div className="col-span-2">
            <label className="block text-xs mb-1" style={{ color: 'var(--body)' }}>세부 용도 (선택, 자유 입력)</label>
            <input
              type="text"
              name="building_use_detail"
              value={formData.building_use_detail}
              onChange={handleChange}
              placeholder="예: 공공업무시설(구청, 어린이집)"
              className="w-full text-xs border rounded px-2 py-1.5"
              style={{ borderColor: 'var(--hairline)' }}
            />
          </div>
        </div>
      </section>

      {/* 3. 공모 요구치 */}
      <section className="pt-5" style={{ borderTop: '1px solid var(--hairline)' }}>
        <h3 className="text-sm font-semibold mb-1 flex items-center gap-2" style={{ color: 'var(--ink)' }}>
          <span style={{ color: 'var(--info)' }}>③</span> 공모 요구치
        </h3>
        <p className="text-xs mb-3" style={{ color: 'var(--mute)' }}>
          공모지침서에 명시된 값을 입력하세요. 모두 선택 — 비워둔 항목은 갭 분석에서 제외됩니다.
        </p>

        <div className="grid grid-cols-2 gap-3">
          <NumInput name="target_floor_area_sqm" label="목표 연면적" unit="㎡" value={formData.target_floor_area_sqm} onChange={handleChange} />
          <NumInput name="target_building_coverage_pct" label="목표 건폐율" unit="%" value={formData.target_building_coverage_pct} onChange={handleChange} />
          <NumInput name="target_far_pct" label="목표 용적률" unit="%" value={formData.target_far_pct} onChange={handleChange} />
          <NumInput name="target_max_height_m" label="목표 최고높이" unit="m" value={formData.target_max_height_m} onChange={handleChange} />
          <NumInput name="target_floors_above" label="목표 지상 층수" unit="층" value={formData.target_floors_above} onChange={handleChange} step="1" />
          <NumInput name="target_parking_count" label="목표 주차대수" unit="대" value={formData.target_parking_count} onChange={handleChange} step="1" />
          <NumInput name="target_open_space_sqm" label="공개공지 요구" unit="㎡" value={formData.target_open_space_sqm} onChange={handleChange} />
          {formData.facility_use === '공동주택' && (
            <>
              <NumInput name="target_units" label="목표 세대수" unit="세대" value={formData.target_units} onChange={handleChange} step="1" />
              <NumInput name="unit_exclusive_area" label="평균 전용면적" unit="㎡" value={formData.unit_exclusive_area} onChange={handleChange} />
            </>
          )}
        </div>
      </section>

      {/* Submit */}
      {error && (
        <div
          className="text-xs px-3 py-2 rounded"
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

      <div className="pt-4 flex justify-end gap-2" style={{ borderTop: '1px solid var(--hairline)' }}>
        <button
          type="submit"
          disabled={loading || !formData.address || !formData.facility_use}
          className="px-4 py-2 text-xs font-semibold text-white rounded disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ backgroundColor: 'var(--brand)', boxShadow: 'var(--shadow-sm)' }}
        >
          {loading ? '검토 중...' : '사업성 검토 실행'}
        </button>
      </div>
    </form>
  )
}

function NumInput({ name, label, unit, value, onChange, step = '0.01' }) {
  return (
    <div>
      <label className="block text-xs mb-1" style={{ color: 'var(--body)' }}>
        {label} <span style={{ color: 'var(--faint)' }}>({unit})</span>
      </label>
      <input
        type="number"
        step={step}
        name={name}
        value={value}
        onChange={onChange}
        placeholder={unit}
        className="w-full text-xs border rounded px-2 py-1.5"
        style={{ borderColor: 'var(--hairline)' }}
      />
    </div>
  )
}

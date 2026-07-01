import { useState } from 'react'
import { useDiagnoseStore } from '../../stores/diagnoseStore'
import { api } from '../../utils/api'
import AddressSearch from '../AddressSearch'
import BriefUploader from '../BriefUploader'

const BUILDING_USES = [
  '제1종근린생활시설', '제2종근린생활시설', '근린생활시설',
  '공동주택', '단독주택',
  '업무시설', '공공업무시설',
  '판매시설',
  '숙박시설', '의료시설', '교육연구시설',
  '문화및집회시설', '종교시설', '운동시설',
  '노유자시설',
  '위락시설', '공장', '창고시설', '기타',
]

const ZONE_USES = [
  '',
  '제1종전용주거지역', '제2종전용주거지역',
  '제1종일반주거지역', '제2종일반주거지역', '제3종일반주거지역',
  '준주거지역',
  '중심상업지역', '일반상업지역', '근린상업지역', '유통상업지역',
  '전용공업지역', '일반공업지역', '준공업지역',
  '보전녹지지역', '생산녹지지역', '자연녹지지역',
]

export default function InputForm({ isDrawer = false }) {
  const {
    formData, setFormData, setSelectedAddress, setResult, setLoading, setError, loading,
    additionalParcels, addParcel, removeParcel, updateParcel, setParcelAddress,
    autoLandInfo, autoLandLoading,
  } = useDiagnoseStore()

  const [briefConditions, setBriefConditions] = useState(null)

  const isMulti = additionalParcels.length > 0

  const handleAddressSelect = (addr) => {
    setSelectedAddress(addr)
  }

  const handleChange = (e) => {
    setFormData({ [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!formData.address) return

    if (isMulti) {
      const allOk = additionalParcels.every(
        (p) => p.address && parseFloat(p.site_area) > 0,
      )
      if (!allOk) {
        setError('추가 필지의 주소와 면적을 모두 입력해주세요.')
        return
      }
    }

    setLoading(true)

    const isApartment = formData.building_use === '공동주택'

    if (isMulti) {
      const parcels = [
        {
          address: formData.address,
          pnu: formData.pnu || undefined,
          site_area: parseFloat(formData.site_area),
          ...(formData.zone_use_override ? { zone_use_override: formData.zone_use_override } : {}),
        },
        ...additionalParcels.map((p) => ({
          address: p.address,
          pnu: p.pnu || undefined,
          site_area: parseFloat(p.site_area),
          ...(p.zone_use_override ? { zone_use_override: p.zone_use_override } : {}),
        })),
      ]

      const payload = {
        parcels,
        building_use: formData.building_use,
        building_area: parseFloat(formData.building_area),
        floor_area_above: parseFloat(formData.floor_area_above),
        ...(formData.floor_area_below ? { floor_area_below: parseFloat(formData.floor_area_below) } : {}),
        ...(formData.floor_area_parking_above ? { floor_area_parking_above: parseFloat(formData.floor_area_parking_above) } : {}),
        ...(formData.floor_area_refuge ? { floor_area_refuge: parseFloat(formData.floor_area_refuge) } : {}),
        ...(formData.floor_area_attic_refuge ? { floor_area_attic_refuge: parseFloat(formData.floor_area_attic_refuge) } : {}),
        ...(formData.building_use_detail ? { building_use_detail: formData.building_use_detail } : {}),
        ...(formData.zone_district ? { zone_district: formData.zone_district } : {}),
        ...(formData.provided_parking_spaces ? { provided_parking_spaces: parseInt(formData.provided_parking_spaces, 10) } : {}),
        ...(formData.unit_exclusive_area ? { unit_exclusive_area: parseFloat(formData.unit_exclusive_area) } : {}),
        ...(formData.parking_capacity ? { parking_capacity: parseInt(formData.parking_capacity, 10) } : {}),
        ...(formData.public_open_space_area ? { public_open_space_area: parseFloat(formData.public_open_space_area) } : {}),
        ...(formData.green_grade        ? { green_grade: formData.green_grade } : {}),
        ...(formData.zero_energy_grade  ? { zero_energy_grade: formData.zero_energy_grade } : {}),
        ...(formData.pilot_project      ? { pilot_project: true } : {}),
        ...(formData.smart_grade        ? { smart_grade: formData.smart_grade } : {}),
        ...(formData.long_life_grade    ? { long_life_grade: formData.long_life_grade } : {}),
        ...(formData.building_agreement ? { building_agreement: true } : {}),
        ...(formData.agreement_landscape_road_facing ? { agreement_landscape_road_facing: true } : {}),
        ...(formData.rema_zone ? { rema_zone: true } : {}),
        ...(formData.easy_remodel ? { easy_remodel: true } : {}),
        ...(formData.public_rental ? { public_rental: true } : {}),
        ...(formData.far_limit_manual_override ? { far_limit_manual_override: parseFloat(formData.far_limit_manual_override) } : {}),
        ...(formData.relief_reason_manual ? { relief_reason_manual: formData.relief_reason_manual } : {}),
        ...(formData.urban_facility_exclude_area ? { urban_facility_exclude_area: parseFloat(formData.urban_facility_exclude_area) } : {}),
        ...(formData.north_setback_m ? { north_setback_m: parseFloat(formData.north_setback_m) } : {}),
        ...(formData.adjacent_zone_north ? { adjacent_zone_north: formData.adjacent_zone_north } : {}),
        ...(formData.road_20m_adjacent ? { road_20m_adjacent: formData.road_20m_adjacent === 'yes' } : {}),
        ...(formData.street_block_max_height_m ? { street_block_max_height_m: parseFloat(formData.street_block_max_height_m) } : {}),
        floors_above: parseInt(formData.floors_above, 10),
        floors_below: parseInt(formData.floors_below || '0', 10),
        height: parseFloat(formData.height),
        ...(formData.road_width ? { road_width: parseFloat(formData.road_width) } : {}),
        ...(formData.landscape_area ? { landscape_area: parseFloat(formData.landscape_area) } : {}),
        ...(formData.rooftop_landscape_area ? { rooftop_landscape_area: parseFloat(formData.rooftop_landscape_area) } : {}),
        ...(isApartment && formData.units ? { units: parseInt(formData.units, 10) } : {}),
        applicant_type: formData.applicant_type || '개인',
        ...(briefConditions ? { brief_conditions: briefConditions } : {}),
      }

      const hasInvalid =
        Object.values(payload).some((v) => typeof v === 'number' && isNaN(v)) ||
        parcels.some((p) => isNaN(p.site_area))
      if (hasInvalid) {
        setError('숫자 입력값을 확인해주세요.')
        return
      }

      try {
        const result = await api.diagnoseMulti(payload)
        setResult(result)
      } catch (err) {
        if (err.detail && typeof err.detail === 'object' && err.detail.error === 'ZONE_LOOKUP_FAILED') {
          const failed = err.detail.failed_addresses?.join('\n  · ') || ''
          setError(`${err.detail.message}\n  · ${failed}`)
        } else {
          setError(err.message)
        }
      }
      return
    }

    const payload = {
      address: formData.address,
      pnu: formData.pnu || undefined,
      building_use: formData.building_use,
      ...(formData.building_use_detail ? { building_use_detail: formData.building_use_detail } : {}),
      ...(formData.zone_district ? { zone_district: formData.zone_district } : {}),
      ...(formData.zone_use_override ? { zone_use_override: formData.zone_use_override } : {}),
      site_area: parseFloat(formData.site_area),
      building_area: parseFloat(formData.building_area),
      floor_area_above: parseFloat(formData.floor_area_above),
      ...(formData.floor_area_below ? { floor_area_below: parseFloat(formData.floor_area_below) } : {}),
      ...(formData.floor_area_parking_above ? { floor_area_parking_above: parseFloat(formData.floor_area_parking_above) } : {}),
      ...(formData.floor_area_refuge ? { floor_area_refuge: parseFloat(formData.floor_area_refuge) } : {}),
      ...(formData.floor_area_attic_refuge ? { floor_area_attic_refuge: parseFloat(formData.floor_area_attic_refuge) } : {}),
      floors_above: parseInt(formData.floors_above, 10),
      floors_below: parseInt(formData.floors_below || '0', 10),
      height: parseFloat(formData.height),
      ...(formData.road_width ? { road_width: parseFloat(formData.road_width) } : {}),
      ...(formData.landscape_area ? { landscape_area: parseFloat(formData.landscape_area) } : {}),
      ...(formData.rooftop_landscape_area ? { rooftop_landscape_area: parseFloat(formData.rooftop_landscape_area) } : {}),
      ...(isApartment && formData.units ? { units: parseInt(formData.units, 10) } : {}),
      ...(formData.provided_parking_spaces ? { provided_parking_spaces: parseInt(formData.provided_parking_spaces, 10) } : {}),
      ...(formData.unit_exclusive_area ? { unit_exclusive_area: parseFloat(formData.unit_exclusive_area) } : {}),
      ...(formData.parking_capacity ? { parking_capacity: parseInt(formData.parking_capacity, 10) } : {}),
      ...(formData.public_open_space_area ? { public_open_space_area: parseFloat(formData.public_open_space_area) } : {}),
      ...(formData.green_grade        ? { green_grade: formData.green_grade } : {}),
      ...(formData.zero_energy_grade  ? { zero_energy_grade: formData.zero_energy_grade } : {}),
      ...(formData.pilot_project      ? { pilot_project: true } : {}),
      ...(formData.smart_grade        ? { smart_grade: formData.smart_grade } : {}),
      ...(formData.long_life_grade    ? { long_life_grade: formData.long_life_grade } : {}),
      ...(formData.building_agreement ? { building_agreement: true } : {}),
      ...(formData.agreement_landscape_road_facing ? { agreement_landscape_road_facing: true } : {}),
      ...(formData.rema_zone ? { rema_zone: true } : {}),
      ...(formData.easy_remodel ? { easy_remodel: true } : {}),
      ...(formData.public_rental ? { public_rental: true } : {}),
      ...(formData.far_limit_manual_override ? { far_limit_manual_override: parseFloat(formData.far_limit_manual_override) } : {}),
      ...(formData.relief_reason_manual ? { relief_reason_manual: formData.relief_reason_manual } : {}),
      ...(formData.urban_facility_exclude_area ? { urban_facility_exclude_area: parseFloat(formData.urban_facility_exclude_area) } : {}),
      ...(formData.north_setback_m ? { north_setback_m: parseFloat(formData.north_setback_m) } : {}),
      ...(formData.adjacent_zone_north ? { adjacent_zone_north: formData.adjacent_zone_north } : {}),
      ...(formData.road_20m_adjacent ? { road_20m_adjacent: formData.road_20m_adjacent === 'yes' } : {}),
      ...(formData.street_block_max_height_m ? { street_block_max_height_m: parseFloat(formData.street_block_max_height_m) } : {}),
      ...(formData.decision_notice_confirmed ? { decision_notice_confirmed: true } : {}),
      ...(formData.decision_notice_confirmed && formData.decision_far_limit ? { decision_far_limit: parseFloat(formData.decision_far_limit) } : {}),
      ...(formData.decision_notice_confirmed && formData.decision_cov_limit ? { decision_cov_limit: parseFloat(formData.decision_cov_limit) } : {}),
      ...(formData.decision_notice_confirmed && formData.decision_height_limit ? { decision_height_limit: parseFloat(formData.decision_height_limit) } : {}),
      applicant_type: formData.applicant_type || '개인',
      ...(briefConditions ? { brief_conditions: briefConditions } : {}),
    }

    const hasInvalid = Object.values(payload).some((v) => typeof v === 'number' && isNaN(v))
    if (hasInvalid) {
      setError('숫자 입력값을 확인해주세요.')
      return
    }

    try {
      const result = await api.diagnose(payload)
      setResult(result)
    } catch (err) {
      setError(err.message)
    }
  }

  const isApartment = formData.building_use === '공동주택'
  const totalSiteArea =
    (parseFloat(formData.site_area) || 0) +
    additionalParcels.reduce((s, p) => s + (parseFloat(p.site_area) || 0), 0)

  /* 와이드 모드: 1단·2단·3단 좌우 3열 / 드로어: 위아래 */
  const outerCls = isDrawer
    ? 'space-y-4'
    : 'grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_minmax(0,1fr)] gap-5 items-start'

  return (
    <form onSubmit={handleSubmit} className="space-y-3">

      <div className={outerCls}>

        {/* ══ 1단: 기본 정보 (좌열) ══ */}
        <div className="space-y-3">
          <SectionLabel>기본 정보</SectionLabel>

          {/* 대지주소 */}
          <div>
            <label className="block text-sm font-medium mb-1" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>
              {isMulti ? '1번 필지 주소' : '대지 주소'} <span style={{color:'var(--error)'}}>*</span>
            </label>
            <AddressSearch onSelect={handleAddressSelect} />
            {formData.address && (
              <p className="mt-1 text-xs font-medium" style={{color:'var(--link)'}}>{formData.address}</p>
            )}
            {formData.pnu && (
              <p className="mt-0.5 text-xs" style={{color:'var(--faint)',fontFamily:'var(--font-mono)'}}>PNU: {formData.pnu}</p>
            )}
            <AutoLandInfoBanner loading={autoLandLoading} info={autoLandInfo} />
          </div>

          {/* 추가 필지 */}
          {additionalParcels.map((p, idx) => (
            <div key={idx} className="p-3 space-y-2" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--info)',backgroundColor:'var(--canvas)'}}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>{idx + 2}번 필지 <span style={{color:'var(--error)'}}>*</span></span>
                <button type="button" onClick={() => removeParcel(idx)} className="text-xs hover:underline" style={{color:'var(--error)'}}>제거</button>
              </div>
              <AddressSearch onSelect={(addr) => setParcelAddress(idx, addr)} />
              {p.address && <p className="text-xs font-medium" style={{color:'var(--link)'}}>{p.address}</p>}
              {p.pnu && <p className="text-xs" style={{color:'var(--faint)',fontFamily:'var(--font-mono)'}}>PNU: {p.pnu}</p>}
              <div className="grid grid-cols-2 gap-2">
                <Field label={`${idx + 2}번 필지 면적 (㎡)`} required>
                  <input type="number" value={p.site_area} onChange={(e) => updateParcel(idx, { site_area: e.target.value })} min="1" step="0.01" className={inputCls} placeholder="300" required />
                </Field>
                <Field label="용도지역 (선택)">
                  <select value={p.zone_use_override || ''} onChange={(e) => updateParcel(idx, { zone_use_override: e.target.value })} className={inputCls}>
                    <option value="">자동 (VWorld 조회)</option>
                    {ZONE_USES.filter(Boolean).map((z) => <option key={z} value={z}>{z}</option>)}
                  </select>
                </Field>
              </div>
            </div>
          ))}

          <div className="flex items-center justify-between">
            <button type="button" onClick={addParcel} disabled={!formData.address} className="text-sm font-medium disabled:opacity-30" style={{color:'var(--link)',fontFamily:'var(--font-sans)'}}>
              + 필지 추가 {isMulti && `(${additionalParcels.length + 1}개 합산)`}
            </button>
            {isMulti && totalSiteArea > 0 && (
              <span className="text-xs" style={{color:'var(--body)'}}>합산: <span className="font-semibold" style={{color:'var(--ink)'}}>{totalSiteArea.toLocaleString()}㎡</span></span>
            )}
          </div>
          {isMulti && (
            <p className="text-xs p-2" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--info)',backgroundColor:'var(--canvas-elevated)',color:'var(--body)'}}>
              <b style={{color:'var(--ink)'}}>합필</b> — 국토계획법 §84 자동 처리
            </p>
          )}

          {/* 건축물 주 용도 */}
          <Field label="건축물 주 용도" required>
            <select name="building_use" value={formData.building_use} onChange={handleChange} className={inputCls} required>
              <option value="">선택</option>
              {BUILDING_USES.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </Field>

          {/* 세부/복합용도 */}
          <Field label="세부/복합 용도" hint="예: 구청,어린이집">
            <input type="text" name="building_use_detail" value={formData.building_use_detail} onChange={handleChange} className={inputCls} placeholder="검토서에 그대로 표시" />
          </Field>

          {/* 신청주체 */}
          <Field label="신청 주체" hint="공공기관 시 의무인증 자동판정">
            <select name="applicant_type" value={formData.applicant_type || '개인'} onChange={handleChange} className={inputCls}>
              <option value="개인">개인</option>
              <option value="민간법인">민간법인</option>
              <option value="공공기관">공공기관</option>
            </select>
          </Field>

          {/* 용도지역 */}
          <Field
            label={isMulti ? '1번 필지 용도지역' : '용도지역'}
            hint={autoLandInfo?.zone_use && formData.zone_use_override === autoLandInfo.zone_use ? '🔄 자동조회됨' : '주소 선택 시 자동조회'}
          >
            <select name="zone_use_override" value={formData.zone_use_override || ''} onChange={handleChange} className={inputCls}>
              <option value="">미지정 (진단 시 재조회)</option>
              {ZONE_USES.filter(Boolean).map((z) => <option key={z} value={z}>{z}</option>)}
            </select>
          </Field>

          {/* 지역지구 */}
          <Field
            label="지역지구"
            hint={autoLandInfo?.zone_district && formData.zone_district === autoLandInfo.zone_district ? '🔄 자동조회됨' : '주소 선택 시 자동조회'}
          >
            <input type="text" name="zone_district" value={formData.zone_district} onChange={handleChange} className={inputCls} placeholder={autoLandLoading ? '조회 중...' : autoLandInfo?.zone_district || '지구단위계획구역 등'} />
          </Field>
        </div>

        {/* ══ 2단: 수치 입력 (중열) ══ */}
        <div className="space-y-3">
          <SectionLabel>규모·면적</SectionLabel>
          <div className="grid grid-cols-2 gap-3">

            {/* 대지면적 */}
            <Field label={isMulti ? '1번 필지 면적 (㎡)' : '대지면적 (㎡)'} required>
              <input type="number" name="site_area" value={formData.site_area} onChange={handleChange} min="1" step="0.01" className={inputCls} placeholder="500" required />
            </Field>

            {/* 건축면적 */}
            <Field label="건축면적 (㎡)" required>
              <input type="number" name="building_area" value={formData.building_area} onChange={handleChange} min="1" step="0.01" className={inputCls} placeholder="250" required />
            </Field>

            {/* 건폐율/용적률 자동계산 */}
            <RatioCell formData={formData} />

            {/* 지상연면적 */}
            <Field label="지상 연면적 (㎡)" required hint="주차장 포함">
              <input type="number" name="floor_area_above" value={formData.floor_area_above} onChange={handleChange} min="1" step="0.01" className={inputCls} placeholder="1500" required />
            </Field>

            {/* 지하연면적 */}
            <Field label="지하 연면적 (㎡)" hint="용적률 제외">
              <input type="number" name="floor_area_below" value={formData.floor_area_below} onChange={handleChange} min="0" step="0.01" className={inputCls} placeholder="500" />
            </Field>

            {/* 지상주차장 */}
            <Field label="지상 주차장 (㎡)" hint="용적률 제외">
              <input type="number" name="floor_area_parking_above" value={formData.floor_area_parking_above} onChange={handleChange} min="0" step="0.01" className={inputCls} placeholder="300" />
            </Field>

            {/* 지상층수 */}
            <Field label="지상 층수" required>
              <input type="number" name="floors_above" value={formData.floors_above} onChange={handleChange} min="1" className={inputCls} placeholder="6" required />
            </Field>

            {/* 지하층수 */}
            <Field label="지하 층수">
              <input type="number" name="floors_below" value={formData.floors_below} onChange={handleChange} min="0" className={inputCls} placeholder="1" />
            </Field>

            {/* 건물높이 */}
            <Field label="건물 높이 (m)" required>
              <input type="number" name="height" value={formData.height} onChange={handleChange} min="1" step="0.1" className={inputCls} placeholder="24" required />
            </Field>

            {/* 전면도로폭 */}
            <Field label="전면도로 폭 (m)" hint={autoLandInfo?.road_width_auto != null ? `🔄 ${autoLandInfo.road_width_auto}m` : '선택'}>
              <input type="number" name="road_width" value={formData.road_width} onChange={handleChange} min="1" step="0.1" className={inputCls} placeholder={autoLandInfo?.road_width_auto != null ? String(autoLandInfo.road_width_auto) : '12'} />
            </Field>

            {/* 계획주차대수 */}
            <Field label="계획 주차대수" hint="법정 대수 비교">
              <input type="number" name="provided_parking_spaces" value={formData.provided_parking_spaces} onChange={handleChange} min="0" className={inputCls} placeholder="30" />
            </Field>
            {/* 골프장·골프연습장·관람장·옥외수영장 전용 */}
            <Field label="홀/타석/정원 수" hint="골프장·관람장 등">
              <input type="number" name="parking_capacity" value={formData.parking_capacity} onChange={handleChange} min="1" className={inputCls} placeholder="18" />
            </Field>

            {/* 공개공지 */}
            <Field label="공개공지 (㎡)">
              <AreaWithRatio name="public_open_space_area" value={formData.public_open_space_area} onChange={handleChange} siteArea={formData.site_area} placeholder="150" />
            </Field>

            {/* 조경면적 */}
            <Field label="조경면적 (㎡)">
              <AreaWithRatio name="landscape_area" value={formData.landscape_area} onChange={handleChange} siteArea={formData.site_area} placeholder="75" />
            </Field>

            {/* 옥상조경 */}
            <Field label="옥상조경 (㎡)" hint="§27③ 2/3 인정">
              <AreaWithRatio name="rooftop_landscape_area" value={formData.rooftop_landscape_area} onChange={handleChange} siteArea={formData.site_area} placeholder="30" />
            </Field>

          </div>

          <FloorAreaSummary formData={formData} />

          {isApartment && (
            <Field label="세대수" hint="주차 산정용">
              <input type="number" name="units" value={formData.units} onChange={handleChange} min="1" className={inputCls} placeholder="50" />
            </Field>
          )}
          {isApartment && (
            <Field label="세대 평균 전용면적 (㎡)" hint="60㎡ 이하 0.7대 분기">
              <input type="number" name="unit_exclusive_area" value={formData.unit_exclusive_area} onChange={handleChange} min="1" step="0.1" className={inputCls} placeholder="85" />
            </Field>
          )}
        </div>

        {/* ══ 3단: 선택 패널 (우열) ══ */}
        <div className="space-y-2">
          <SectionLabel>선택 옵션</SectionLabel>

          {/* 용적률 추가 제외 */}
          <details className="px-3 py-2" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)'}}>
            <summary className="text-xs cursor-pointer select-none font-medium" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>용적률 추가 제외</summary>
            <div className="space-y-2 mt-2">
              <Field label="피난안전구역 (㎡)" hint="30층↑">
                <input type="number" name="floor_area_refuge" value={formData.floor_area_refuge} onChange={handleChange} min="0" step="0.01" className={inputCls} placeholder="200" />
              </Field>
              <Field label="경사지붕 대피공간 (㎡)" hint="11층↑">
                <input type="number" name="floor_area_attic_refuge" value={formData.floor_area_attic_refuge} onChange={handleChange} min="0" step="0.01" className={inputCls} placeholder="50" />
              </Field>
            </div>
          </details>

          {/* 용적률 완화 */}
          <details className="px-3 py-2" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--ok)',backgroundColor:'var(--canvas)'}}>
            <summary className="text-xs cursor-pointer select-none font-medium" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>용적률 완화</summary>
            <div className="space-y-2 mt-2">
              <Field label="녹색건축 인증">
                <select name="green_grade" value={formData.green_grade} onChange={handleChange} className={inputCls}>
                  <option value="">미인증</option>
                  <option value="최우수">최우수 (+6%)</option>
                  <option value="우수">우수 (+3%)</option>
                </select>
              </Field>
              <Field label="제로에너지건축물(ZEB) 인증">
                <select name="zero_energy_grade" value={formData.zero_energy_grade} onChange={handleChange} className={inputCls}>
                  <option value="">미인증</option>
                  <option value="1등급">1등급 / 플러스(+) (+15%)</option>
                  <option value="2등급">2등급 (+14%)</option>
                  <option value="3등급">3등급 (+13%)</option>
                  <option value="4등급">4등급 (+12%)</option>
                  <option value="5등급">5등급 (+11%)</option>
                </select>
              </Field>
              <Field label="녹색건축물 조성 시범사업" hint="국토부 시범사업 지정 건축물만">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="pilot_project" checked={!!formData.pilot_project} onChange={e => handleChange({ target: { name: 'pilot_project', value: e.target.checked } })} />
                  시범사업 지정 (+10%)
                </label>
              </Field>
              <Field label="지능형건축물 인증" hint="완화율 고시 원문 확인 필요 — 현재 미지원">
                <select name="smart_grade" value={formData.smart_grade} onChange={handleChange} className={inputCls} disabled>
                  <option value="">미인증 (고시 원문 확인 필요)</option>
                </select>
              </Field>
              <Field label="장수명주택 인증" hint="공동주택만 / 완화율 고시 원문 확인 필요">
                <select name="long_life_grade" value={formData.long_life_grade} onChange={handleChange} className={inputCls} disabled>
                  <option value="">미인증 (고시 원문 확인 필요)</option>
                </select>
              </Field>
              <Field label="용적률 한도 직접 지정 (%)">
                <input type="number" name="far_limit_manual_override" value={formData.far_limit_manual_override} onChange={handleChange} min="1" step="0.01" className={inputCls} placeholder="예: 460" />
              </Field>
              <Field label="완화 사유">
                <input type="text" name="relief_reason_manual" value={formData.relief_reason_manual} onChange={handleChange} className={inputCls} placeholder="예: 도시계획심의 결정" />
              </Field>
            </div>
            <p className="mt-2 text-[10px]" style={{color:'var(--mute)'}}>※ 인증 합산 캡 15%, 전체 캡 1.15배 (녹색건축물법 §15)</p>
          </details>

          {/* 도시계획시설 결정고시 */}
          <details className="px-3 py-2" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--info)',backgroundColor:'var(--canvas)'}}>
            <summary className="text-xs cursor-pointer select-none font-medium" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>결정고시</summary>
            <div className="space-y-2 mt-2">
              <label className="flex items-center gap-2 text-xs cursor-pointer">
                <input type="checkbox" name="decision_notice_confirmed" checked={!!formData.decision_notice_confirmed} onChange={(e) => setFormData({ decision_notice_confirmed: e.target.checked })} className="w-4 h-4 accent-blue-600" />
                <span>결정고시 확인됨</span>
              </label>
              {formData.decision_notice_confirmed && (
                <div className="space-y-2">
                  <Field label="결정고시 용적률 (%)">
                    <input type="number" name="decision_far_limit" value={formData.decision_far_limit ?? ''} onChange={handleChange} className={inputCls} placeholder="예: 600" min={0} step={10} />
                  </Field>
                  <Field label="결정고시 건폐율 (%)">
                    <input type="number" name="decision_cov_limit" value={formData.decision_cov_limit ?? ''} onChange={handleChange} className={inputCls} placeholder="예: 70" min={0} step={5} />
                  </Field>
                  <Field label="결정고시 높이 (m)">
                    <input type="number" name="decision_height_limit" value={formData.decision_height_limit ?? ''} onChange={handleChange} className={inputCls} placeholder="예: 120" min={0} step={1} />
                  </Field>
                </div>
              )}
            </div>
            <p className="mt-2 text-[10px]" style={{color:'var(--mute)'}}>※ 확인 시 도시계획시설 저촉 → 조건부통과(YELLOW)</p>
          </details>

          {/* 건축협정 */}
          <details className="px-3 py-2" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--warn)',backgroundColor:'var(--canvas)'}}>
            <summary className="text-xs cursor-pointer select-none font-medium" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>건축협정</summary>
            <div className="space-y-2 mt-2">
              <label className="flex items-center gap-2 text-xs cursor-pointer">
                <input type="checkbox" name="building_agreement" checked={!!formData.building_agreement} onChange={(e) => setFormData({ building_agreement: e.target.checked })} className="w-4 h-4 accent-[var(--warn)]" />
                <span>협정 체결 (건폐율·용적률 1.2배)</span>
              </label>
              <label className="flex items-center gap-2 text-xs cursor-pointer ml-4">
                <input type="checkbox" name="agreement_landscape_road_facing" checked={!!formData.agreement_landscape_road_facing} onChange={(e) => setFormData({ agreement_landscape_road_facing: e.target.checked })} disabled={!formData.building_agreement} className="w-4 h-4 accent-[var(--warn)]" />
                <span className={!formData.building_agreement ? 'text-gray-400' : ''}>조경 도로면 통합조성 (의무 0.8배)</span>
              </label>
            </div>
            <p className="mt-2 text-[10px]" style={{color:'var(--mute)'}}>※ 협정 인가 + 심의 통과 시에만 효력</p>
          </details>

          {/* 특별 지구·인증 특례 */}
          <details className="px-3 py-2" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)'}}>
            <summary className="text-xs cursor-pointer select-none font-medium" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>특별 지구·인증 특례</summary>
            <div className="space-y-2 mt-2">
              <label className="flex items-center gap-2 text-xs cursor-pointer">
                <input type="checkbox" name="rema_zone" checked={!!formData.rema_zone} onChange={(e) => setFormData({ rema_zone: e.target.checked })} className="w-4 h-4 accent-[var(--brand)]" />
                <span>재정비촉진지구 (용적률 ×1.2)</span>
              </label>
              <label className="flex items-center gap-2 text-xs cursor-pointer">
                <input type="checkbox" name="easy_remodel" checked={!!formData.easy_remodel} onChange={(e) => setFormData({ easy_remodel: e.target.checked })} disabled={!isApartment} className="w-4 h-4 accent-[var(--brand)]" />
                <span className={!isApartment ? 'text-gray-400' : ''}>리모델링이 쉬운 구조 (공동주택, 용적률 ×1.2)</span>
              </label>
              <label className="flex items-center gap-2 text-xs cursor-pointer">
                <input type="checkbox" name="public_rental" checked={!!formData.public_rental} onChange={(e) => setFormData({ public_rental: e.target.checked })} className="w-4 h-4 accent-[var(--brand)]" />
                <span>공공지원민간임대주택 (법정 상한까지)</span>
              </label>
            </div>
            <p className="mt-2 text-[10px]" style={{color:'var(--mute)'}}>※ 실제 인허가 단계에서 검토 필수</p>
          </details>

          {/* 도시계획시설 저촉 면적 */}
          <details className="px-3 py-2" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)'}}>
            <summary className="text-xs cursor-pointer select-none font-medium" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>시설 저촉 면적</summary>
            <div className="mt-2">
              <Field label="시설부지 면적 (㎡)" hint="비워두면 자동 산정">
                <input type="number" name="urban_facility_exclude_area" value={formData.urban_facility_exclude_area} onChange={handleChange} min="0" step="0.01" className={inputCls} placeholder="예: 50.5" />
              </Field>
            </div>
            <p className="mt-2 text-[10px]" style={{color:'var(--mute)'}}>※ 입력 시 VWorld×SHP 자동 추정 결과 무시</p>
          </details>

          {/* 높이·일조 */}
          <details className="px-3 py-2" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--warn)',backgroundColor:'var(--canvas)'}}>
            <summary className="text-xs cursor-pointer select-none font-medium" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>높이·일조 판정</summary>
            <div className="space-y-2 mt-2">
              <Field label="정북 이격거리 (m)" hint="§86 ①항 자동비교">
                <input type="number" name="north_setback_m" value={formData.north_setback_m} onChange={handleChange} min="0" step="0.01" className={inputCls} placeholder="예: 4.5" />
              </Field>
              <Field label="정북 인접 용도지역" hint="비주거 시 제외">
                <select name="adjacent_zone_north" value={formData.adjacent_zone_north} onChange={handleChange} className={inputCls}>
                  <option value="">미지정</option>
                  <option value="제1종전용주거지역">제1종전용주거지역</option>
                  <option value="제2종전용주거지역">제2종전용주거지역</option>
                  <option value="제1종일반주거지역">제1종일반주거지역</option>
                  <option value="제2종일반주거지역">제2종일반주거지역</option>
                  <option value="제3종일반주거지역">제3종일반주거지역</option>
                  <option value="준주거지역">준주거지역</option>
                  <option value="중심상업지역">중심상업지역</option>
                  <option value="일반상업지역">일반상업지역</option>
                  <option value="근린상업지역">근린상업지역</option>
                  <option value="유통상업지역">유통상업지역</option>
                  <option value="전용공업지역">전용공업지역</option>
                  <option value="일반공업지역">일반공업지역</option>
                  <option value="준공업지역">준공업지역</option>
                  <option value="비주거(기타)">비주거(기타)</option>
                </select>
              </Field>
              <Field label="20m 이상 도로 접함" hint="§86 ②항 1호 제외">
                <select name="road_20m_adjacent" value={formData.road_20m_adjacent} onChange={handleChange} className={inputCls}>
                  <option value="">미지정</option>
                  <option value="yes">예 (20m 이상)</option>
                  <option value="no">아니오</option>
                </select>
              </Field>
              <Field label="가로구역 최고높이 (m)" hint="§60 자동비교">
                <input type="number" name="street_block_max_height_m" value={formData.street_block_max_height_m} onChange={handleChange} min="1" step="0.1" className={inputCls} placeholder="예: 30" />
              </Field>
            </div>
            <p className="mt-2 text-[10px]" style={{color:'var(--mute)'}}>※ 미입력 시 수동 검토 필요</p>
          </details>

        </div>

      </div>{/* end outer 3-column */}

      <BriefUploader onExtracted={(data) => setBriefConditions(data)} />

      <button
        type="submit"
        disabled={loading || !formData.address || !formData.building_use}
        className="w-full py-3 font-semibold text-sm transition-colors"
        style={{backgroundColor:'var(--brand)',color:'#fff',borderRadius:'var(--radius-pill)',height:'var(--btn-h)',opacity:(loading || !formData.address || !formData.building_use)?0.4:1,cursor:(loading || !formData.address || !formData.building_use)?'not-allowed':'pointer',fontFamily:'var(--font-sans)'}}
      >
        {loading ? '진단 중...' : isMulti ? `합필 진단 시작 (${additionalParcels.length + 1}개 필지)` : '법규 진단 시작'}
      </button>
    </form>
  )
}

function SectionLabel({ children }) {
  return (
    <p className="text-xs font-semibold uppercase pb-1" style={{color:'var(--mute)',fontFamily:'var(--font-mono)',letterSpacing:'0.08em',borderBottom:'1px solid var(--hairline)'}}>
      {children}
    </p>
  )
}

function RatioCell({ formData }) {
  const site = parseFloat(formData.site_area) || 0
  const building = parseFloat(formData.building_area) || 0
  const above = parseFloat(formData.floor_area_above) || 0
  const parking = parseFloat(formData.floor_area_parking_above) || 0
  const refuge = parseFloat(formData.floor_area_refuge) || 0
  const attic = parseFloat(formData.floor_area_attic_refuge) || 0
  const farArea = Math.max(0, above - parking - refuge - attic)

  const coverage = site > 0 && building > 0 ? (building / site) * 100 : null
  const far = site > 0 && above > 0 ? (farArea / site) * 100 : null

  return (
    <div className="px-3 py-2 flex flex-col justify-center" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--info)',backgroundColor:'var(--canvas)'}}>
      <p className="text-[10px] font-semibold mb-1.5" style={{color:'var(--mute)',fontFamily:'var(--font-mono)',textTransform:'uppercase',letterSpacing:'0.06em'}}>자동계산</p>
      <div className="flex gap-4">
        <div>
          <span className="text-[10px] block" style={{color:'var(--mute)'}}>건폐율</span>
          <span className="text-base font-bold tabular-nums" style={{color:'var(--ink)',fontFamily:'var(--font-mono)'}}>
            {coverage !== null ? `${coverage.toFixed(1)}%` : '—'}
          </span>
        </div>
        <div>
          <span className="text-[10px] block" style={{color:'var(--mute)'}}>용적률</span>
          <span className="text-base font-bold tabular-nums" style={{color:'var(--ink)',fontFamily:'var(--font-mono)'}}>
            {far !== null ? `${far.toFixed(1)}%` : '—'}
          </span>
        </div>
      </div>
    </div>
  )
}

function FloorAreaSummary({ formData }) {
  const above = parseFloat(formData.floor_area_above) || 0
  const below = parseFloat(formData.floor_area_below) || 0
  const parking = parseFloat(formData.floor_area_parking_above) || 0
  const refuge = parseFloat(formData.floor_area_refuge) || 0
  const atticRefuge = parseFloat(formData.floor_area_attic_refuge) || 0
  if (above <= 0 && below <= 0) return null
  const farArea = Math.max(0, above - parking - refuge - atticRefuge)
  const hasExclusion = below > 0 || parking > 0 || refuge > 0 || atticRefuge > 0
  const excludedParts = []
  if (parking > 0) excludedParts.push(`지상 주차장 ${parking.toLocaleString()}㎡`)
  if (refuge > 0) excludedParts.push(`피난안전구역 ${refuge.toLocaleString()}㎡`)
  if (atticRefuge > 0) excludedParts.push(`경사지붕 대피공간 ${atticRefuge.toLocaleString()}㎡`)
  return (
    <p className="text-xs leading-relaxed" style={{color:'var(--mute)'}}>
      전체 연면적:{' '}
      <span className="font-semibold" style={{color:'var(--body)'}}>{(above + below).toLocaleString()}㎡</span>
      {hasExclusion && (
        <span style={{color:'var(--faint)'}}>
          {' '}· 용적률 산정:{' '}
          <span className="font-semibold" style={{color:'var(--link)',fontFamily:'var(--font-mono)'}}>{farArea.toLocaleString()}㎡</span>
          {excludedParts.length > 0 && (
            <span className="ml-1">({excludedParts.join(', ')} 제외)</span>
          )}
        </span>
      )}
    </p>
  )
}

function AutoLandInfoBanner({ loading, info }) {
  if (loading) {
    return (
      <div className="mt-2 text-xs px-2 py-1.5 inline-flex items-center gap-1.5" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--mute)',backgroundColor:'var(--canvas)'}}>
        <div style={{width:10,height:10,border:'2px solid var(--hairline)',borderTopColor:'var(--brand)',borderRadius:'50%',animation:'spin 0.8s linear infinite',flexShrink:0}} />
        토지이용계획 조회 중...
      </div>
    )
  }
  if (!info) return null
  const items = []
  if (info.zone_use) items.push(['용도지역', info.zone_use])
  if (info.zone_district) items.push(['지역지구', info.zone_district])
  if (info.zone_area) items.push(['용도구역', info.zone_area])
  if (info.land_category) items.push(['지목', info.land_category])
  if (info.official_price) items.push(['공시지가', `${info.official_price.toLocaleString()}원/㎡`])
  if (info.road_width_auto != null) items.push(['전면도로 폭', `${info.road_width_auto}m (자동)`])
  if (items.length === 0) {
    return <p className="mt-2 text-xs" style={{color:'var(--warn-deep)'}}>토지이용계획 조회 실패 (수동 입력 필요)</p>
  }
  return (
    <div className="mt-2 text-xs px-3 py-2" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--info)',backgroundColor:'var(--canvas)'}}>
      <p className="font-semibold mb-1" style={{color:'var(--ink)'}}>자동 조회 결과 (VWorld)</p>
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
        {items.map(([k, v]) => (
          <div key={k}>
            <span style={{color:'var(--mute)'}}>{k}: </span>
            <span className="font-medium" style={{color:'var(--ink)'}}>{v}</span>
          </div>
        ))}
      </div>
      <p className="mt-1 text-[10px]" style={{color:'var(--link)'}}>↓ 아래 입력란에 자동 반영됨. 실제와 다르면 수정하세요.</p>
    </div>
  )
}

function AreaWithRatio({ name, value, onChange, siteArea, placeholder }) {
  const area = parseFloat(value) || 0
  const site = parseFloat(siteArea) || 0
  const ratio = site > 0 && area > 0 ? (area / site) * 100 : null
  return (
    <div className="relative">
      <input
        type="number" name={name} value={value}
        onChange={onChange} min="0" step="0.01"
        className={inputCls + ' pr-16'}
        placeholder={placeholder}
      />
      {ratio !== null && (
        <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--font-size-2xs)] text-blue-600 font-medium pointer-events-none">
          {ratio.toFixed(1)}%
        </span>
      )}
    </div>
  )
}

function Field({ label, required, hint, children }) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>
        {label}
        {required && <span className="ml-0.5" style={{color:'var(--error)'}}>*</span>}
        {hint && <span className="ml-1 font-normal text-xs" style={{color:'var(--faint)'}}>({hint})</span>}
      </label>
      {children}
    </div>
  )
}

const inputCls =
  'w-full px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--brand)] focus:ring-offset-0'
  + ' border border-[var(--hairline)] rounded-[6px] bg-[var(--canvas-elevated)] text-[var(--ink)] font-[var(--font-sans)]'

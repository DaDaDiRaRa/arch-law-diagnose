import { useDiagnoseStore } from '../../stores/diagnoseStore'
import { api } from '../../utils/api'
import AddressSearch from '../AddressSearch'

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
  '', // 자동 조회
  '제1종전용주거지역', '제2종전용주거지역',
  '제1종일반주거지역', '제2종일반주거지역', '제3종일반주거지역',
  '준주거지역',
  '중심상업지역', '일반상업지역', '근린상업지역', '유통상업지역',
  '전용공업지역', '일반공업지역', '준공업지역',
  '보전녹지지역', '생산녹지지역', '자연녹지지역',
]

export default function InputForm() {
  const {
    formData, setFormData, setSelectedAddress, setResult, setLoading, setError, loading,
    additionalParcels, addParcel, removeParcel, updateParcel, setParcelAddress,
    autoLandInfo, autoLandLoading,
  } = useDiagnoseStore()

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

    // 합필 모드 검증
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
      // 합필 진단
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
        ...(formData.floor_area_below
          ? { floor_area_below: parseFloat(formData.floor_area_below) }
          : {}),
        ...(formData.floor_area_parking_above
          ? { floor_area_parking_above: parseFloat(formData.floor_area_parking_above) }
          : {}),
        ...(formData.floor_area_refuge
          ? { floor_area_refuge: parseFloat(formData.floor_area_refuge) }
          : {}),
        ...(formData.floor_area_attic_refuge
          ? { floor_area_attic_refuge: parseFloat(formData.floor_area_attic_refuge) }
          : {}),
        ...(formData.building_use_detail ? { building_use_detail: formData.building_use_detail } : {}),
        ...(formData.zone_district ? { zone_district: formData.zone_district } : {}),
        ...(formData.provided_parking_spaces
          ? { provided_parking_spaces: parseInt(formData.provided_parking_spaces, 10) }
          : {}),
        ...(formData.public_open_space_area
          ? { public_open_space_area: parseFloat(formData.public_open_space_area) }
          : {}),
        ...(formData.green_grade      ? { green_grade: formData.green_grade } : {}),
        ...(formData.energy_grade     ? { energy_grade: formData.energy_grade } : {}),
        ...(formData.smart_grade      ? { smart_grade: formData.smart_grade } : {}),
        ...(formData.long_life_grade  ? { long_life_grade: formData.long_life_grade } : {}),
        ...(formData.far_limit_manual_override
          ? { far_limit_manual_override: parseFloat(formData.far_limit_manual_override) }
          : {}),
        ...(formData.relief_reason_manual
          ? { relief_reason_manual: formData.relief_reason_manual }
          : {}),
        ...(formData.urban_facility_exclude_area
          ? { urban_facility_exclude_area: parseFloat(formData.urban_facility_exclude_area) }
          : {}),
        floors_above: parseInt(formData.floors_above, 10),
        floors_below: parseInt(formData.floors_below || '0', 10),
        height: parseFloat(formData.height),
        ...(formData.road_width ? { road_width: parseFloat(formData.road_width) } : {}),
        ...(formData.landscape_area ? { landscape_area: parseFloat(formData.landscape_area) } : {}),
        ...(isApartment && formData.units ? { units: parseInt(formData.units, 10) } : {}),
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
        // ZONE_LOOKUP_FAILED 같은 구조화 에러 처리
        if (err.detail && typeof err.detail === 'object' && err.detail.error === 'ZONE_LOOKUP_FAILED') {
          const failed = err.detail.failed_addresses?.join('\n  · ') || ''
          setError(`${err.detail.message}\n  · ${failed}`)
        } else {
          setError(err.message)
        }
      }
      return
    }

    // 단일 진단 (기존)
    const payload = {
      address: formData.address,
      pnu: formData.pnu || undefined,
      building_use: formData.building_use,
      site_area: parseFloat(formData.site_area),
      building_area: parseFloat(formData.building_area),
      floor_area_above: parseFloat(formData.floor_area_above),
      ...(formData.floor_area_below
        ? { floor_area_below: parseFloat(formData.floor_area_below) }
        : {}),
      floors_above: parseInt(formData.floors_above, 10),
      floors_below: parseInt(formData.floors_below || '0', 10),
      height: parseFloat(formData.height),
      ...(formData.road_width ? { road_width: parseFloat(formData.road_width) } : {}),
      ...(formData.landscape_area ? { landscape_area: parseFloat(formData.landscape_area) } : {}),
      ...(isApartment && formData.units ? { units: parseInt(formData.units, 10) } : {}),
      ...(formData.zone_use_override ? { zone_use_override: formData.zone_use_override } : {}),
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

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* 1번 필지 (대표) */}
      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-1.5">
          {isMulti ? '1번 필지 주소' : '대지 주소'} <span className="text-red-500">*</span>
        </label>
        <AddressSearch onSelect={handleAddressSelect} />
        {formData.address && (
          <p className="mt-1.5 text-xs text-blue-600 font-medium">{formData.address}</p>
        )}
        {formData.pnu && (
          <p className="mt-0.5 text-xs text-gray-400 font-mono">PNU: {formData.pnu}</p>
        )}
        <AutoLandInfoBanner loading={autoLandLoading} info={autoLandInfo} />
      </div>

      {/* 추가 필지들 */}
      {additionalParcels.map((p, idx) => (
        <div key={idx} className="border border-blue-200 bg-blue-50/40 rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-700">
              {idx + 2}번 필지 <span className="text-red-500">*</span>
            </span>
            <button
              type="button"
              onClick={() => removeParcel(idx)}
              className="text-xs text-red-600 hover:underline"
            >
              제거
            </button>
          </div>
          <AddressSearch onSelect={(addr) => setParcelAddress(idx, addr)} />
          {p.address && (
            <p className="text-xs text-blue-600 font-medium">{p.address}</p>
          )}
          {p.pnu && (
            <p className="text-xs text-gray-400 font-mono">PNU: {p.pnu}</p>
          )}
          <div className="grid grid-cols-2 gap-2">
            <Field label={`${idx + 2}번 필지 면적 (㎡)`} required>
              <input
                type="number"
                value={p.site_area}
                onChange={(e) => updateParcel(idx, { site_area: e.target.value })}
                min="1" step="0.01" className={inputCls} placeholder="300" required
              />
            </Field>
            <Field label="용도지역 (선택)">
              <select
                value={p.zone_use_override || ''}
                onChange={(e) => updateParcel(idx, { zone_use_override: e.target.value })}
                className={inputCls}
              >
                <option value="">자동 (VWorld 조회)</option>
                {ZONE_USES.filter(Boolean).map((z) => (
                  <option key={z} value={z}>{z}</option>
                ))}
              </select>
            </Field>
          </div>
        </div>
      ))}

      {/* 필지 추가 버튼 */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={addParcel}
          disabled={!formData.address}
          className="text-sm text-blue-600 hover:text-blue-800 disabled:text-gray-300 font-medium"
        >
          + 필지 추가 {isMulti && `(${additionalParcels.length + 1}개 합산)`}
        </button>
        {isMulti && totalSiteArea > 0 && (
          <span className="text-xs text-gray-600">
            합산 대지면적: <span className="font-semibold text-gray-900">{totalSiteArea.toLocaleString()}㎡</span>
          </span>
        )}
      </div>

      {isMulti && (
        <div className="text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded p-2 leading-relaxed">
          ℹ️ <b>합필 진단 (Phase 2)</b> — 용도지역이 다른 경우 국토계획법 제84조에 따라 자동 처리됩니다.
          <ul className="mt-1 ml-4 list-disc text-blue-600">
            <li>같은 용도지역 → 단순 합산</li>
            <li>작은 부분이 330㎡ 이하 → 큰 부분 기준 전체 적용 (소규모 예외)</li>
            <li>그 외 → 면적 가중평균 (안분 계산)</li>
          </ul>
        </div>
      )}

      {/* 건축물 용도 + 세부/복합 용도 */}
      <div className="grid grid-cols-1 gap-3">
        <Field label="건축물 주 용도" required>
          <select
            name="building_use"
            value={formData.building_use}
            onChange={handleChange}
            className={inputCls}
            required
          >
            <option value="">선택하세요</option>
            {BUILDING_USES.map((u) => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
        </Field>
        <Field
          label="세부/복합 용도 (선택)"
          hint="예: 공공업무시설(구청, 구의회, 어린이집(노유자시설), 부설주차장)"
        >
          <input
            type="text" name="building_use_detail" value={formData.building_use_detail}
            onChange={handleChange} className={inputCls}
            placeholder="자세한 용도 표기 (검토서에 그대로 표시)"
          />
        </Field>
      </div>

      {/* 용도지역 + 지역지구 — 주소 선택 시 자동 채움 */}
      <div className="grid grid-cols-2 gap-3">
        <Field
          label={isMulti ? '1번 필지 용도지역' : '용도지역'}
          hint={
            autoLandInfo?.zone_use && formData.zone_use_override === autoLandInfo.zone_use
              ? '🔄 자동 조회됨 · 다르면 변경'
              : '주소 선택 시 자동 조회'
          }
        >
          <select
            name="zone_use_override"
            value={formData.zone_use_override || ''}
            onChange={handleChange}
            className={inputCls}
          >
            <option value="">미지정 (진단 시 VWorld 재조회)</option>
            {ZONE_USES.filter(Boolean).map((z) => (
              <option key={z} value={z}>{z}</option>
            ))}
          </select>
        </Field>
        <Field
          label="지역지구"
          hint={
            autoLandInfo?.zone_district && formData.zone_district === autoLandInfo.zone_district
              ? '🔄 자동 조회됨 · 다르면 변경'
              : '주소 선택 시 자동 조회'
          }
        >
          <input
            type="text" name="zone_district" value={formData.zone_district}
            onChange={handleChange} className={inputCls}
            placeholder={
              autoLandLoading
                ? '조회 중...'
                : autoLandInfo?.zone_district || '예: 지구단위계획구역, 일반미관지구'
            }
          />
        </Field>
      </div>

      {/* 면적 입력 */}
      <div className="grid grid-cols-2 gap-3">
        <Field label={isMulti ? '1번 필지 면적 (㎡)' : '대지면적 (㎡)'} required>
          <input
            type="number" name="site_area" value={formData.site_area}
            onChange={handleChange} min="1" step="0.01"
            className={inputCls} placeholder="500" required
          />
        </Field>
        <Field label="건축면적 (㎡)" required>
          <input
            type="number" name="building_area" value={formData.building_area}
            onChange={handleChange} min="1" step="0.01"
            className={inputCls} placeholder="250" required
          />
        </Field>
      </div>

      {/* 연면적 — 지상(필수) + 지하(선택) + 지상 주차장(선택) */}
      <div className="grid grid-cols-3 gap-3">
        <Field label="지상 연면적 (㎡)" required hint="주차장 포함 전체">
          <input
            type="number" name="floor_area_above" value={formData.floor_area_above}
            onChange={handleChange} min="1" step="0.01"
            className={inputCls} placeholder="1500" required
          />
        </Field>
        <Field label="지하 연면적 (㎡)" hint="선택 — 용적률 제외">
          <input
            type="number" name="floor_area_below" value={formData.floor_area_below}
            onChange={handleChange} min="0" step="0.01"
            className={inputCls} placeholder="500"
          />
        </Field>
        <Field label="지상 주차장 면적 (㎡)" hint="선택 — 부속용도, 용적률 제외">
          <input
            type="number" name="floor_area_parking_above" value={formData.floor_area_parking_above}
            onChange={handleChange} min="0" step="0.01"
            className={inputCls} placeholder="300"
          />
        </Field>
      </div>

      {/* 용적률 추가 제외 (고층 등, 선택) */}
      <details className="rounded border border-gray-200 bg-gray-50 px-3 py-2">
        <summary className="text-xs text-gray-600 cursor-pointer select-none">
          용적률 추가 제외 면적 (선택, 고층 건축물 한정)
        </summary>
        <div className="grid grid-cols-2 gap-3 mt-2">
          <Field label="피난안전구역 면적 (㎡)" hint="30층 이상/120m 이상">
            <input
              type="number" name="floor_area_refuge" value={formData.floor_area_refuge}
              onChange={handleChange} min="0" step="0.01"
              className={inputCls} placeholder="200"
            />
          </Field>
          <Field label="경사지붕 대피공간 (㎡)" hint="11층 이상">
            <input
              type="number" name="floor_area_attic_refuge" value={formData.floor_area_attic_refuge}
              onChange={handleChange} min="0" step="0.01"
              className={inputCls} placeholder="50"
            />
          </Field>
        </div>
      </details>

      <FloorAreaSummary formData={formData} />

      {/* 용적률 완화 입력 (선택) */}
      <details className="rounded border border-emerald-200 bg-emerald-50/60 px-3 py-2">
        <summary className="text-xs text-emerald-800 cursor-pointer select-none font-medium">
          🌿 용적률 완화 입력 (선택 — 모두 비워두면 일반 한도 적용)
        </summary>
        <div className="grid grid-cols-2 gap-3 mt-3">
          <Field label="녹색건축 인증" hint="건축법 시행령 §61의2">
            <select
              name="green_grade" value={formData.green_grade}
              onChange={handleChange} className={inputCls}
            >
              <option value="">미인증 / 미적용</option>
              <option value="최우수">최우수 (+9%)</option>
              <option value="우수">우수 (+6%)</option>
              <option value="우량">우량 (+3%)</option>
              <option value="일반">일반</option>
            </select>
          </Field>
          <Field label="에너지효율 등급" hint="건축법 시행령 §61의2">
            <select
              name="energy_grade" value={formData.energy_grade}
              onChange={handleChange} className={inputCls}
            >
              <option value="">미인증 / 미적용</option>
              <option value="1++">1++ (+12%)</option>
              <option value="1+">1+ (+9%)</option>
              <option value="1">1등급 (+6%)</option>
              <option value="2">2등급</option>
            </select>
          </Field>
          <Field label="지능형건축물 인증" hint="건축법 시행령 §61의2">
            <select
              name="smart_grade" value={formData.smart_grade}
              onChange={handleChange} className={inputCls}
            >
              <option value="">미인증 / 미적용</option>
              <option value="최우수">최우수 (+9%)</option>
              <option value="우수">우수 (+6%)</option>
              <option value="우량">우량 (+3%)</option>
              <option value="일반">일반</option>
            </select>
          </Field>
          <Field label="장수명주택 인증" hint="공동주택 한정">
            <select
              name="long_life_grade" value={formData.long_life_grade}
              onChange={handleChange} className={inputCls}
              disabled={!isApartment}
            >
              <option value="">미인증 / 미적용</option>
              <option value="최우수">최우수 (+9%)</option>
              <option value="우수">우수 (+6%)</option>
              <option value="우량">우량 (+3%)</option>
              <option value="일반">일반 (+3%)</option>
            </select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3 mt-3 pt-3 border-t border-emerald-200">
          <Field label="용적률 한도 직접 지정 (%)" hint="심의·지구단위·정비사업 인센티브">
            <input
              type="number" name="far_limit_manual_override" value={formData.far_limit_manual_override}
              onChange={handleChange} min="1" step="0.01"
              className={inputCls} placeholder="예: 460"
            />
          </Field>
          <Field label="완화 사유 (선택)" hint="검토서에 그대로 표시">
            <input
              type="text" name="relief_reason_manual" value={formData.relief_reason_manual}
              onChange={handleChange} className={inputCls}
              placeholder="예: 도시계획심의 결정"
            />
          </Field>
        </div>
        <p className="mt-2 text-[10px] text-emerald-700 leading-relaxed">
          ※ 인증 등급별 완화율은 자동 합산 (합산 캡 12%, 전체 캡 기본 한도의 1.2배).
          한도 직접 지정 시 인증 등급 합산 대신 그 값 사용.
          모든 완화는 자동 추정이며 <b>실제 인허가 심의에서 인정받아야 효력</b> 발생합니다.
        </p>
      </details>

      {/* 🗺 도시계획시설 저촉 면적 — B7 */}
      <details className="rounded-lg border border-sky-200 bg-sky-50/40 p-3">
        <summary className="cursor-pointer text-sm font-semibold text-sky-900 select-none">
          🗺 도시계획시설 저촉 면적 (선택 — 자동 추정 결과 직접 수정 시)
        </summary>
        <div className="mt-3">
          <Field
            label="시설부지 면적 (㎡)"
            hint="입력 시 자동 추정 결과 무시. 비워두면 VWorld 지적도 × 시설 SHP 자동 산정."
          >
            <input
              type="number" name="urban_facility_exclude_area"
              value={formData.urban_facility_exclude_area}
              onChange={handleChange} min="0" step="0.01"
              className={inputCls} placeholder="예: 50.5"
            />
          </Field>
        </div>
        <p className="mt-2 text-[10px] text-sky-700 leading-relaxed">
          ※ 대지 일부가 도시계획시설(도로/공원/공공청사 등) 부지에 포함될 때
          <b> 그 면적은 대지면적에서 제외 산정</b>합니다 (건축법 시행령 §3).
          자동 추정은 VWorld 지적 폴리곤과 결정도형 SHP의 공간 교차로 계산하며,
          실제 도면 확인 후 수정 가능합니다.
        </p>
      </details>

      {/* 층수 + 높이 */}
      <div className="grid grid-cols-4 gap-3">
        <Field label="지상 층수" required>
          <input
            type="number" name="floors_above" value={formData.floors_above}
            onChange={handleChange} min="1" className={inputCls} placeholder="6" required
          />
        </Field>
        <Field label="지하 층수">
          <input
            type="number" name="floors_below" value={formData.floors_below}
            onChange={handleChange} min="0" className={inputCls} placeholder="1"
          />
        </Field>
        <Field label="건물 높이 (m)" required>
          <input
            type="number" name="height" value={formData.height}
            onChange={handleChange} min="1" step="0.1"
            className={inputCls} placeholder="24" required
          />
        </Field>
        <Field label="전면도로 폭 (m)" hint="미입력 가능">
          <input
            type="number" name="road_width" value={formData.road_width}
            onChange={handleChange} min="1" step="0.1"
            className={inputCls} placeholder="12"
          />
        </Field>
      </div>

      {/* 세대수 (공동주택) + 계획 주차대수 */}
      <div className="grid grid-cols-2 gap-3">
        {isApartment ? (
          <Field label="세대수" hint="공동주택 주차 산정용">
            <input
              type="number" name="units" value={formData.units}
              onChange={handleChange} min="1"
              className={inputCls} placeholder="50"
            />
          </Field>
        ) : <div />}
        <Field label="계획 주차대수 (선택)" hint="법정 대수와 비교">
          <input
            type="number" name="provided_parking_spaces" value={formData.provided_parking_spaces}
            onChange={handleChange} min="0"
            className={inputCls} placeholder="30"
          />
        </Field>
      </div>

      {/* 공개공지 + 조경 — 각각 우측에 % 자동 표시 */}
      <div className="grid grid-cols-2 gap-3">
        <Field label="공개공지 면적 (㎡)" hint="선택, 입력 시 % 자동 표시">
          <AreaWithRatio
            name="public_open_space_area"
            value={formData.public_open_space_area}
            onChange={handleChange}
            siteArea={formData.site_area}
            placeholder="150"
          />
        </Field>
        <Field label="조경면적 (㎡)" hint="선택, 입력 시 % 자동 표시">
          <AreaWithRatio
            name="landscape_area"
            value={formData.landscape_area}
            onChange={handleChange}
            siteArea={formData.site_area}
            placeholder="75"
          />
        </Field>
      </div>

      <button
        type="submit"
        disabled={loading || !formData.address || !formData.building_use}
        className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-semibold rounded-lg transition-colors text-sm"
      >
        {loading ? '진단 중...' : isMulti ? `합필 진단 시작 (${additionalParcels.length + 1}개 필지)` : '법규 진단 시작'}
      </button>
    </form>
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
    <p className="-mt-3 text-xs text-gray-500 leading-relaxed">
      전체 연면적 (지상+지하):{' '}
      <span className="font-semibold text-gray-700">{(above + below).toLocaleString()}㎡</span>
      {hasExclusion && (
        <span className="text-gray-400">
          {' '}· 용적률 산정 면적:{' '}
          <span className="font-semibold text-blue-700">{farArea.toLocaleString()}㎡</span>
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
      <div className="mt-2 text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded px-2 py-1.5 inline-flex items-center gap-1.5">
        <span className="animate-spin">⟳</span>
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
  if (items.length === 0) {
    return (
      <p className="mt-2 text-xs text-amber-600">⚠ 토지이용계획 조회 실패 (수동 입력 필요)</p>
    )
  }
  return (
    <div className="mt-2 text-xs bg-blue-50 border border-blue-200 rounded px-3 py-2">
      <p className="font-semibold text-blue-900 mb-1">🔄 자동 조회 결과 (VWorld)</p>
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
        {items.map(([k, v]) => (
          <div key={k}>
            <span className="text-gray-500">{k}: </span>
            <span className="font-medium text-gray-800">{v}</span>
          </div>
        ))}
      </div>
      <p className="mt-1 text-blue-600 text-[10px]">
        ↓ 아래 입력란에 자동 반영됨. 실제와 다르면 수정하세요.
      </p>
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
        className={inputCls + ' pr-24'}
        placeholder={placeholder}
      />
      {ratio !== null && (
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-blue-600 font-medium pointer-events-none">
          대지의 {ratio.toFixed(2)}%
        </span>
      )}
    </div>
  )
}

function Field({ label, required, hint, children }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
        {hint && <span className="text-gray-400 ml-1 font-normal text-xs">({hint})</span>}
      </label>
      {children}
    </div>
  )
}

const inputCls =
  'w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500'

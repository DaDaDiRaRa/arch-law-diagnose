import { useDiagnoseStore } from '../../stores/diagnoseStore'
import { api } from '../../utils/api'
import AddressSearch from '../AddressSearch'

const BUILDING_USES = [
  '제1종근린생활시설', '제2종근린생활시설', '근린생활시설',
  '공동주택', '단독주택',
  '업무시설', '판매시설',
  '숙박시설', '의료시설', '교육연구시설',
  '문화및집회시설', '종교시설', '운동시설',
  '위락시설', '공장', '창고시설', '기타',
]

export default function InputForm() {
  const { formData, setFormData, setSelectedAddress, setResult, setLoading, setError, loading } =
    useDiagnoseStore()

  const handleAddressSelect = (addr) => {
    setSelectedAddress(addr)
  }

  const handleChange = (e) => {
    setFormData({ [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!formData.address) return

    setLoading(true)

    const isApartment = formData.building_use === '공동주택'

    const payload = {
      address: formData.address,
      pnu: formData.pnu || undefined,
      building_use: formData.building_use,
      site_area: parseFloat(formData.site_area),
      building_area: parseFloat(formData.building_area),
      total_floor_area: parseFloat(formData.total_floor_area),
      floors_above: parseInt(formData.floors_above, 10),
      floors_below: parseInt(formData.floors_below || '0', 10),
      height: parseFloat(formData.height),
      ...(formData.road_width ? { road_width: parseFloat(formData.road_width) } : {}),
      ...(formData.landscape_area ? { landscape_area: parseFloat(formData.landscape_area) } : {}),
      ...(isApartment && formData.units ? { units: parseInt(formData.units, 10) } : {}),
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

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* 주소 */}
      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-1.5">
          대지 주소 <span className="text-red-500">*</span>
        </label>
        <AddressSearch onSelect={handleAddressSelect} />
        {formData.address && (
          <p className="mt-1.5 text-xs text-blue-600 font-medium">{formData.address}</p>
        )}
        {formData.pnu && (
          <p className="mt-0.5 text-xs text-gray-400 font-mono">PNU: {formData.pnu}</p>
        )}
      </div>

      {/* 건축물 용도 */}
      <Field label="건축물 용도" required>
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

      {/* 면적 3종 */}
      <div className="grid grid-cols-3 gap-3">
        <Field label="대지면적 (㎡)" required>
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
        <Field label="연면적 (㎡)" required>
          <input
            type="number" name="total_floor_area" value={formData.total_floor_area}
            onChange={handleChange} min="1" step="0.01"
            className={inputCls} placeholder="1500" required
          />
        </Field>
      </div>

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

      {/* 세대수 (공동주택) + 조경면적 */}
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
        <Field label="조경면적 (㎡)" hint="선택, 200㎡ 이상 대지">
          <input
            type="number" name="landscape_area" value={formData.landscape_area}
            onChange={handleChange} min="0" step="0.01"
            className={inputCls} placeholder="75"
          />
        </Field>
      </div>

      <button
        type="submit"
        disabled={loading || !formData.address || !formData.building_use}
        className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-semibold rounded-lg transition-colors text-sm"
      >
        {loading ? '진단 중...' : '법규 진단 시작'}
      </button>
    </form>
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

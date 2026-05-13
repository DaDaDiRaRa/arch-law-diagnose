import { useState } from 'react'
import { useDiagnoseStore } from '../../stores/diagnoseStore'
import { api } from '../../utils/api'

const BUILDING_USES = [
  '제1종근린생활시설', '제2종근린생활시설', '근린생활시설',
  '공동주택', '단독주택',
  '업무시설', '판매시설',
  '숙박시설', '의료시설', '교육연구시설',
  '문화및집회시설', '종교시설', '운동시설',
  '위락시설', '공장', '창고시설', '기타',
]

const SIGNAL_CFG = {
  GREEN:  { dot: '🟢', label: '적합',   cls: 'text-green-700 bg-green-50' },
  YELLOW: { dot: '🟡', label: '주의',   cls: 'text-yellow-700 bg-yellow-50' },
  RED:    { dot: '🔴', label: '부적합', cls: 'text-red-700 bg-red-50' },
}

const CATEGORY_LABELS = {
  건폐율: '건폐율',
  용적률: '용적률',
  높이_일조: '높이·일조',
  주차: '주차',
  조경: '조경',
  설비_소방: '설비·소방',
}

function emptyScenario(name) {
  return {
    name,
    building_use: '근린생활시설',
    site_area: '',
    building_area: '',
    total_floor_area: '',
    floors_above: '',
    floors_below: '0',
    height: '',
    units: '',
    road_width: '',
    landscape_area: '',
  }
}

export default function ScenarioCompare() {
  const { formData, result } = useDiagnoseStore()
  const [scenarios, setScenarios] = useState(() => [
    seedFromBase(emptyScenario('안 A'), formData),
    emptyScenario('안 B'),
    emptyScenario('안 C'),
  ])
  const [compareResult, setCompareResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const address = formData.address
  const pnu = formData.pnu

  const updateScenario = (idx, patch) =>
    setScenarios((arr) => arr.map((s, i) => (i === idx ? { ...s, ...patch } : s)))

  const removeScenario = (idx) =>
    setScenarios((arr) => arr.filter((_, i) => i !== idx))

  const addScenario = () => {
    if (scenarios.length >= 4) return
    setScenarios((arr) => [...arr, emptyScenario(`안 ${String.fromCharCode(65 + arr.length)}`)])
  }

  const copyFromBase = (idx) => {
    if (!formData.site_area) return
    updateScenario(idx, seedFromBase(scenarios[idx], formData))
  }

  const handleCompare = async () => {
    if (!address) {
      setError('주소를 먼저 선택해주세요 (좌측 입력 폼).')
      return
    }
    const filled = scenarios.filter((s) => s.site_area && s.building_area)
    if (filled.length < 2) {
      setError('최소 2개 시나리오의 필수 면적 정보를 입력하세요.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const payload = {
        address,
        pnu: pnu || undefined,
        scenarios: filled.map((s) => ({
          name: s.name,
          building_use: s.building_use,
          site_area: parseFloat(s.site_area),
          building_area: parseFloat(s.building_area),
          total_floor_area: parseFloat(s.total_floor_area),
          floors_above: parseInt(s.floors_above, 10),
          floors_below: parseInt(s.floors_below || '0', 10),
          height: parseFloat(s.height),
          ...(s.road_width ? { road_width: parseFloat(s.road_width) } : {}),
          ...(s.landscape_area ? { landscape_area: parseFloat(s.landscape_area) } : {}),
          ...(s.building_use === '공동주택' && s.units ? { units: parseInt(s.units, 10) } : {}),
        })),
        skip_ai: true,
      }
      const r = await api.compare(payload)
      setCompareResult(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-purple-100 bg-purple-50 p-4">
        <p className="text-sm font-semibold text-purple-800">시나리오 비교 매트릭스</p>
        <p className="text-xs text-purple-600 mt-0.5">
          최대 4개 안을 동시 진단하여 나란히 비교. 토지 조회는 1회만 수행.
          {!address && ' 좌측에서 주소를 먼저 선택해주세요.'}
        </p>
      </div>

      {/* 시나리오 입력 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {scenarios.map((s, idx) => (
          <ScenarioCard
            key={idx}
            scenario={s}
            canCopy={!!formData.site_area && idx > 0}
            canRemove={scenarios.length > 2}
            onChange={(patch) => updateScenario(idx, patch)}
            onCopy={() => copyFromBase(idx)}
            onRemove={() => removeScenario(idx)}
          />
        ))}
      </div>

      <div className="flex items-center justify-between">
        <button
          onClick={addScenario}
          disabled={scenarios.length >= 4}
          className="text-xs text-purple-600 hover:text-purple-800 disabled:opacity-40 underline"
        >
          + 시나리오 추가 (최대 4개)
        </button>
        <button
          onClick={handleCompare}
          disabled={loading || !address}
          className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-300 text-white text-sm font-semibold rounded-lg"
        >
          {loading ? '비교 중...' : '동시 진단 실행'}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {compareResult && <ComparisonTable data={compareResult} />}
    </div>
  )
}

function ScenarioCard({ scenario, canCopy, canRemove, onChange, onCopy, onRemove }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3 space-y-2">
      <div className="flex items-center justify-between">
        <input
          value={scenario.name}
          onChange={(e) => onChange({ name: e.target.value })}
          className="font-semibold text-sm w-24 border-b border-gray-200 focus:border-purple-500 focus:outline-none"
        />
        <div className="flex gap-2 text-xs">
          {canCopy && (
            <button onClick={onCopy} className="text-blue-600 hover:underline">기본 복사</button>
          )}
          {canRemove && (
            <button onClick={onRemove} className="text-red-500 hover:underline">제거</button>
          )}
        </div>
      </div>
      <select
        value={scenario.building_use}
        onChange={(e) => onChange({ building_use: e.target.value })}
        className={inputCls}
      >
        {BUILDING_USES.map((u) => <option key={u} value={u}>{u}</option>)}
      </select>
      <div className="grid grid-cols-2 gap-2">
        <NumInput v={scenario.site_area}        onChange={(v) => onChange({ site_area: v })}        ph="대지면적" />
        <NumInput v={scenario.building_area}    onChange={(v) => onChange({ building_area: v })}    ph="건축면적" />
        <NumInput v={scenario.total_floor_area} onChange={(v) => onChange({ total_floor_area: v })} ph="연면적" />
        <NumInput v={scenario.floors_above}     onChange={(v) => onChange({ floors_above: v })}     ph="지상층수" />
        <NumInput v={scenario.height}           onChange={(v) => onChange({ height: v })}           ph="높이(m)" />
        <NumInput v={scenario.landscape_area}   onChange={(v) => onChange({ landscape_area: v })}   ph="조경면적" />
      </div>
    </div>
  )
}

function NumInput({ v, onChange, ph }) {
  return (
    <input
      type="number"
      value={v}
      onChange={(e) => onChange(e.target.value)}
      placeholder={ph}
      min="0" step="0.01"
      className={inputCls}
    />
  )
}

const inputCls = 'w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:outline-none focus:ring-2 focus:ring-purple-500'

function ComparisonTable({ data }) {
  const { scenarios, summary } = data
  const categories = Object.keys(scenarios[0]?.result?.results || {})

  return (
    <div className="space-y-3">
      {/* 요약 */}
      {summary?.best && (
        <div className="rounded-lg border border-purple-200 bg-purple-50 p-3 text-sm">
          <span className="font-semibold text-purple-800">최고 점수: {summary.best}</span>
          {summary.best_score != null && (
            <span className="text-purple-700"> ({summary.best_score.toFixed(1)}/10)</span>
          )}
          <span className="text-xs text-purple-600 ml-3">
            🟢 {summary.signal_count.GREEN} · 🟡 {summary.signal_count.YELLOW} · 🔴 {summary.signal_count.RED}
          </span>
        </div>
      )}

      {/* 비교 표 */}
      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs">
            <tr>
              <th className="text-left p-2 border-b font-medium text-gray-600">항목</th>
              {scenarios.map((s, i) => (
                <th key={i} className="text-left p-2 border-b font-medium text-gray-700">{s.name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="p-2 border-b text-gray-500 text-xs">신호</td>
              {scenarios.map((s, i) => {
                const sig = SIGNAL_CFG[s.result.signal] || SIGNAL_CFG.YELLOW
                return (
                  <td key={i} className={`p-2 border-b text-xs font-semibold ${sig.cls}`}>
                    {sig.dot} {sig.label}
                  </td>
                )
              })}
            </tr>
            <tr>
              <td className="p-2 border-b text-gray-500 text-xs">종합 점수</td>
              {scenarios.map((s, i) => (
                <td key={i} className="p-2 border-b font-bold text-gray-800">
                  {s.result.overall_score != null ? `${s.result.overall_score.toFixed(1)}/10` : '–'}
                </td>
              ))}
            </tr>
            <tr>
              <td className="p-2 border-b text-gray-500 text-xs">위험 항목</td>
              {scenarios.map((s, i) => (
                <td key={i} className="p-2 border-b text-xs text-red-600">
                  {s.result.risks?.length || 0}건
                </td>
              ))}
            </tr>

            {categories.map((cat) => (
              <tr key={cat}>
                <td className="p-2 border-b text-gray-500 text-xs">{CATEGORY_LABELS[cat] || cat}</td>
                {scenarios.map((s, i) => {
                  const c = s.result.results?.[cat] || {}
                  return (
                    <td key={i} className="p-2 border-b text-xs">
                      <CategoryCell cat={c} />
                    </td>
                  )
                })}
              </tr>
            ))}

            {/* 시나리오 입력값 (참고) */}
            <tr className="bg-gray-50">
              <td className="p-2 text-gray-400 text-xs">건축/연면적</td>
              {scenarios.map((s, i) => (
                <td key={i} className="p-2 text-xs text-gray-500">
                  {s.input.building_area}/{s.input.total_floor_area}㎡
                </td>
              ))}
            </tr>
            <tr className="bg-gray-50">
              <td className="p-2 text-gray-400 text-xs">층수/높이</td>
              {scenarios.map((s, i) => (
                <td key={i} className="p-2 text-xs text-gray-500">
                  {s.input.floors_above}층/{s.input.height}m
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

function CategoryCell({ cat }) {
  const passed = cat.pass
  const cls =
    passed === false ? 'text-red-600' :
    passed === true ? 'text-green-600' :
    'text-yellow-600'
  const symbol =
    passed === false ? '✗' :
    passed === true ? '✓' :
    '?'

  let detail = ''
  if (cat.actual_pct != null && cat.limit_pct != null) {
    detail = `${cat.actual_pct}/${cat.limit_pct}%`
  } else if (cat.actual_pct != null && cat.required_pct != null) {
    detail = `${cat.actual_pct}/${cat.required_pct}%`
  } else if (cat.required_pct != null) {
    detail = `의무 ${cat.required_pct}%`
  } else if (cat.required_spaces != null) {
    detail = `${cat.required_spaces}대`
  } else if (cat.actual_height_m != null) {
    detail = `${cat.actual_height_m}m`
  }

  return (
    <div>
      <span className={`font-bold ${cls}`}>{symbol}</span>
      {detail && <span className="text-gray-600 ml-1">{detail}</span>}
      {cat.score != null && (
        <span className="text-gray-400 ml-1">({cat.score})</span>
      )}
    </div>
  )
}

function seedFromBase(target, base) {
  if (!base.site_area) return target
  return {
    ...target,
    building_use: base.building_use || target.building_use,
    site_area: base.site_area || '',
    building_area: base.building_area || '',
    total_floor_area: base.total_floor_area || '',
    floors_above: base.floors_above || '',
    floors_below: base.floors_below || '0',
    height: base.height || '',
    units: base.units || '',
    road_width: base.road_width || '',
    landscape_area: base.landscape_area || '',
  }
}

import { useEffect, useMemo, useRef, useState } from 'react'
import { useDiagnoseStore } from '../../stores/diagnoseStore'
import { api } from '../../utils/api'

const VARIABLES = [
  { key: 'building_area',    label: '건축면적',   unit: '㎡', min: 1, max: 10000, step: 10 },
  { key: 'total_floor_area', label: '연면적',     unit: '㎡', min: 1, max: 50000, step: 50 },
  { key: 'floors_above',     label: '지상 층수',  unit: '층', min: 1, max: 50,    step: 1 },
  { key: 'floors_below',     label: '지하 층수',  unit: '층', min: 0, max: 10,    step: 1 },
  { key: 'height',           label: '건물 높이',  unit: 'm',  min: 1, max: 200,   step: 0.5 },
  { key: 'landscape_area',   label: '조경면적',   unit: '㎡', min: 0, max: 5000,  step: 5 },
]

const SIGNAL_CFG = {
  GREEN:  { dot: '🟢', label: '적합',     cls: 'text-green-700' },
  YELLOW: { dot: '🟡', label: '주의 필요', cls: 'text-yellow-700' },
  RED:    { dot: '🔴', label: '부적합',   cls: 'text-red-700' },
}

export default function WhatIfPanel() {
  const {
    result, formData,
    whatIfResult, whatIfLoading, whatIfOverrides,
    setWhatIfLoading, setWhatIfResult, setWhatIfOverrides,
  } = useDiagnoseStore()

  const baseValues = useMemo(() => extractBase(formData), [formData])
  const [values, setValues] = useState(whatIfOverrides || baseValues)
  const debounceRef = useRef(null)

  useEffect(() => {
    // 기본 진단이 새로 돌면 슬라이더 초기화
    setValues(whatIfOverrides || baseValues)
  }, [baseValues, whatIfOverrides])

  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
  }, [])

  if (!result) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6 text-center">
        <p className="text-sm text-gray-500">먼저 좌측에서 기본 진단을 실행해주세요.</p>
        <p className="text-xs text-gray-400 mt-1">What-if는 진단 결과의 토지 정보를 재사용합니다.</p>
      </div>
    )
  }

  const updateValue = (key, raw) => {
    const v = parseFloat(raw)
    const next = { ...values, [key]: isNaN(v) ? 0 : v }
    setValues(next)
    setWhatIfOverrides(next)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => runSimulation(next), 400)
  }

  const runSimulation = async (overrides) => {
    setWhatIfLoading(true)
    try {
      const payload = {
        ...buildBasePayload(formData),
        ...overrides,
        zone_use: result.land_info.zone_use,
        land_info: result.land_info,
        skip_ai: true,
        cached_fire_safety: result.results['설비_소방'] || null,
      }
      const r = await api.whatIf(payload)
      setWhatIfResult(r)
    } catch (e) {
      console.error(e)
      setWhatIfLoading(false)
    }
  }

  const reset = () => {
    setValues(baseValues)
    setWhatIfOverrides(null)
    setWhatIfResult(null)
    if (debounceRef.current) clearTimeout(debounceRef.current)
  }

  const dirty = JSON.stringify(values) !== JSON.stringify(baseValues)

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-blue-100 bg-blue-50 p-4">
        <p className="text-sm font-semibold text-blue-800">What-if 시뮬레이션</p>
        <p className="text-xs text-blue-600 mt-0.5">
          슬라이더로 변수 조정 → 0.4초 후 자동 재계산. 설비·소방 AI는 기본 진단 결과 재사용.
        </p>
      </div>

      <div className="space-y-3">
        {VARIABLES.map((v) => (
          <Slider
            key={v.key}
            {...v}
            value={values[v.key] ?? 0}
            base={baseValues[v.key] ?? 0}
            onChange={(val) => updateValue(v.key, val)}
          />
        ))}
      </div>

      <div className="flex items-center justify-between">
        <button
          onClick={reset}
          disabled={!dirty}
          className="text-xs text-gray-500 hover:text-gray-700 disabled:opacity-40 underline"
        >
          기본값으로 리셋
        </button>
        {whatIfLoading && (
          <span className="text-xs text-blue-600">⟳ 재계산 중...</span>
        )}
      </div>

      <CompactResult result={whatIfResult || (dirty ? null : result)} base={result} />
    </div>
  )
}

function Slider({ label, unit, min, max, step, value, base, onChange }) {
  const changed = value !== base
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <label className="text-xs font-medium text-gray-700">{label}</label>
        <div className="text-xs">
          <span className={`font-bold ${changed ? 'text-blue-700' : 'text-gray-800'}`}>
            {value} {unit}
          </span>
          {changed && (
            <span className="text-gray-400 ml-1.5">(기본 {base})</span>
          )}
        </div>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full accent-blue-600"
      />
    </div>
  )
}

function CompactResult({ result, base }) {
  if (!result) {
    return (
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-xs text-gray-400 text-center">
        슬라이더를 움직이면 재계산 결과가 표시됩니다.
      </div>
    )
  }

  const sig = SIGNAL_CFG[result.signal] || SIGNAL_CFG.YELLOW
  const baseScore = base?.overall_score
  const diff = baseScore != null && result.overall_score != null
    ? result.overall_score - baseScore
    : null

  return (
    <div className="rounded-xl border-2 border-blue-200 bg-white p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className={`text-lg font-bold ${sig.cls}`}>
          {sig.dot} {sig.label}
        </p>
        {result.overall_score != null && (
          <div className="text-right">
            <p className="text-2xl font-bold text-gray-800">
              {result.overall_score.toFixed(1)}
              <span className="text-sm text-gray-400">/10</span>
            </p>
            {diff != null && diff !== 0 && (
              <p className={`text-xs font-medium ${diff > 0 ? 'text-green-600' : 'text-red-600'}`}>
                {diff > 0 ? '▲' : '▼'} {Math.abs(diff).toFixed(1)} (기본 대비)
              </p>
            )}
          </div>
        )}
      </div>

      {result.risks?.length > 0 && (
        <div className="text-xs space-y-1">
          <p className="font-semibold text-red-700">위험 항목 ({result.risks.length}건)</p>
          {result.risks.map((r, i) => (
            <p key={i} className="text-red-600">
              <span className="font-medium">{r.category}:</span> {r.reason}
            </p>
          ))}
        </div>
      )}

      {/* 카테고리별 간이 표 */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        {Object.entries(result.results || {}).map(([key, cat]) => (
          <MiniRow key={key} label={key.replace('_', '·')} cat={cat} />
        ))}
      </div>
    </div>
  )
}

function MiniRow({ label, cat }) {
  const passed = cat.pass
  const badge =
    passed === false ? { cls: 'bg-red-100 text-red-700', txt: '✗' } :
    passed === true ? { cls: 'bg-green-100 text-green-700', txt: '✓' } :
    { cls: 'bg-yellow-100 text-yellow-700', txt: '?' }
  return (
    <div className="flex items-center gap-2 py-1 border-b border-gray-100">
      <span className={`px-1.5 rounded text-[10px] font-bold ${badge.cls}`}>{badge.txt}</span>
      <span className="text-gray-700 flex-1">{label}</span>
      <span className="text-gray-500 font-medium">
        {cat.score != null ? `${cat.score}/10` : '–'}
      </span>
    </div>
  )
}

function buildBasePayload(fd) {
  const isApartment = fd.building_use === '공동주택'
  return {
    address: fd.address,
    pnu: fd.pnu || undefined,
    building_use: fd.building_use,
    site_area: parseFloat(fd.site_area),
    building_area: parseFloat(fd.building_area),
    total_floor_area: parseFloat(fd.total_floor_area),
    floors_above: parseInt(fd.floors_above, 10),
    floors_below: parseInt(fd.floors_below || '0', 10),
    height: parseFloat(fd.height),
    ...(fd.road_width ? { road_width: parseFloat(fd.road_width) } : {}),
    ...(fd.landscape_area ? { landscape_area: parseFloat(fd.landscape_area) } : {}),
    ...(isApartment && fd.units ? { units: parseInt(fd.units, 10) } : {}),
  }
}

function extractBase(fd) {
  return {
    building_area: parseFloat(fd.building_area) || 0,
    total_floor_area: parseFloat(fd.total_floor_area) || 0,
    floors_above: parseInt(fd.floors_above, 10) || 1,
    floors_below: parseInt(fd.floors_below || '0', 10),
    height: parseFloat(fd.height) || 0,
    landscape_area: parseFloat(fd.landscape_area) || 0,
  }
}

import { useEffect, useMemo, useRef, useState } from 'react'
import { useDiagnoseStore } from '../../stores/diagnoseStore'
import { api } from '../../utils/api'

/**
 * What-if 시나리오 패널.
 *
 * 진단 완료 후 마운트되어 핵심 변수(건축면적·연면적·높이·층수·주차수)를
 * 슬라이더로 조정하면 300ms debounce 후 /api/diagnose/whatif 호출 →
 * 진단 결과(8개 카드) 즉시 갱신.
 *
 * 설계 — 외과적 변경:
 *   - 원본 진단 결과는 컴포넌트 내부에 백업 (originalResultRef).
 *   - 슬라이더 변경 시 store.result 만 덮어쓰고 formData 는 그대로 둔다.
 *   - 리셋 버튼이 원본 결과를 store.result 로 복원.
 */

const SLIDERS = [
  { key: 'building_area',   label: '건축면적',     unit: '㎡', step: 1, range: 0.5 },
  { key: 'floor_area_above', label: '지상 연면적',  unit: '㎡', step: 1, range: 0.5 },
  { key: 'height',          label: '건물 높이',    unit: 'm',  step: 0.5, range: 0.5 },
  { key: 'floors_above',    label: '지상 층수',    unit: '층', step: 1, range: 0.5, integer: true },
  { key: 'provided_parking_spaces', label: '계획 주차대수', unit: '대', step: 1, range: 0.5, integer: true, optional: true },
]

const CATEGORY_LABELS = {
  '행위제한': '행위제한',
  '도시계획시설': '도시계획시설',
  '건폐율': '건폐율',
  '용적률': '용적률',
  '높이_일조': '높이·일조',
  '주차': '주차',
  '조경': '조경',
  '설비_소방': '설비·소방',
}

const SIGNAL_LABEL = { GREEN: '✅ 적합', YELLOW: '🟡 주의', RED: '🔴 위험' }
const SIGNAL_CLS = {
  GREEN: 'text-green-700', YELLOW: 'text-yellow-700', RED: 'text-red-700',
}

export default function WhatIfPanel() {
  const result = useDiagnoseStore((s) => s.result)
  const formData = useDiagnoseStore((s) => s.formData)
  const setResult = useDiagnoseStore((s) => s.setResult)

  // 원본 result + formData 보존
  const originalResultRef = useRef(result)
  const originalFormDataRef = useRef(formData)
  const [overrides, setOverrides] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const debounceRef = useRef(null)

  // 원본 fire_safety 카드 (캐시용) — results 는 카테고리명을 키로 갖는 dict
  const cachedFireSafety = useMemo(() => {
    const orig = originalResultRef.current
    return orig?.results?.['설비_소방'] || null
  }, [])

  // base 값 — 원본 formData 기준
  const baseValues = useMemo(() => {
    const fd = originalFormDataRef.current
    return SLIDERS.reduce((acc, s) => {
      const raw = fd[s.key]
      const num = raw === '' || raw == null ? null : Number(raw)
      acc[s.key] = Number.isFinite(num) ? num : null
      return acc
    }, {})
  }, [])

  // overrides 변경 시 debounce 호출
  useEffect(() => {
    if (Object.keys(overrides).length === 0) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      runWhatif()
    }, 300)
    return () => clearTimeout(debounceRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overrides])

  const runWhatif = async () => {
    const fd = originalFormDataRef.current
    // formData → API payload 변환 (빈 문자열 → null/생략)
    const payload = {}
    Object.entries(fd).forEach(([k, v]) => {
      if (v === '' || v == null) return
      payload[k] = v
    })
    // 슬라이더 override 덮어쓰기
    Object.entries(overrides).forEach(([k, v]) => {
      payload[k] = v
    })
    // 숫자 필드 변환
    const numFields = [
      'site_area', 'building_area', 'floor_area_above', 'floor_area_below',
      'floor_area_parking_above', 'floor_area_refuge', 'floor_area_attic_refuge',
      'floors_above', 'floors_below', 'height', 'units', 'road_width',
      'landscape_area', 'provided_parking_spaces', 'public_open_space_area',
      'urban_facility_exclude_area', 'far_limit_manual_override',
      'north_setback_m', 'street_block_max_height_m',
    ]
    numFields.forEach((f) => {
      if (payload[f] !== undefined) {
        const n = Number(payload[f])
        payload[f] = Number.isFinite(n) ? n : undefined
      }
    })
    payload.cached_fire_safety = cachedFireSafety

    setLoading(true)
    setError(null)
    try {
      const newResult = await api.diagnoseWhatif(payload)
      setResult(newResult)
    } catch (e) {
      setError(e.message || 'What-if 호출 실패')
    } finally {
      setLoading(false)
    }
  }

  const handleSlider = (key, val) => {
    setOverrides((prev) => ({ ...prev, [key]: val }))
  }

  const reset = () => {
    setOverrides({})
    setResult(originalResultRef.current)
    setError(null)
  }

  const hasChanges = Object.keys(overrides).length > 0

  // 비교 데이터 — 원본 vs 현재(슬라이더 반영) result
  const comparison = useMemo(() => {
    const orig = originalResultRef.current
    if (!orig || !result || result === orig) return null

    const origRes = orig.results || {}
    const currRes = result.results || {}
    const rows = []
    Object.keys(origRes).forEach((key) => {
      const o = origRes[key]
      const c = currRes[key]
      if (!c) return
      const os = o.score
      const cs = c.score
      const op = o.pass
      const cp = c.pass
      const scoreChanged = (os != null && cs != null && Math.abs(cs - os) >= 0.05)
      const passChanged = op !== cp
      if (!scoreChanged && !passChanged) return
      rows.push({
        key,
        label: CATEGORY_LABELS[key] || key,
        origScore: os, currScore: cs,
        origPass: op, currPass: cp,
        delta: (os != null && cs != null) ? cs - os : null,
      })
    })

    return {
      origScore: orig.overall_score,
      currScore: result.overall_score,
      origSignal: orig.signal,
      currSignal: result.signal,
      signalChanged: orig.signal !== result.signal,
      overallDelta: (orig.overall_score != null && result.overall_score != null)
        ? result.overall_score - orig.overall_score
        : null,
      rows,
    }
  }, [result])

  return (
    <div className="rounded-xl border border-purple-200 bg-purple-50/50 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-purple-900">🔮 What-if 시나리오</span>
          {loading && <span className="text-xs text-purple-600">재계산 중…</span>}
        </div>
        {hasChanges && (
          <button
            onClick={reset}
            className="text-xs px-2 py-1 rounded bg-white border border-purple-300 text-purple-700 hover:bg-purple-100"
          >
            ↺ 원본 복원
          </button>
        )}
      </div>
      <p className="text-xs text-purple-700 mb-3">
        값을 조정하면 위 진단 결과가 즉시 갱신됩니다. 설비·소방 카드는 원본 결과 재사용 (AI 비용 절약).
      </p>

      {/* 원본 vs 변경 비교 매트릭스 — 변화 있을 때만 노출 */}
      {comparison && (
        <div className="mb-3 rounded-lg border border-purple-300 bg-white p-3 space-y-2">
          <p className="text-xs font-semibold text-purple-900">📊 원본 ↔ 변경 비교</p>

          {/* 종합 점수·신호 */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-purple-50 rounded p-2">
              <p className="text-[var(--font-size-2xs)] text-gray-500 mb-0.5">종합 점수</p>
              <div className="flex items-center gap-1.5">
                <span className="text-gray-500">
                  {comparison.origScore?.toFixed(1) ?? '–'}
                </span>
                <span className="text-gray-400">→</span>
                <span className="font-bold text-gray-900">
                  {comparison.currScore?.toFixed(1) ?? '–'}
                </span>
                {comparison.overallDelta != null && Math.abs(comparison.overallDelta) >= 0.05 && (
                  <span className={comparison.overallDelta > 0 ? 'text-green-600' : 'text-red-600'}>
                    ({comparison.overallDelta > 0 ? '▲' : '▼'} {Math.abs(comparison.overallDelta).toFixed(1)})
                  </span>
                )}
              </div>
            </div>
            <div className="bg-purple-50 rounded p-2">
              <p className="text-[var(--font-size-2xs)] text-gray-500 mb-0.5">종합 신호</p>
              <div className="flex items-center gap-1.5">
                <span className={`text-[var(--font-size-xs)] ${SIGNAL_CLS[comparison.origSignal] || 'text-gray-500'}`}>
                  {SIGNAL_LABEL[comparison.origSignal] || comparison.origSignal}
                </span>
                {comparison.signalChanged && (
                  <>
                    <span className="text-gray-400">→</span>
                    <span className={`text-[var(--font-size-xs)] font-bold ${SIGNAL_CLS[comparison.currSignal] || 'text-gray-500'}`}>
                      {SIGNAL_LABEL[comparison.currSignal] || comparison.currSignal}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* 카테고리별 변화 */}
          {comparison.rows.length > 0 ? (
            <div className="space-y-1 pt-1 border-t border-purple-100">
              {comparison.rows.map((r) => {
                const passChanged = r.origPass !== r.currPass
                const passMark = (p) => p === true ? '✓' : p === false ? '✗' : '?'
                const passCls = (p) => p === true ? 'text-green-600' : p === false ? 'text-red-600' : 'text-yellow-600'
                return (
                  <div key={r.key} className="flex items-center justify-between text-xs">
                    <span className="text-gray-700">{r.label}</span>
                    <div className="flex items-center gap-1.5 font-mono">
                      <span className={passCls(r.origPass)}>{passMark(r.origPass)}</span>
                      <span className="text-gray-500">{r.origScore?.toFixed(1) ?? '–'}</span>
                      <span className="text-gray-400">→</span>
                      {passChanged && <span className={passCls(r.currPass)}>{passMark(r.currPass)}</span>}
                      <span className="font-bold text-gray-900">{r.currScore?.toFixed(1) ?? '–'}</span>
                      {r.delta != null && Math.abs(r.delta) >= 0.05 && (
                        <span className={r.delta > 0 ? 'text-green-600' : 'text-red-600'}>
                          ({r.delta > 0 ? '▲' : '▼'} {Math.abs(r.delta).toFixed(1)})
                        </span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="text-[var(--font-size-2xs)] text-gray-500 italic pt-1 border-t border-purple-100">
              변경된 카테고리 점수 없음 (입력 변화가 결과에 영향 없음)
            </p>
          )}
        </div>
      )}

      <div className="space-y-3">
        {SLIDERS.map((s) => {
          const base = baseValues[s.key]
          if (base == null) {
            if (s.optional) return null
            return null
          }
          const min = s.integer ? Math.max(1, Math.floor(base * (1 - s.range)))
                                : Math.max(0, Math.round(base * (1 - s.range) * 10) / 10)
          const max = s.integer ? Math.ceil(base * (1 + s.range))
                                : Math.round(base * (1 + s.range) * 10) / 10
          const cur = overrides[s.key] ?? base
          const diff = cur - base
          const diffPct = base > 0 ? ((cur - base) / base) * 100 : 0
          return (
            <div key={s.key} className="bg-white rounded-lg p-3 border border-purple-100">
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-gray-700">{s.label}</label>
                <div className="text-xs flex items-center gap-2">
                  <span className="font-mono text-gray-900">
                    {s.integer ? Math.round(cur) : cur.toFixed(1)} {s.unit}
                  </span>
                  {Math.abs(diff) > 0.01 && (
                    <span className={diff > 0 ? 'text-orange-600' : 'text-blue-600'}>
                      ({diff > 0 ? '+' : ''}{s.integer ? Math.round(diff) : diff.toFixed(1)}, {diffPct > 0 ? '+' : ''}{diffPct.toFixed(0)}%)
                    </span>
                  )}
                </div>
              </div>
              <input
                type="range"
                min={min}
                max={max}
                step={s.integer ? 1 : s.step}
                value={cur}
                onChange={(e) => handleSlider(s.key, Number(e.target.value))}
                className="w-full accent-purple-600"
              />
              <div className="flex justify-between text-[var(--font-size-2xs)] text-gray-400 mt-0.5">
                <span>{s.integer ? min : min.toFixed(1)}</span>
                <span className="text-gray-500">기준: {s.integer ? base : base.toFixed(1)}</span>
                <span>{s.integer ? max : max.toFixed(1)}</span>
              </div>
            </div>
          )
        })}
      </div>

      {error && (
        <div className="mt-3 p-2 rounded bg-red-50 border border-red-200 text-xs text-red-700">
          {error}
        </div>
      )}
    </div>
  )
}

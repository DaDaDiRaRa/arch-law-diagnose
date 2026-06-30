/**
 * 대안 비교 (What-If) — 완화 레버를 조정하며 가능 범위가 어떻게 변하는지 실시간 비교.
 *
 * 레버: 용도 / 녹색건축 / 제로에너지 / 공개공지 / 건축협정 / 재정비촉진 / 리모델링 용이구조
 * 흐름: 레버 변경 → 즉시 재계산 → "현재 안" 카드 → "이 안 저장" → 매트릭스로 나란히 비교
 */
import { useFeasibilityStore } from '../../stores/feasibilityStore'

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

const GREEN_GRADES = [
  { v: '', label: '없음' },
  { v: '우수', label: '우수' },
  { v: '최우수', label: '최우수' },
]
const ENERGY_GRADES = [
  { v: '', label: '없음' },
  { v: '1', label: '1등급' },
  { v: '2', label: '2등급' },
  { v: '3', label: '3등급' },
  { v: '4', label: '4등급' },
  { v: '5', label: '5등급' },
]

const fmt = (v, d = 0) =>
  v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: d })

// 매트릭스 행 정의 — higherBetter: 값이 클수록 유리 (최댓값 강조)
const ROWS = [
  { key: 'far', label: '용적률 한도', unit: '%', d: 1, higherBetter: true, get: (p) => p?.far_pct },
  { key: 'cov', label: '건폐율 한도', unit: '%', d: 1, higherBetter: true, get: (p) => p?.max_building_coverage_pct },
  { key: 'floor', label: '가능 연면적', unit: '㎡', d: 0, higherBetter: true, get: (p) => p?.max_floor_area_sqm },
  { key: 'parking', label: '권장 주차', unit: '대', d: 0, higherBetter: false, get: (p) => p?.recommended_parking_spaces },
]

export default function FeasibilityWhatIf() {
  const {
    whatifOpen, whatifLevers, whatifResult, whatifLoading, whatifError,
    setLever, saveAlternative, alternatives, removeAlternative, clearAlternatives,
  } = useFeasibilityStore()

  if (!whatifOpen) return null

  const L = whatifLevers
  const p = whatifResult?.proposal
  const verdict = whatifResult?.overall_recommendation?.verdict
  const reviewCount = whatifResult?.review_burden?.count_required

  // 매트릭스 컬럼: 저장된 대안들 + 맨 끝 "현재 안"
  const columns = [
    ...alternatives.map((a) => ({
      id: a.id,
      label: a.label,
      proposal: a.proposal,
      review_count: a.review_count,
      saved: true,
    })),
    {
      id: 'current',
      label: '현재 안',
      proposal: p,
      review_count: reviewCount,
      saved: false,
    },
  ]

  // 행별 최적값 (강조용)
  const bestByRow = {}
  ROWS.forEach((r) => {
    const vals = columns
      .map((c) => r.get(c.proposal))
      .filter((v) => v != null)
    if (vals.length) {
      bestByRow[r.key] = r.higherBetter ? Math.max(...vals) : Math.min(...vals)
    }
  })

  return (
    <section
      className="border-2 p-5"
      style={{ borderColor: 'var(--brand)', borderRadius: 'var(--radius)' }}
    >
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-sm font-bold" style={{ color: 'var(--ink)' }}>대안 비교 (What-If)</h3>
        {whatifLoading && (
          <span className="text-[11px] flex items-center gap-1" style={{ color: 'var(--faint)' }}>
            <span className="inline-block w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: 'var(--brand)' }} />
            계산 중…
          </span>
        )}
      </div>
      <p className="text-[11px] mb-4" style={{ color: 'var(--mute)' }}>
        완화 옵션·용도를 바꾸면 가능 범위가 즉시 다시 계산됩니다. 마음에 드는 조합은 저장해 나란히 비교하세요.
      </p>

      {/* 레버 패널 */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
        <LeverSelect
          label="시설 용도"
          value={L.facility_use}
          onChange={(v) => setLever({ facility_use: v })}
          options={[{ v: '', label: '— 선택 —' }, ...FACILITY_USES.map((u) => ({ v: u, label: u }))]}
        />
        <LeverSelect
          label="녹색건축 인증"
          value={L.green_grade}
          onChange={(v) => setLever({ green_grade: v })}
          options={GREEN_GRADES}
        />
        <LeverSelect
          label="제로에너지 등급"
          value={L.energy_grade}
          onChange={(v) => setLever({ energy_grade: v })}
          options={ENERGY_GRADES}
        />
        <div>
          <label className="block text-[11px] mb-1" style={{ color: 'var(--body)' }}>공개공지 (㎡)</label>
          <input
            type="number"
            step="0.01"
            value={L.target_open_space_sqm}
            onChange={(e) => setLever({ target_open_space_sqm: e.target.value })}
            placeholder="㎡"
            className="w-full text-xs border rounded px-2 py-1.5"
            style={{ borderColor: 'var(--hairline)' }}
          />
        </div>
        <div className="col-span-2 md:col-span-3 flex flex-wrap gap-x-5 gap-y-2 pt-1">
          <LeverToggle label="건축협정" checked={L.building_agreement} onChange={(v) => setLever({ building_agreement: v })} />
          <LeverToggle label="재정비촉진지구" checked={L.rema_zone} onChange={(v) => setLever({ rema_zone: v })} />
          <LeverToggle label="리모델링 용이구조" hint="공동주택" checked={L.easy_remodel} onChange={(v) => setLever({ easy_remodel: v })} />
        </div>
      </div>

      {whatifError && (
        <div
          className="text-xs px-3 py-2 rounded mb-3"
          style={{
            color: 'var(--error)',
            background: 'var(--canvas-elevated)',
            borderLeft: '3px solid var(--error)',
            border: '1px solid var(--hairline)',
          }}
        >
          {whatifError}
        </div>
      )}

      {/* 현재 안 요약 + 저장 */}
      <div
        className="border p-3 mb-4"
        style={{
          background: 'var(--canvas-inset)',
          borderColor: 'var(--hairline)',
          borderRadius: 'var(--radius-sm)',
        }}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-semibold" style={{ color: 'var(--body)' }}>
            현재 안 {verdict ? `· ${verdict}` : ''}
          </span>
          <button
            onClick={() => saveAlternative()}
            disabled={!p}
            className="text-[11px] font-semibold text-white rounded px-3 py-1 disabled:opacity-40"
            style={{ backgroundColor: 'var(--brand)' }}
          >
            + 이 안 저장
          </button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {ROWS.map((r) => (
            <div
              key={r.key}
              className="text-center border rounded py-2"
              style={{ background: 'var(--canvas-elevated)', borderColor: 'var(--hairline)' }}
            >
              <div className="text-[10px]" style={{ color: 'var(--mute)' }}>{r.label}</div>
              <div className="text-sm font-bold" style={{ color: 'var(--ink)' }}>
                {fmt(r.get(p), r.d)}{r.get(p) != null ? r.unit : ''}
              </div>
            </div>
          ))}
        </div>
        {p?.applied_relief_items?.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {p.applied_relief_items.map((it, i) => (
              <span
                key={i}
                className="text-[10px] px-2 py-0.5"
                style={{
                  backgroundColor: 'rgba(22,163,74,0.1)',
                  color: 'var(--ok)',
                  borderRadius: 'var(--radius-pill)',
                  border: '1px solid var(--hairline)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '10px',
                }}
              >
                {it.label || it.kind}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 비교 매트릭스 */}
      {alternatives.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-semibold" style={{ color: 'var(--body)' }}>
              저장된 대안 비교 ({alternatives.length})
            </span>
            <button
              onClick={clearAlternatives}
              className="text-[10px]"
              style={{ color: 'var(--faint)' }}
            >
              전체 삭제
            </button>
          </div>
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
                  {columns.map((c) => (
                    <th
                      key={c.id}
                      className="px-2 py-1.5 text-center min-w-[88px]"
                      style={{ borderBottom: '1px solid var(--hairline)' }}
                    >
                      <div className="flex items-center justify-center gap-1">
                        <span
                          className={c.saved ? 'font-semibold' : 'font-bold'}
                          style={c.saved ? { color: 'var(--body)' } : { color: 'var(--brand)' }}
                        >
                          {c.label}
                        </span>
                        {c.saved && (
                          <button
                            onClick={() => removeAlternative(c.id)}
                            className="leading-none"
                            style={{ color: 'var(--hairline)' }}
                            title="삭제"
                          >×</button>
                        )}
                      </div>
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
                    {columns.map((c) => {
                      const val = r.get(c.proposal)
                      const isBest = val != null && val === bestByRow[r.key] && columns.length > 1
                      return (
                        <td
                          key={c.id}
                          className="px-2 py-1.5 text-center"
                          style={
                            isBest
                              ? { color: 'var(--ok)', fontWeight: 700, borderBottom: '1px solid var(--hairline-soft)' }
                              : { color: 'var(--ink)', borderBottom: '1px solid var(--hairline-soft)' }
                          }
                        >
                          {fmt(val, r.d)}{val != null ? r.unit : ''}
                        </td>
                      )
                    })}
                  </tr>
                ))}
                <tr>
                  <td
                    className="px-2 py-1.5"
                    style={{ color: 'var(--body)', borderBottom: '1px solid var(--hairline-soft)' }}
                  >
                    심의 필수
                  </td>
                  {columns.map((c) => (
                    <td
                      key={c.id}
                      className="px-2 py-1.5 text-center"
                      style={{ color: 'var(--body)', borderBottom: '1px solid var(--hairline-soft)' }}
                    >
                      {c.review_count != null ? `${c.review_count}건` : '—'}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-[10px] mt-2" style={{ color: 'var(--faint)' }}>
            초록색 = 항목별 가장 유리한 값 (용적률·건폐율·연면적은 클수록, 주차는 적을수록).
          </p>
        </div>
      )}
    </section>
  )
}

function LeverSelect({ label, value, onChange, options }) {
  return (
    <div>
      <label className="block text-[11px] mb-1" style={{ color: 'var(--body)' }}>{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full text-xs border rounded px-2 py-1.5"
        style={{ borderColor: 'var(--hairline)' }}
      >
        {options.map((o) => (
          <option key={o.v} value={o.v}>{o.label}</option>
        ))}
      </select>
    </div>
  )
}

function LeverToggle({ label, hint, checked, onChange }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <input
        type="checkbox"
        checked={!!checked}
        onChange={(e) => onChange(e.target.checked)}
        className="rounded"
      />
      <span className="text-xs" style={{ color: 'var(--body)' }}>
        {label}
        {hint && <span className="text-[10px] ml-1" style={{ color: 'var(--faint)' }}>({hint})</span>}
      </span>
    </label>
  )
}

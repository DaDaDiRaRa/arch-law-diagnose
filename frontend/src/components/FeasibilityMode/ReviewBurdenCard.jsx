/**
 * 심의·평가 부담 카드 — Option A (항목만, 개월수 X).
 *
 * REQUIRED 항목과 MAYBE 항목을 분리 표시.
 * 일정 추정은 시니어 검토 영역으로 명시.
 */
export default function ReviewBurdenCard({ reviewBurden }) {
  if (!reviewBurden) return null
  const { required = [], maybe = [], count_required = 0, count_maybe = 0 } = reviewBurden

  if (count_required === 0 && count_maybe === 0) {
    return (
      <div
        className="border p-4"
        style={{
          borderColor: 'var(--hairline)',
          borderRadius: 'var(--radius-sm)',
          background: 'var(--canvas-elevated)',
        }}
      >
        <h4 className="text-sm font-semibold mb-2" style={{ color: 'var(--ink)' }}>심의·평가 부담</h4>
        <p className="text-xs" style={{ color: 'var(--mute)' }}>자동 트리거된 추가 심의·평가 없음.</p>
      </div>
    )
  }

  return (
    <div
      className="border p-4 space-y-3"
      style={{
        borderColor: 'var(--hairline)',
        borderRadius: 'var(--radius-sm)',
        background: 'var(--canvas-elevated)',
      }}
    >
      <div className="flex items-baseline justify-between">
        <h4 className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>심의·평가 부담</h4>
        <span className="text-[10px]" style={{ color: 'var(--mute)' }}>
          일정 추정은 시니어 확인 필요
        </span>
      </div>

      {required.length > 0 && (
        <div>
          <div className="text-xs font-medium mb-1.5 flex items-center gap-1.5" style={{ color: 'var(--body)' }}>
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: 'var(--error)' }}
            />
            필수 ({count_required})
          </div>
          <ul className="space-y-1.5">
            {required.map((item, idx) => (
              <BurdenRow key={idx} item={item} severity="required" />
            ))}
          </ul>
        </div>
      )}

      {maybe.length > 0 && (
        <div
          className={required.length > 0 ? 'pt-2' : ''}
          style={required.length > 0 ? { borderTop: '1px solid var(--hairline)' } : {}}
        >
          <div className="text-xs font-medium mb-1.5 flex items-center gap-1.5" style={{ color: 'var(--body)' }}>
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: 'var(--warn)' }}
            />
            조건부 ({count_maybe})
          </div>
          <ul className="space-y-1.5">
            {maybe.map((item, idx) => (
              <BurdenRow key={idx} item={item} severity="maybe" />
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function BurdenRow({ item, severity }) {
  const dotColor = severity === 'required' ? 'var(--error)' : 'var(--warn)'
  return (
    <li className="flex items-start gap-2 text-xs">
      <span
        className="inline-block w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0"
        style={{ backgroundColor: dotColor }}
      />
      <div className="flex-1 min-w-0">
        <div className="font-medium" style={{ color: 'var(--ink)' }}>{item.name}</div>
        {item.reason && (
          <div className="text-[11px] mt-0.5" style={{ color: 'var(--body)' }}>{item.reason}</div>
        )}
        {item.law_ref && (
          <div className="text-[10px] mt-0.5" style={{ color: 'var(--mute)' }}>{item.law_ref}</div>
        )}
      </div>
    </li>
  )
}

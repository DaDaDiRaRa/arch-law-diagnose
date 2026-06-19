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
      <div className="border border-gray-200 rounded-lg p-4 bg-white">
        <h4 className="text-sm font-semibold text-gray-800 mb-2">심의·평가 부담</h4>
        <p className="text-xs text-gray-500">자동 트리거된 추가 심의·평가 없음.</p>
      </div>
    )
  }

  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white space-y-3">
      <div className="flex items-baseline justify-between">
        <h4 className="text-sm font-semibold text-gray-800">심의·평가 부담</h4>
        <span className="text-[10px] text-gray-500">
          일정 추정은 시니어 확인 필요
        </span>
      </div>

      {required.length > 0 && (
        <div>
          <div className="text-xs font-medium text-gray-700 mb-1.5 flex items-center gap-1.5">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: 'var(--color-danger)' }}
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
        <div className={required.length > 0 ? 'pt-2 border-t border-gray-200' : ''}>
          <div className="text-xs font-medium text-gray-700 mb-1.5 flex items-center gap-1.5">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: 'var(--color-warning)' }}
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
  const dotColor =
    severity === 'required' ? 'var(--color-danger)' : 'var(--color-warning)'
  return (
    <li className="flex items-start gap-2 text-xs">
      <span
        className="inline-block w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0"
        style={{ backgroundColor: dotColor }}
      />
      <div className="flex-1 min-w-0">
        <div className="font-medium text-gray-800">{item.name}</div>
        {item.reason && (
          <div className="text-[11px] text-gray-600 mt-0.5">{item.reason}</div>
        )}
        {item.law_ref && (
          <div className="text-[10px] text-gray-400 mt-0.5">{item.law_ref}</div>
        )}
      </div>
    </li>
  )
}

import { useState } from 'react'
import { api } from '../../utils/api'

export default function ReviewRequestButton({ context }) {
  const [open, setOpen] = useState(false)
  const [requester, setRequester] = useState('')
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const submit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const r = await api.requestReview({
        address: context.address,
        risk_category: context.risk_category,
        risk_reason: context.risk_reason,
        requester: requester.trim() || undefined,
        note: note.trim() || undefined,
        building_info: context.building_info,
        signal: context.signal,
        overall_score: context.overall_score,
      })
      setResult(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const reset = () => {
    setOpen(false)
    setRequester('')
    setNote('')
    setResult(null)
    setError(null)
  }

  if (result) {
    return (
      <div className="mt-2 text-xs">
        <span className="text-green-700">
          ✓ {result.channel === 'slack' ? 'Slack 발송 완료' : '로그 기록 완료'}
        </span>
        <button onClick={reset} className="ml-2 text-gray-500 underline">
          닫기
        </button>
      </div>
    )
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="text-[11px] px-2 py-0.5 rounded bg-red-100 hover:bg-red-200 text-red-700 font-medium"
        title="시니어에게 검토 요청 (Slack/로그)"
      >
        🛎️ 시니어 검토 요청
      </button>
    )
  }

  return (
    <div className="mt-2 rounded-lg border border-red-200 bg-white p-3 space-y-2">
      <p className="text-xs font-semibold text-red-700">시니어 검토 요청</p>
      <input
        value={requester}
        onChange={(e) => setRequester(e.target.value)}
        placeholder="요청자 이름 또는 이메일 (선택)"
        className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-red-400"
      />
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
        placeholder="추가 메모 (선택, 예: 조례 강화 가능성 확인 요청)"
        className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-red-400"
      />
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex items-center justify-end gap-2">
        <button
          onClick={reset}
          className="text-xs text-gray-500 hover:text-gray-700"
        >
          취소
        </button>
        <button
          onClick={submit}
          disabled={submitting}
          className="px-3 py-1.5 bg-red-600 hover:bg-red-700 disabled:bg-gray-300 text-white text-xs font-semibold rounded"
        >
          {submitting ? '발송 중...' : '요청 발송'}
        </button>
      </div>
    </div>
  )
}

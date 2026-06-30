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
        <span style={{color:'var(--ok)'}}>
          ✓ {result.channel === 'slack' ? 'Slack 발송 완료' : '로그 기록 완료'}
        </span>
        <button onClick={reset} className="ml-2 underline" style={{color:'var(--mute)'}}>닫기</button>
      </div>
    )
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="text-xs px-2 py-0.5 font-medium"
        style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:'var(--error)',backgroundColor:'var(--canvas)',fontFamily:'var(--font-sans)'}}
        title="시니어에게 검토 요청 (Slack/로그)"
      >
        시니어 검토 요청
      </button>
    )
  }

  return (
    <div className="mt-2 p-3 space-y-2" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--error)',backgroundColor:'var(--canvas-elevated)'}}>
      <p className="text-xs font-semibold" style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}}>시니어 검토 요청</p>
      <input
        value={requester}
        onChange={(e) => setRequester(e.target.value)}
        placeholder="요청자 이름 또는 이메일 (선택)"
        className="w-full px-2 py-1.5 text-xs focus:outline-none"
        style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius-sm)',backgroundColor:'var(--canvas-elevated)',color:'var(--ink)',fontFamily:'var(--font-sans)'}}
      />
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
        placeholder="추가 메모 (선택, 예: 조례 강화 가능성 확인 요청)"
        className="w-full px-2 py-1.5 text-xs focus:outline-none"
        style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius-sm)',backgroundColor:'var(--canvas-elevated)',color:'var(--ink)',fontFamily:'var(--font-sans)'}}
      />
      {error && <p className="text-xs" style={{color:'var(--error)'}}>{error}</p>}
      <div className="flex items-center justify-end gap-2">
        <button onClick={reset} className="text-xs" style={{color:'var(--mute)'}}>취소</button>
        <button
          onClick={submit}
          disabled={submitting}
          className="px-3 py-1.5 text-xs font-semibold"
          style={{borderRadius:'var(--radius-sm)',backgroundColor:'var(--error)',color:'#fff',opacity:submitting?0.5:1,cursor:submitting?'not-allowed':'pointer',fontFamily:'var(--font-sans)'}}
        >
          {submitting ? '발송 중...' : '요청 발송'}
        </button>
      </div>
    </div>
  )
}

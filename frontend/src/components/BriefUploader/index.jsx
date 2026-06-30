import { useRef, useState } from 'react'

const FIELD_LABELS = {
  max_bcr_pct: '건폐율 한도 (%)',
  max_far_pct: '용적률 한도 (%)',
  max_floors: '최고 층수',
  max_height_m: '최고 높이 (m)',
  min_landscape_pct: '조경 최소 비율 (%)',
  min_parking_spaces: '주차 최소 대수',
  required_uses: '의무 도입 용도',
  prohibited_uses: '금지 용도',
  special_conditions: '기타 조건',
}

export default function BriefUploader({ onExtracted }) {
  const fileRef = useRef(null)
  const [status, setStatus] = useState('idle')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [fileName, setFileName] = useState(null)

  const handleFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('PDF 파일만 업로드 가능합니다.')
      return
    }

    setFileName(file.name)
    setStatus('loading')
    setError(null)
    setResult(null)

    const form = new FormData()
    form.append('file', file)

    try {
      const res = await fetch('/api/brief/extract', { method: 'POST', body: form })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `서버 오류 (${res.status})`)
      }
      const data = await res.json()
      setResult(data)
      setStatus('done')
      onExtracted?.(data)
    } catch (err) {
      setError(err.message)
      setStatus('error')
    } finally {
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const handleReset = () => {
    setStatus('idle')
    setResult(null)
    setError(null)
    setFileName(null)
    onExtracted?.(null)
  }

  const hasNumericResult = result && Object.entries(result).some(
    ([k, v]) => FIELD_LABELS[k] && v !== null && !Array.isArray(v)
  )

  return (
    <div className="p-3 space-y-2" style={{borderRadius:'var(--radius-sm)',border:'2px dashed var(--hairline)',backgroundColor:'var(--canvas)'}}>
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>발주처 지침서 PDF 업로드</p>
        {status === 'done' && (
          <button type="button" onClick={handleReset} className="text-[10px] underline" style={{color:'var(--faint)'}}>
            초기화
          </button>
        )}
      </div>

      {status === 'idle' || status === 'error' ? (
        <div>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="px-3 py-1.5 text-xs transition-colors" style={{borderRadius:'var(--radius-sm)',backgroundColor:'var(--brand)',color:'#fff',fontFamily:'var(--font-sans)'}}>
              파일 선택
            </span>
            <span className="text-xs" style={{color:'var(--mute)'}}>건폐율·용적률·높이 등 자동 추출</span>
            <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={handleFile} />
          </label>
          {error && <p className="mt-1 text-xs" style={{color:'var(--error)'}}>{error}</p>}
        </div>
      ) : status === 'loading' ? (
        <div className="flex items-center gap-2 text-xs" style={{color:'var(--mute)'}}>
          <div style={{width:14,height:14,border:'2px solid var(--hairline)',borderTopColor:'var(--brand)',borderRadius:'50%',animation:'spin 0.8s linear infinite',flexShrink:0}} />
          <span>{fileName} 분석 중...</span>
        </div>
      ) : (
        <div className="space-y-1.5">
          <p className="text-[10px] font-medium" style={{color:'var(--ok)'}}>
            {fileName} 추출 완료 — 아래 조건이 진단에 반영됩니다
          </p>

          {hasNumericResult && (
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
              {Object.entries(FIELD_LABELS).map(([key, label]) => {
                const val = result[key]
                if (val === null || val === undefined || Array.isArray(val)) return null
                return (
                  <div key={key} className="flex justify-between text-[10px]">
                    <span style={{color:'var(--mute)'}}>{label}</span>
                    <span className="font-semibold" style={{color:'var(--ink)',fontFamily:'var(--font-mono)'}}>{val}</span>
                  </div>
                )
              })}
            </div>
          )}

          {result.required_uses?.length > 0 && (
            <p className="text-[10px]" style={{color:'var(--body)'}}>
              <span className="font-medium" style={{color:'var(--ink)'}}>의무 용도:</span> {result.required_uses.join(', ')}
            </p>
          )}
          {result.prohibited_uses?.length > 0 && (
            <p className="text-[10px]" style={{color:'var(--body)'}}>
              <span className="font-medium" style={{color:'var(--ink)'}}>금지 용도:</span> {result.prohibited_uses.join(', ')}
            </p>
          )}

          {result.special_conditions?.length > 0 && (
            <div className="text-[10px]" style={{color:'var(--body)'}}>
              <span className="font-medium" style={{color:'var(--ink)'}}>기타 조건:</span>
              <ul className="list-disc list-inside">
                {result.special_conditions.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}

          {result.source_excerpt && (
            <details className="text-[10px]" style={{color:'var(--mute)'}}>
              <summary className="cursor-pointer hover:underline">추출 근거 원문</summary>
              <p className="mt-1 whitespace-pre-wrap p-1.5" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas-elevated)',color:'var(--body)',fontFamily:'var(--font-mono)'}}>
                {result.source_excerpt}
              </p>
            </details>
          )}
        </div>
      )}
    </div>
  )
}

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
  const [status, setStatus] = useState('idle') // idle | loading | done | error
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
      // 동일 파일 재업로드 허용
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
    <div className="border border-dashed border-blue-300 rounded-lg p-3 bg-blue-50 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-blue-700">발주처 지침서 PDF 업로드</p>
        {status === 'done' && (
          <button
            type="button"
            onClick={handleReset}
            className="text-[10px] text-gray-400 hover:text-gray-600 underline"
          >
            초기화
          </button>
        )}
      </div>

      {status === 'idle' || status === 'error' ? (
        <div>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition-colors">
              파일 선택
            </span>
            <span className="text-xs text-gray-500">건폐율·용적률·높이 등 자동 추출</span>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={handleFile}
            />
          </label>
          {error && (
            <p className="mt-1 text-xs text-red-600">{error}</p>
          )}
        </div>
      ) : status === 'loading' ? (
        <div className="flex items-center gap-2 text-xs text-blue-600">
          <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <span>{fileName} 분석 중...</span>
        </div>
      ) : (
        <div className="space-y-1.5">
          <p className="text-[10px] text-green-700 font-medium">✅ {fileName} 추출 완료 — 아래 조건이 진단에 반영됩니다</p>

          {/* 수치 조건 */}
          {hasNumericResult && (
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
              {Object.entries(FIELD_LABELS).map(([key, label]) => {
                const val = result[key]
                if (val === null || val === undefined || Array.isArray(val)) return null
                return (
                  <div key={key} className="flex justify-between text-[10px]">
                    <span className="text-gray-500">{label}</span>
                    <span className="font-semibold text-blue-800">{val}</span>
                  </div>
                )
              })}
            </div>
          )}

          {/* 용도 목록 */}
          {result.required_uses?.length > 0 && (
            <p className="text-[10px] text-gray-700">
              <span className="font-medium">의무 용도:</span> {result.required_uses.join(', ')}
            </p>
          )}
          {result.prohibited_uses?.length > 0 && (
            <p className="text-[10px] text-gray-700">
              <span className="font-medium">금지 용도:</span> {result.prohibited_uses.join(', ')}
            </p>
          )}

          {/* 기타 조건 */}
          {result.special_conditions?.length > 0 && (
            <div className="text-[10px] text-gray-700">
              <span className="font-medium">기타 조건:</span>
              <ul className="list-disc list-inside">
                {result.special_conditions.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}

          {/* 추출 근거 */}
          {result.source_excerpt && (
            <details className="text-[10px] text-gray-500">
              <summary className="cursor-pointer hover:text-gray-700">추출 근거 원문</summary>
              <p className="mt-1 whitespace-pre-wrap bg-white border border-gray-200 rounded p-1.5">
                {result.source_excerpt}
              </p>
            </details>
          )}
        </div>
      )}
    </div>
  )
}

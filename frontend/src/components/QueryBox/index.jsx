import { useState } from 'react'
import { useDiagnoseStore } from '../../stores/diagnoseStore'
import { api } from '../../utils/api'

const SUGGESTIONS = [
  '이 대지에 근생 6층 지으면 주차 몇 대 필요해?',
  '용적률 한도 안에서 최대 몇 ㎡까지 지을 수 있어?',
  '일조권 사선 적용 대상인지 확인해줘',
  '조경 의무비율을 어떻게 줄일 수 있어?',
]

const CONFIDENCE_CFG = {
  high:   { label: '신뢰도 높음', cls: 'bg-green-100 text-green-700' },
  medium: { label: '신뢰도 보통', cls: 'bg-yellow-100 text-yellow-700' },
  low:    { label: '신뢰도 낮음', cls: 'bg-gray-100 text-gray-700' },
}

export default function QueryBox() {
  const { formData, result } = useDiagnoseStore()
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])

  const submit = async (q) => {
    const text = (q ?? question).trim()
    if (!text) return
    setLoading(true)
    setError(null)
    try {
      const payload = {
        question: text,
        address: formData.address || undefined,
        zone_use: result?.land_info?.zone_use || undefined,
        building_info: buildBuildingInfo(formData),
        current_result: result || undefined,
      }
      const r = await api.query(payload)
      setAnswer(r)
      setQuestion('')
      setHistory((h) => [{ q: text, a: r, ts: Date.now() }, ...h].slice(0, 5))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const onKey = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit()
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-4">
        <p className="text-sm font-semibold text-emerald-800">자연어 질의 (AI 컨설팅)</p>
        <p className="text-xs text-emerald-600 mt-0.5">
          현재 진단 컨텍스트(주소·용도지역·시나리오)를 함께 전달하여 조문 근거가 있는 답변을 받습니다.
          {!result && ' 진단을 먼저 실행하면 더 정확한 답변을 받을 수 있습니다.'}
        </p>
      </div>

      <div className="space-y-2">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onKey}
          rows={3}
          placeholder="질문을 입력하세요 (Ctrl+Enter 로 전송)"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
        />
        <div className="flex items-center justify-between">
          <div className="flex flex-wrap gap-1.5">
            {SUGGESTIONS.map((s, i) => (
              <button
                key={i}
                onClick={() => submit(s)}
                disabled={loading}
                className="text-xs px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 text-gray-600 disabled:opacity-40"
              >
                {s}
              </button>
            ))}
          </div>
          <button
            onClick={() => submit()}
            disabled={loading || !question.trim()}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-300 text-white text-sm font-semibold rounded-lg"
          >
            {loading ? '답변 작성 중...' : '질문하기'}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {answer && <AnswerCard answer={answer} />}

      {history.length > 1 && (
        <div className="pt-4 border-t border-gray-200">
          <p className="text-xs font-semibold text-gray-500 mb-2">이전 질의 ({history.length - 1}건)</p>
          <div className="space-y-2">
            {history.slice(1).map((h, i) => (
              <details key={i} className="rounded-lg border border-gray-200 bg-gray-50 p-2">
                <summary className="text-xs font-medium text-gray-700 cursor-pointer">
                  Q. {h.q}
                </summary>
                <div className="mt-2">
                  <AnswerCard answer={h.a} compact />
                </div>
              </details>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function AnswerCard({ answer, compact }) {
  const cfg = CONFIDENCE_CFG[answer.confidence] || CONFIDENCE_CFG.medium
  return (
    <div className={`rounded-xl border-2 border-emerald-200 bg-white ${compact ? 'p-3' : 'p-5'}`}>
      <div className="flex items-start justify-between mb-2">
        <span className="text-xs font-medium text-emerald-700">💬 AI 답변</span>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cfg.cls}`}>
          {cfg.label}
        </span>
      </div>

      <p className={`text-gray-800 whitespace-pre-wrap leading-relaxed ${compact ? 'text-xs' : 'text-sm'}`}>
        {answer.answer}
      </p>

      {answer.citations?.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <p className="text-xs font-semibold text-gray-500 mb-1.5">📖 근거 조문</p>
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {answer.citations.map((c, i) => (
              c.url ? (
                <a
                  key={i}
                  href={c.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:underline"
                >
                  {c.name}
                </a>
              ) : (
                <span key={i} className="text-xs text-gray-600">{c.name}</span>
              )
            ))}
          </div>
        </div>
      )}

      {answer.follow_ups?.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <p className="text-xs font-semibold text-gray-500 mb-1">추가 검토 권장</p>
          <ul className="text-xs text-gray-600 list-disc list-inside space-y-0.5">
            {answer.follow_ups.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

function buildBuildingInfo(fd) {
  if (!fd.site_area) return undefined
  const obj = {
    building_use: fd.building_use,
    site_area: fd.site_area && `${fd.site_area}㎡`,
    building_area: fd.building_area && `${fd.building_area}㎡`,
    total_floor_area: fd.total_floor_area && `${fd.total_floor_area}㎡`,
    floors_above: fd.floors_above && `${fd.floors_above}층`,
    floors_below: fd.floors_below && `${fd.floors_below}층`,
    height: fd.height && `${fd.height}m`,
    units: fd.units && `${fd.units}세대`,
    road_width: fd.road_width && `${fd.road_width}m`,
    landscape_area: fd.landscape_area && `${fd.landscape_area}㎡`,
  }
  return Object.fromEntries(Object.entries(obj).filter(([_, v]) => v))
}

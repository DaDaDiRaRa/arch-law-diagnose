import { useState } from 'react'
import { useDiagnoseStore } from '../../stores/diagnoseStore'
import { api } from '../../utils/api'
import { graphSearchUrl } from '../../utils/graphLink'

const SUGGESTIONS = [
  '이 대지에 근생 6층 지으면 주차 몇 대 필요해?',
  '용적률 한도 안에서 최대 몇 ㎡까지 지을 수 있어?',
  '일조권 사선 적용 대상인지 확인해줘',
  '조경 의무비율을 어떻게 줄일 수 있어?',
]

const CONFIDENCE_CFG = {
  high:   { label: '신뢰도 높음', color: 'var(--ok)' },
  medium: { label: '신뢰도 보통', color: 'var(--warn-deep)' },
  low:    { label: '신뢰도 낮음', color: 'var(--mute)' },
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
      <div className="p-4" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--ok)',backgroundColor:'var(--canvas-elevated)'}}>
        <p className="text-sm font-semibold" style={{color:'var(--ink)',fontFamily:'var(--font-sans)',letterSpacing:'-0.02em'}}>자연어 질의 (AI 컨설팅)</p>
        <p className="text-xs mt-0.5" style={{color:'var(--mute)'}}>
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
          className="w-full px-3 py-2 text-sm focus:outline-none"
          style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius-sm)',backgroundColor:'var(--canvas-elevated)',color:'var(--ink)',fontFamily:'var(--font-sans)'}}
        />
        <div className="flex items-center justify-between gap-2">
          <div className="flex flex-wrap gap-1.5">
            {SUGGESTIONS.map((s, i) => (
              <button
                key={i}
                onClick={() => submit(s)}
                disabled={loading}
                className="text-xs px-2 py-1 transition-colors disabled:opacity-40"
                style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)',color:'var(--body)',fontFamily:'var(--font-sans)'}}
              >
                {s}
              </button>
            ))}
          </div>
          <button
            onClick={() => submit()}
            disabled={loading || !question.trim()}
            className="px-4 py-2 text-sm font-semibold flex-shrink-0"
            style={{borderRadius:'var(--radius-pill)',backgroundColor:'var(--brand)',color:'#fff',opacity:(loading || !question.trim())?0.4:1,cursor:(loading||!question.trim())?'not-allowed':'pointer',fontFamily:'var(--font-sans)'}}
          >
            {loading ? '답변 작성 중...' : '질문하기'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 text-sm" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--error)',backgroundColor:'var(--canvas-elevated)',color:'var(--error)'}}>
          {error}
        </div>
      )}

      {answer && <AnswerCard answer={answer} />}

      {history.length > 1 && (
        <div className="pt-4" style={{borderTop:'1px solid var(--hairline)'}}>
          <p className="text-xs font-semibold mb-2" style={{color:'var(--mute)',fontFamily:'var(--font-mono)',textTransform:'uppercase',letterSpacing:'0.06em'}}>이전 질의 ({history.length - 1}건)</p>
          <div className="space-y-2">
            {history.slice(1).map((h, i) => (
              <details key={i} className="p-2" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas)'}}>
                <summary className="text-xs font-medium cursor-pointer" style={{color:'var(--body)',fontFamily:'var(--font-sans)'}}>
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
    <div className={compact ? 'p-3' : 'p-5'} style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--ok)',backgroundColor:'var(--canvas-elevated)'}}>
      <div className="flex items-start justify-between mb-2">
        <span className="text-xs font-medium" style={{color:'var(--mute)',fontFamily:'var(--font-mono)',textTransform:'uppercase',letterSpacing:'0.06em'}}>AI 답변</span>
        <span className="text-[10px] px-1.5 py-0.5 font-medium" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:cfg.color,fontFamily:'var(--font-mono)'}}>
          {cfg.label}
        </span>
      </div>

      <p className={`whitespace-pre-wrap leading-relaxed ${compact ? 'text-xs' : 'text-sm'}`} style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}}>
        {answer.answer}
      </p>

      {answer.citations?.length > 0 && (
        <div className="mt-3 pt-3" style={{borderTop:'1px solid var(--hairline-soft)'}}>
          <p className="text-xs font-semibold mb-1.5" style={{color:'var(--mute)',fontFamily:'var(--font-mono)',textTransform:'uppercase',letterSpacing:'0.06em'}}>근거 조문</p>
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {answer.citations.map((c, i) => {
              const graphUrl = graphSearchUrl(c.name)
              return (
                <span key={i} className="inline-flex items-center gap-1">
                  {c.url ? (
                    <a href={c.url} target="_blank" rel="noopener noreferrer" className="text-xs hover:underline" style={{color:'var(--link)'}}>
                      {c.name}
                    </a>
                  ) : (
                    <span className="text-xs" style={{color:'var(--body)'}}>{c.name}</span>
                  )}
                  {graphUrl && (
                    <a href={graphUrl} target="_blank" rel="noopener noreferrer" className="hover:underline" style={{fontSize:'10px',color:'var(--faint)'}} title="법령 그래프에서 조문 원문·인용관계·지자체 비교 보기">
                      원문↗
                    </a>
                  )}
                </span>
              )
            })}
          </div>
        </div>
      )}

      {answer.follow_ups?.length > 0 && (
        <div className="mt-3 pt-3" style={{borderTop:'1px solid var(--hairline-soft)'}}>
          <p className="text-xs font-semibold mb-1" style={{color:'var(--mute)',fontFamily:'var(--font-mono)'}}>추가 검토 권장</p>
          <ul className="text-xs list-disc list-inside space-y-0.5" style={{color:'var(--body)'}}>
            {answer.follow_ups.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

function buildBuildingInfo(fd) {
  if (!fd.site_area) return undefined
  const above = parseFloat(fd.floor_area_above) || 0
  const below = parseFloat(fd.floor_area_below) || 0
  const parking = parseFloat(fd.floor_area_parking_above) || 0
  const refuge = parseFloat(fd.floor_area_refuge) || 0
  const atticRefuge = parseFloat(fd.floor_area_attic_refuge) || 0
  const totalFloor = above + below
  const obj = {
    building_use: fd.building_use,
    site_area: fd.site_area && `${fd.site_area}㎡`,
    building_area: fd.building_area && `${fd.building_area}㎡`,
    floor_area_above: above > 0 ? `${above}㎡` : '',
    floor_area_below: below > 0 ? `${below}㎡` : '',
    floor_area_parking_above: parking > 0 ? `${parking}㎡ (용적률 제외)` : '',
    floor_area_refuge: refuge > 0 ? `${refuge}㎡ (용적률 제외)` : '',
    floor_area_attic_refuge: atticRefuge > 0 ? `${atticRefuge}㎡ (용적률 제외)` : '',
    total_floor_area: totalFloor > 0 ? `${totalFloor}㎡` : '',
    floors_above: fd.floors_above && `${fd.floors_above}층`,
    floors_below: fd.floors_below && `${fd.floors_below}층`,
    height: fd.height && `${fd.height}m`,
    units: fd.units && `${fd.units}세대`,
    road_width: fd.road_width && `${fd.road_width}m`,
    landscape_area: fd.landscape_area && `${fd.landscape_area}㎡`,
  }
  return Object.fromEntries(Object.entries(obj).filter(([_, v]) => v))
}

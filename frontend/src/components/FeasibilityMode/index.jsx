import { useFeasibilityStore } from '../../stores/feasibilityStore'
import FeasibilityInputForm from './FeasibilityInputForm'
import FeasibilityResult from './FeasibilityResult'
import MultiSiteCompare from './MultiSiteCompare'

export default function FeasibilityMode({ onBack }) {
  const { result, loading, view, setView } = useFeasibilityStore()
  const showResult = !!result && view === 'single'

  return (
    <div className="max-w-screen-xl mx-auto">
      {/* 모드 헤더 */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <button onClick={onBack} className="text-xs mb-2 transition-colors" style={{color:'var(--mute)'}}>
            ← 모드 선택
          </button>
          <h2 className="text-lg font-semibold" style={{color:'var(--ink)',fontFamily:'var(--font-sans)',letterSpacing:'-0.02em'}}>
            사전 사업성 검토
          </h2>
          <p className="text-xs mt-0.5" style={{color:'var(--mute)'}}>
            이 대지의 가능 범위(건폐율·용적률·연면적·주차)를 먼저 제시 — 공모 요구치 입력 시 갭 분석까지
          </p>
        </div>
      </div>

      {/* 단일 / 다중 전환 */}
      <div className="flex gap-1 mb-4 p-1 w-fit" style={{backgroundColor:'var(--canvas)',borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)'}}>
        {[
          { k: 'single', label: '단일 검토' },
          { k: 'multi', label: '다중 대지 비교' },
        ].map((t) => (
          <button
            key={t.k}
            onClick={() => setView(t.k)}
            className="text-xs font-medium px-3 py-1.5 transition-colors"
            style={view === t.k
              ? {borderRadius:'var(--radius-sm)',backgroundColor:'var(--canvas-elevated)',color:'var(--brand)',boxShadow:'var(--shadow-sm)',fontFamily:'var(--font-sans)'}
              : {borderRadius:'var(--radius-sm)',color:'var(--mute)',fontFamily:'var(--font-sans)'}}
          >
            {t.label}
          </button>
        ))}
      </div>

      {view === 'multi' ? (
        <div className="p-6" style={{backgroundColor:'var(--canvas-elevated)',borderRadius:'var(--radius)',border:'1px solid var(--hairline)',boxShadow:'var(--shadow-sm)'}}>
          <MultiSiteCompare />
        </div>
      ) : showResult ? (
        <div className="p-6" style={{backgroundColor:'var(--canvas-elevated)',borderRadius:'var(--radius)',border:'1px solid var(--hairline)',boxShadow:'var(--shadow-sm)'}}>
          <FeasibilityResult />
        </div>
      ) : (
        <div className="p-6" style={{backgroundColor:'var(--canvas-elevated)',borderRadius:'var(--radius)',border:'1px solid var(--hairline)',boxShadow:'var(--shadow-sm)'}}>
          <FeasibilityInputForm />
        </div>
      )}

      {loading && (
        <div className="fixed inset-0 flex items-center justify-center z-50" style={{backgroundColor:'rgba(0,0,0,0.3)'}}>
          <div className="px-6 py-4" style={{backgroundColor:'var(--canvas-elevated)',borderRadius:'var(--radius)',boxShadow:'var(--shadow-md)'}}>
            <div className="flex items-center gap-3">
              <div style={{width:16,height:16,border:'2px solid var(--hairline)',borderTopColor:'var(--brand)',borderRadius:'50%',animation:'spin 0.8s linear infinite'}} />
              <div>
                <div className="text-sm font-medium" style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}}>검토 중...</div>
                <div className="text-xs mt-0.5" style={{color:'var(--mute)'}}>토지 정보 조회 + 8 카테고리 한도 산정 (5~15초)</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

import { useState, useEffect } from 'react'
import InputForm from './components/InputForm'
import DiagnoseResult from './components/DiagnoseResult'
import QueryBox from './components/QueryBox'
import FeasibilityMode from './components/FeasibilityMode'
import { useDiagnoseStore } from './stores/diagnoseStore'

const TABS = [
  { key: 'diagnose', label: '진단 결과', icon: '📋' },
  { key: 'query',    label: '자연어 질의', icon: '💬' },
]

export default function App() {
  const { result, loading, error } = useDiagnoseStore()
  const [activeTab, setActiveTab] = useState('diagnose')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [mode, setMode] = useState(null)  // null | 'verify' | 'feasibility'

  const hasOutput = result || loading || error

  useEffect(() => {
    if (loading) setDrawerOpen(false)
  }, [loading])

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 sticky top-0 z-10">
        <div className="w-full flex items-center gap-3">
          <span className="text-2xl">🏛️</span>
          <div>
            <h1 className="text-base font-bold text-gray-900 leading-tight">
              건축 법규 자동 진단
            </h1>
            <p className="text-xs text-gray-500">arch-law-diagnose · Phase 4</p>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {mode === 'verify' && hasOutput && (
              <button
                onClick={() => setDrawerOpen(true)}
                className="flex items-center gap-1.5 text-xs bg-white border border-gray-300 text-gray-700 px-3 py-1.5 rounded-lg hover:bg-gray-50 hover:border-gray-400 transition-colors shadow-sm"
              >
                ✏️ 대지정보 수정
              </button>
            )}
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full font-medium">
              사내 전용
            </span>
          </div>
        </div>
      </header>

      <main className="w-full px-6 py-6">
        {mode === null && <ModeSelector onSelect={setMode} />}

        {mode === 'feasibility' && (
          <FeasibilityMode onBack={() => setMode(null)} />
        )}

        {mode === 'verify' && (
          <VerifyMode
            hasOutput={hasOutput}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            onBack={() => setMode(null)}
          />
        )}
      </main>

      {/* 사이드 드로어 — 검증 모드 전용 */}
      {mode === 'verify' && hasOutput && (
        <>
          <div
            className={`fixed inset-0 bg-black/40 z-20 transition-opacity duration-300 ${
              drawerOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
            }`}
            onClick={() => setDrawerOpen(false)}
          />
          <div
            className={`fixed top-0 left-0 h-full w-[var(--panel-width-lg)] max-w-full bg-white shadow-2xl z-30 flex flex-col transition-transform duration-300 ${
              drawerOpen ? 'translate-x-0' : '-translate-x-full'
            }`}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gray-50 shrink-0">
              <div className="flex items-center gap-2">
                <span className="text-base">✏️</span>
                <h2 className="text-sm font-semibold text-gray-800">대지 정보 수정</h2>
              </div>
              <button
                onClick={() => setDrawerOpen(false)}
                className="text-gray-400 hover:text-gray-700 text-lg leading-none p-1 rounded hover:bg-gray-200 transition-colors"
              >
                ✕
              </button>
            </div>
            <div className="overflow-y-auto flex-1 px-6 py-5">
              <InputForm isDrawer />
            </div>
          </div>
        </>
      )}

      <footer className="text-center py-6 text-xs text-gray-400 border-t border-gray-200 mt-8">
        arch-law-diagnose v4.0 · 사내 자산 · 법규 해석은 반드시 시니어에게 확인하세요
      </footer>
    </div>
  )
}

// ── 모드 선택 화면 ──────────────────────────────────────────────────────────

function ModeSelector({ onSelect }) {
  return (
    <div className="max-w-screen-lg mx-auto py-8">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          어떤 작업을 하시나요?
        </h2>
        <p className="text-sm text-gray-500">
          공모를 막 받으셨다면 사전 사업성 · 설계안이 있으시면 검증
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ModeCard
          icon="📋"
          title="사전 사업성"
          tagline="공모 받음 — 들어갈 만한가?"
          description="공모 요구치(면적·층수·용적률 등)와 법적 가능 범위를 비교해 참여 판단을 돕습니다. 아직 설계 안 했어도 OK."
          features={[
            '갭 분석 — 공모 요구 vs 법 한계',
            '완화 시나리오 자동 추천',
            '심의·평가 부담 자동 트리거',
            '참여/협상/패스 종합 판단',
          ]}
          ctaLabel="사전 사업성 시작"
          accent="var(--color-accent)"
          onClick={() => onSelect('feasibility')}
        />
        <ModeCard
          icon="✅"
          title="설계 검증"
          tagline="설계안 있음 — 통과 여부 체크"
          description="이미 잡힌 설계안(면적·건축면적·층수 등)이 법규를 모두 통과하는지 8개 카테고리 진단. 종합점수·신호등으로 답."
          features={[
            '8 카테고리 가중평균 진단',
            'GREEN / YELLOW / RED 신호',
            'What-If — 인증 등급별 비교',
            '합필 진단 · 자연어 질의',
          ]}
          ctaLabel="설계 검증 시작"
          accent="var(--color-info)"
          onClick={() => onSelect('verify')}
        />
      </div>

      <div className="mt-6 text-[11px] text-gray-400 text-center">
        모드는 진단 화면에서 언제든 돌아가 변경 가능합니다.
      </div>
    </div>
  )
}

function ModeCard({ icon, title, tagline, description, features, ctaLabel, accent, onClick }) {
  return (
    <button
      onClick={onClick}
      className="text-left bg-white rounded-2xl border-2 border-gray-200 p-6 hover:border-gray-400 hover:shadow-lg transition-all"
    >
      <div className="flex items-start gap-3 mb-3">
        <span className="text-3xl">{icon}</span>
        <div>
          <h3 className="text-lg font-bold text-gray-900">{title}</h3>
          <p className="text-xs font-medium" style={{ color: accent }}>
            {tagline}
          </p>
        </div>
      </div>
      <p className="text-sm text-gray-600 mb-4">{description}</p>
      <ul className="space-y-1.5 mb-5">
        {features.map((f, idx) => (
          <li key={idx} className="text-xs text-gray-700 flex items-start gap-1.5">
            <span style={{ color: accent }}>·</span>
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <div
        className="text-center text-sm font-semibold py-2.5 rounded-lg text-white"
        style={{ backgroundColor: accent }}
      >
        {ctaLabel} →
      </div>
    </button>
  )
}

// ── 검증 모드 (기존 흐름) ────────────────────────────────────────────────────

function VerifyMode({ hasOutput, activeTab, setActiveTab, onBack }) {
  return (
    <div className="max-w-screen-2xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <div>
          <button
            onClick={onBack}
            className="text-xs text-gray-500 hover:text-gray-700 mb-2"
          >
            ← 모드 선택
          </button>
          <h2 className="text-lg font-bold text-gray-900">설계 검증</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            설계 안의 법규 통과 여부 — 8 카테고리 종합 진단
          </p>
        </div>
      </div>

      {!hasOutput ? (
        <>
          <div className="bg-white rounded-2xl border border-gray-200 p-8 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 mb-5">
              대지 정보 입력
            </h2>
            <InputForm />
          </div>
          <div className="mt-5 rounded-xl bg-blue-50 border border-blue-100 p-4">
            <p className="text-sm font-medium text-blue-800 mb-1">기능 안내</p>
            <ul className="text-xs text-blue-700 space-y-1 list-disc list-inside">
              <li>8개 카테고리 종합 진단 (건폐율·용적률·높이·주차·조경·설비소방·행위제한·도시계획)</li>
              <li>합필 진단 — 여러 필지 동시 진단 + 면적 안분 (국토계획법 제84조)</li>
              <li>용적률 4가지 제외 — 지하·지상주차장·피난안전구역·경사지붕 대피공간</li>
              <li>자연어 질의 — 진단 컨텍스트 기반 AI 답변 + 조문 인용</li>
              <li>법규 변경 모니터링 — SHA256 해시 비교 + 변경 배너</li>
              <li>시니어 검토 요청 버튼 (Slack/로그)</li>
            </ul>
          </div>
        </>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <nav className="flex border-b border-gray-200 bg-gray-50">
            {TABS.map((t) => {
              const active = activeTab === t.key
              return (
                <button
                  key={t.key}
                  onClick={() => setActiveTab(t.key)}
                  className={[
                    'flex-1 px-3 py-3 text-xs font-medium transition-colors border-b-2',
                    active
                      ? 'border-blue-600 text-blue-700 bg-white'
                      : 'border-transparent text-gray-500 hover:text-gray-700',
                  ].join(' ')}
                >
                  <span className="mr-1">{t.icon}</span>
                  {t.label}
                </button>
              )
            })}
          </nav>
          <div className="p-6">
            {activeTab === 'diagnose' && <DiagnoseResult />}
            {activeTab === 'query'    && <QueryBox />}
          </div>
        </div>
      )}
    </div>
  )
}

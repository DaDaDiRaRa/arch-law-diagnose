import { useState } from 'react'
import InputForm from './components/InputForm'
import DiagnoseResult from './components/DiagnoseResult'
import QueryBox from './components/QueryBox'
import { useDiagnoseStore } from './stores/diagnoseStore'

const TABS = [
  { key: 'diagnose', label: '진단 결과', icon: '📋' },
  { key: 'query',    label: '자연어 질의', icon: '💬' },
]

export default function App() {
  const { result, loading, error, formData } = useDiagnoseStore()
  const [activeTab, setActiveTab] = useState('diagnose')

  const hasOutput = result || loading || error
  const hasAddress = !!formData.address

  // 탭별 비활성 조건
  const tabDisabled = {
    diagnose: false,
    query:    false,
  }

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
          <div className="ml-auto">
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full font-medium">
              사내 전용
            </span>
          </div>
        </div>
      </header>

      <main className="w-full px-6 py-6">
        <div className={`grid gap-6 ${hasOutput || hasAddress ? 'grid-cols-1 lg:grid-cols-[400px_minmax(0,1fr)]' : 'grid-cols-1 max-w-2xl'}`}>

          {/* 입력 패널 */}
          <section>
            <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
              <h2 className="text-base font-semibold text-gray-800 mb-5">
                대지 정보 입력
              </h2>
              <InputForm />
            </div>

            {!hasOutput && (
              <div className="mt-5 rounded-xl bg-blue-50 border border-blue-100 p-4">
                <p className="text-sm font-medium text-blue-800 mb-1">기능 안내</p>
                <ul className="text-xs text-blue-700 space-y-1 list-disc list-inside">
                  <li>6개 카테고리 종합 진단 (건폐율·용적률·높이·주차·조경·설비소방)</li>
                  <li>합필 진단 — 여러 필지 동시 진단 + 면적 안분 (국토계획법 제84조)</li>
                  <li>용적률 4가지 제외 — 지하·지상주차장·피난안전구역·경사지붕 대피공간</li>
                  <li>자연어 질의 — 진단 컨텍스트 기반 AI 답변 + 조문 인용</li>
                  <li>사내 케이스 연계 (KUNWON_DB) — 유사 프로젝트 자동 매칭</li>
                  <li>법규 변경 모니터링 — SHA256 해시 비교 + 변경 배너</li>
                  <li>시니어 검토 요청 버튼 (Slack/로그)</li>
                </ul>
              </div>
            )}
          </section>

          {/* 우측 패널 — 탭 네비 */}
          {(hasOutput || hasAddress) && (
            <section>
              <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
                <nav className="flex border-b border-gray-200 bg-gray-50">
                  {TABS.map((t) => {
                    const disabled = tabDisabled[t.key]
                    const active = activeTab === t.key
                    return (
                      <button
                        key={t.key}
                        onClick={() => !disabled && setActiveTab(t.key)}
                        disabled={disabled}
                        className={[
                          'flex-1 px-3 py-3 text-xs font-medium transition-colors border-b-2',
                          active
                            ? 'border-blue-600 text-blue-700 bg-white'
                            : 'border-transparent text-gray-500 hover:text-gray-700',
                          disabled && 'opacity-40 cursor-not-allowed hover:text-gray-500',
                        ].filter(Boolean).join(' ')}
                        title={disabled ? '먼저 좌측 입력을 완료해주세요' : ''}
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
            </section>
          )}
        </div>
      </main>

      <footer className="text-center py-6 text-xs text-gray-400 border-t border-gray-200 mt-8">
        arch-law-diagnose v4.0 · 사내 자산 · 법규 해석은 반드시 시니어에게 확인하세요
      </footer>
    </div>
  )
}

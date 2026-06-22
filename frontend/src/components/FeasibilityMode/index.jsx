import { useState } from 'react'
import { useFeasibilityStore } from '../../stores/feasibilityStore'
import FeasibilityInputForm from './FeasibilityInputForm'
import FeasibilityResult from './FeasibilityResult'
import MultiSiteCompare from './MultiSiteCompare'

export default function FeasibilityMode({ onBack }) {
  const { result, loading } = useFeasibilityStore()
  const [view, setView] = useState('single') // 'single' | 'multi'
  const showResult = !!result && view === 'single'

  return (
    <div className="max-w-screen-xl mx-auto">
      {/* 모드 헤더 */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <button
            onClick={onBack}
            className="text-xs text-gray-500 hover:text-gray-700 mb-2"
          >
            ← 모드 선택
          </button>
          <h2 className="text-lg font-bold text-gray-900">
            사전 사업성 검토
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            이 대지의 가능 범위(건폐율·용적률·연면적·주차)를 먼저 제시 — 공모 요구치 입력 시 갭 분석까지
          </p>
        </div>
      </div>

      {/* 단일 / 다중 전환 */}
      <div className="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
        {[
          { k: 'single', label: '단일 검토' },
          { k: 'multi', label: '다중 대지 비교' },
        ].map((t) => (
          <button
            key={t.k}
            onClick={() => setView(t.k)}
            className="text-xs font-medium px-3 py-1.5 rounded-md transition-colors"
            style={
              view === t.k
                ? { backgroundColor: 'white', color: 'var(--color-accent)', boxShadow: '0 1px 2px rgba(0,0,0,0.06)' }
                : { color: 'var(--color-text-faint)' }
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      {view === 'multi' ? (
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <MultiSiteCompare />
        </div>
      ) : showResult ? (
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <FeasibilityResult />
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <FeasibilityInputForm />
        </div>
      )}

      {loading && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg px-6 py-4 shadow-xl">
            <div className="text-sm font-medium text-gray-800">검토 중...</div>
            <div className="text-xs text-gray-500 mt-1">
              토지 정보 조회 + 8 카테고리 한도 산정 (5~15초)
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

import { useFeasibilityStore } from '../../stores/feasibilityStore'
import FeasibilityInputForm from './FeasibilityInputForm'
import FeasibilityResult from './FeasibilityResult'

export default function FeasibilityMode({ onBack }) {
  const { result, loading } = useFeasibilityStore()
  const showResult = !!result

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
            공모 요구치와 법적 가능 범위를 비교 — 참여 판단용
          </p>
        </div>
      </div>

      {showResult ? (
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

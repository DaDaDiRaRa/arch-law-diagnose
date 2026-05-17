import { Component } from 'react'

/**
 * What-if 패널 전용 Error Boundary.
 * 슬라이더/재진단 로직에서 예외 발생해도 위 진단 결과 카드는 살아남도록 격리.
 */
export default class WhatIfErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('WhatIfPanel error:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-semibold text-red-700 mb-1">
            🔮 What-if 패널 오류
          </p>
          <p className="text-xs text-red-600">
            {this.state.error.message || '슬라이더 패널 렌더링 실패'}
          </p>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-2 text-xs px-2 py-1 rounded bg-white border border-red-300 text-red-700"
          >
            다시 시도
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

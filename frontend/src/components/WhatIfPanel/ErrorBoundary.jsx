import { Component } from 'react'

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
        <div className="mt-6 p-4" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--error)',backgroundColor:'var(--canvas-elevated)'}}>
          <p className="text-sm font-semibold mb-1" style={{color:'var(--error)',fontFamily:'var(--font-sans)'}}>
            What-if 패널 오류
          </p>
          <p className="text-xs" style={{color:'var(--error)'}}>
            {this.state.error.message || '슬라이더 패널 렌더링 실패'}
          </p>
          <button
            onClick={() => this.setState({ error: null })}
            className="mt-2 text-xs px-2 py-1"
            style={{borderRadius:'var(--radius-sm)',backgroundColor:'var(--canvas)',border:'1px solid var(--hairline)',color:'var(--body)',fontFamily:'var(--font-sans)'}}
          >
            다시 시도
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

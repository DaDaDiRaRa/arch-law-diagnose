const LEVEL_STYLE = {
  error: {
    row: 'bg-red-50 border-red-300 text-red-800',
    icon: '🔴',
  },
  warn: {
    row: 'bg-yellow-50 border-yellow-300 text-yellow-800',
    icon: '⚠️',
  },
  info: {
    row: 'bg-blue-50 border-blue-200 text-blue-700',
    icon: 'ℹ️',
  },
}

export default function DataQualityBanner({ dataQuality }) {
  if (!dataQuality) return null
  const { issues = [], ordinance_used, llm_used, luris_used, zone_use_source, land_cache_stale, land_cache_age_days } = dataQuality

  if (issues.length === 0) {
    return (
      <div className="rounded-xl border border-green-200 bg-green-50 px-4 py-2.5 flex items-center gap-2">
        <span className="text-green-600 text-sm">✅</span>
        <span className="text-xs text-green-700 font-medium">데이터 품질 양호</span>
        <span className="ml-auto text-[10px] text-green-600 flex gap-3">
          <span>VWorld ✓</span>
          {ordinance_used && <span>조례 ✓</span>}
          {llm_used && <span>AI ✓</span>}
          {luris_used && <span>LURIS ✓</span>}
        </span>
      </div>
    )
  }

  const hasError = issues.some(i => i.level === 'error')
  const wrapCls = hasError
    ? 'rounded-xl border-2 border-red-300 bg-red-50'
    : 'rounded-xl border border-yellow-300 bg-yellow-50'

  return (
    <div className={`${wrapCls} p-3 space-y-1.5`}>
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs font-semibold text-gray-700">
          {hasError ? '🔴 데이터 품질 문제' : '⚠️ 데이터 품질 주의'}
        </p>
        <DataSourcePills
          ordinance_used={ordinance_used}
          llm_used={llm_used}
          luris_used={luris_used}
          zone_use_source={zone_use_source}
          land_cache_stale={land_cache_stale}
          land_cache_age_days={land_cache_age_days}
        />
      </div>
      {issues.map((issue, i) => {
        const sty = LEVEL_STYLE[issue.level] || LEVEL_STYLE.warn
        return (
          <div key={i} className={`text-xs rounded px-2.5 py-1.5 border ${sty.row}`}>
            {sty.icon} {issue.msg}
          </div>
        )
      })}
    </div>
  )
}

function DataSourcePills({ ordinance_used, llm_used, luris_used, zone_use_source, land_cache_stale, land_cache_age_days }) {
  const pills = []

  if (zone_use_source === 'user') {
    pills.push({ label: '용도지역 수동', cls: 'bg-blue-100 text-blue-700' })
  } else if (zone_use_source === 'vworld') {
    pills.push({ label: 'VWorld ✓', cls: 'bg-green-100 text-green-700' })
  } else {
    pills.push({ label: 'VWorld ✗', cls: 'bg-red-100 text-red-700' })
  }

  if (land_cache_stale) {
    pills.push({ label: `캐시 ${land_cache_age_days}일 전`, cls: 'bg-orange-100 text-orange-700' })
  }

  pills.push({
    label: ordinance_used ? '조례 ✓' : '조례 ✗(시행령)',
    cls: ordinance_used ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700',
  })
  pills.push({
    label: llm_used ? 'AI ✓' : 'AI ✗',
    cls: llm_used ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600',
  })
  pills.push({
    label: luris_used ? 'LURIS ✓' : 'LURIS ✗',
    cls: luris_used ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600',
  })

  return (
    <div className="flex flex-wrap gap-1">
      {pills.map((p, i) => (
        <span key={i} className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${p.cls}`}>
          {p.label}
        </span>
      ))}
    </div>
  )
}

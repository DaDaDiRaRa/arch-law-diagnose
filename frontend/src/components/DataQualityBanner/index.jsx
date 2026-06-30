const LEVEL_CONFIG = {
  error: { color: 'var(--error)', dotColor: 'var(--error)' },
  warn:  { color: 'var(--warn-deep)', dotColor: 'var(--warn)' },
  info:  { color: 'var(--info)', dotColor: 'var(--info)' },
}

export default function DataQualityBanner({ dataQuality }) {
  if (!dataQuality) return null
  const { issues = [], ordinance_used, llm_used, luris_used, zone_use_source, land_cache_stale, land_cache_age_days, aggregate_confidence } = dataQuality

  if (issues.length === 0) {
    return (
      <div className="px-4 py-2.5 flex items-center gap-2" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:'3px solid var(--ok)',backgroundColor:'var(--canvas-elevated)'}}>
        <div style={{width:8,height:8,borderRadius:'50%',backgroundColor:'var(--ok)',flexShrink:0}} />
        <span className="text-xs font-medium" style={{color:'var(--ok)',fontFamily:'var(--font-sans)'}}>데이터 품질 양호</span>
        <span className="ml-auto flex items-center gap-3" style={{color:'var(--mute)'}}>
          <ConfidenceBadge value={aggregate_confidence} />
          <span className="text-[10px]" style={{fontFamily:'var(--font-mono)'}}>VWorld ✓</span>
          {ordinance_used && <span className="text-[10px]" style={{fontFamily:'var(--font-mono)'}}>조례 ✓</span>}
          {llm_used && <span className="text-[10px]" style={{fontFamily:'var(--font-mono)'}}>AI ✓</span>}
          {luris_used && <span className="text-[10px]" style={{fontFamily:'var(--font-mono)'}}>LURIS ✓</span>}
        </span>
      </div>
    )
  }

  const hasError = issues.some(i => i.level === 'error')
  const borderColor = hasError ? 'var(--error)' : 'var(--warn)'

  return (
    <div className="p-3 space-y-1.5" style={{borderRadius:'var(--radius)',border:'1px solid var(--hairline)',borderLeft:`3px solid ${borderColor}`,backgroundColor:'var(--canvas-elevated)'}}>
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs font-semibold" style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}}>
          {hasError ? '데이터 품질 문제' : '데이터 품질 주의'}
        </p>
        <DataSourcePills
          ordinance_used={ordinance_used}
          llm_used={llm_used}
          luris_used={luris_used}
          zone_use_source={zone_use_source}
          land_cache_stale={land_cache_stale}
          land_cache_age_days={land_cache_age_days}
          aggregate_confidence={aggregate_confidence}
        />
      </div>
      {issues.map((issue, i) => {
        const cfg = LEVEL_CONFIG[issue.level] || LEVEL_CONFIG.warn
        return (
          <div key={i} className="text-xs px-2.5 py-1.5 flex items-start gap-1.5" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',borderLeft:`2px solid ${cfg.color}`,backgroundColor:'var(--canvas)'}}>
            <div style={{width:6,height:6,borderRadius:'50%',backgroundColor:cfg.dotColor,flexShrink:0,marginTop:3}} />
            <span style={{color:'var(--body)'}}>{issue.msg}</span>
          </div>
        )
      })}
    </div>
  )
}

function ConfidenceBadge({ value }) {
  if (value == null) return null
  const color = value >= 4 ? 'var(--ok)' : value === 3 ? 'var(--warn-deep)' : 'var(--error)'
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 font-medium"
      style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color,fontFamily:'var(--font-mono)',cursor:'default'}}
      title="채점된 항목 중 최저 신뢰도 (1~5). 산정한 종합 점수를 얼마나 믿을 수 있는지를 나타내며, 신호 판정과는 별개입니다."
    >
      신뢰도 {value}/5
    </span>
  )
}

function DataSourcePills({ ordinance_used, llm_used, luris_used, zone_use_source, land_cache_stale, land_cache_age_days, aggregate_confidence }) {
  const pills = []

  if (zone_use_source === 'user') {
    pills.push({ label: '용도지역 수동', color: 'var(--info)' })
  } else if (zone_use_source === 'vworld') {
    pills.push({ label: 'VWorld ✓', color: 'var(--ok)' })
  } else {
    pills.push({ label: 'VWorld ✗', color: 'var(--error)' })
  }

  if (land_cache_stale) {
    pills.push({ label: `캐시 ${land_cache_age_days}일 전`, color: 'var(--warn-deep)' })
  }

  pills.push({ label: ordinance_used ? '조례 ✓' : '조례 ✗(시행령)', color: ordinance_used ? 'var(--ok)' : 'var(--warn-deep)' })
  pills.push({ label: llm_used ? 'AI ✓' : 'AI ✗', color: llm_used ? 'var(--ok)' : 'var(--mute)' })
  pills.push({ label: luris_used ? 'LURIS ✓' : 'LURIS ✗', color: luris_used ? 'var(--ok)' : 'var(--mute)' })

  return (
    <div className="flex flex-wrap gap-1">
      <ConfidenceBadge value={aggregate_confidence} />
      {pills.map((p, i) => (
        <span key={i} className="text-[10px] px-1.5 py-0.5 font-medium" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',color:p.color,fontFamily:'var(--font-mono)'}}>
          {p.label}
        </span>
      ))}
    </div>
  )
}

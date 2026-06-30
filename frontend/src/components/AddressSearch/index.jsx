import { useState, useRef, useEffect } from 'react'
import { api } from '../../utils/api'

export default function AddressSearch({ onSelect }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const timerRef = useRef(null)
  const wrapRef = useRef(null)

  useEffect(() => {
    const handler = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleChange = (e) => {
    const val = e.target.value
    setQuery(val)
    clearTimeout(timerRef.current)
    if (val.length < 2) { setResults([]); setOpen(false); return }
    timerRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const data = await api.searchAddress(val)
        setResults(data.results || [])
        setOpen(true)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 400)
  }

  const handleSelect = (item) => {
    setQuery(item.road_addr || item.jibun_addr)
    setResults([])
    setOpen(false)
    onSelect(item)
  }

  return (
    <div ref={wrapRef} className="relative">
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={handleChange}
          placeholder="도로명 또는 지번 주소 검색 (예: 영등포구 당산로 123)"
          className="w-full px-4 py-3 pr-10 text-sm focus:outline-none"
          style={{border:'1px solid var(--hairline)',borderRadius:'var(--radius-sm)',backgroundColor:'var(--canvas-elevated)',color:'var(--ink)',fontFamily:'var(--font-sans)'}}
        />
        {loading && (
          <div className="absolute right-3 top-3.5" style={{width:14,height:14,border:'2px solid var(--hairline)',borderTopColor:'var(--brand)',borderRadius:'50%',animation:'spin 0.8s linear infinite'}} />
        )}
      </div>

      {open && results.length > 0 && (
        <ul className="absolute z-20 w-full mt-1 max-h-64 overflow-y-auto" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas-elevated)',boxShadow:'var(--shadow-md)'}}>
          {results.map((item, i) => (
            <li
              key={i}
              onClick={() => handleSelect(item)}
              className="px-4 py-3 cursor-pointer transition-colors"
              style={{borderBottom:'1px solid var(--hairline-soft)'}}
              onMouseEnter={e=>e.currentTarget.style.backgroundColor='var(--canvas)'}
              onMouseLeave={e=>e.currentTarget.style.backgroundColor='transparent'}
            >
              <p className="text-sm font-medium" style={{color:'var(--ink)',fontFamily:'var(--font-sans)'}}>{item.road_addr}</p>
              <p className="text-xs mt-0.5" style={{color:'var(--mute)'}}>{item.jibun_addr}</p>
              {item.pnu && (
                <p className="text-xs" style={{color:'var(--faint)',fontFamily:'var(--font-mono)'}}>PNU: {item.pnu}</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {open && results.length === 0 && query.length >= 2 && !loading && (
        <div className="absolute z-20 w-full mt-1 p-3 text-sm" style={{borderRadius:'var(--radius-sm)',border:'1px solid var(--hairline)',backgroundColor:'var(--canvas-elevated)',color:'var(--mute)',boxShadow:'var(--shadow-sm)'}}>
          검색 결과가 없습니다.
        </div>
      )}
    </div>
  )
}

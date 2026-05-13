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
          className="w-full px-4 py-3 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
        />
        {loading && (
          <span className="absolute right-3 top-3.5 text-gray-400 text-xs animate-spin">⟳</span>
        )}
      </div>

      {open && results.length > 0 && (
        <ul className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-64 overflow-y-auto">
          {results.map((item, i) => (
            <li
              key={i}
              onClick={() => handleSelect(item)}
              className="px-4 py-3 hover:bg-blue-50 cursor-pointer border-b border-gray-100 last:border-0"
            >
              <p className="text-sm font-medium text-gray-900">{item.road_addr}</p>
              <p className="text-xs text-gray-500 mt-0.5">{item.jibun_addr}</p>
              {item.pnu && (
                <p className="text-xs text-gray-400 font-mono">PNU: {item.pnu}</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {open && results.length === 0 && query.length >= 2 && !loading && (
        <div className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow p-3 text-sm text-gray-500">
          검색 결과가 없습니다.
        </div>
      )}
    </div>
  )
}

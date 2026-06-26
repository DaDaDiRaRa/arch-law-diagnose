/**
 * 공모지침 목록 선택기 — 카테고리 필터(서버사이드) + 공모명 검색(클라이언트).
 *
 * BriefImportPanel(단일)·MultiSiteCompare(다중) 양쪽에서 공용. 마운트되면 목록을
 * 불러오고, 행 클릭 시 onPick(fileId)을 호출한다(이후 동작은 부모가 결정).
 */
import { useEffect, useState } from 'react'
import { api } from '../../utils/api'

// 생산 앱(competition_comparison) 카테고리 — 파일명 suffix와 동일. 서버사이드 필터에 사용.
// 새 카테고리가 생겨도 "전체"에는 항상 나옴(여기 미등록 시 칩만 누락).
const CATEGORY_OPTIONS = [
  ['', '전체'],
  ['public', '공공'], ['residential', '주거'], ['commercial', '상업'],
  ['office', '업무'], ['mixed_use', '복합'], ['cultural', '문화'],
  ['education', '교육'], ['medical', '의료'], ['hospitality', '숙박·관광'],
  ['industrial', '산업'], ['transport', '교통'], ['reconstruction', '재정비'],
  ['masterplan', '마스터플랜'], ['alternative', '대안'],
]

export default function BriefList({ onPick, picking = false }) {
  const [briefs, setBriefs] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')

  // 카테고리는 서버에서 필터(수백 건 누적 대비, limit 적용 전 분기)
  const load = async (cat) => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.listBriefs({ category: cat || undefined })
      setBriefs(res.briefs || [])
    } catch (e) {
      setError(e.message || '목록 조회 실패')
      setBriefs([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load('')
  }, [])

  const changeCategory = (cat) => {
    setCategory(cat)
    load(cat)
  }

  // 검색은 로드된 목록에 대해 클라이언트에서 즉시 필터(공모명·파일명)
  const shown = (briefs || []).filter((b) => {
    if (!search.trim()) return true
    const q = search.trim().toLowerCase()
    return (
      (b.competition_name || '').toLowerCase().includes(q) ||
      (b.file_id || '').toLowerCase().includes(q)
    )
  })

  return (
    <div>
      <div className="flex gap-1.5 mb-2">
        <select
          value={category}
          onChange={(e) => changeCategory(e.target.value)}
          disabled={loading}
          className="text-[11px] border border-gray-200 rounded px-1.5 py-1 bg-white text-gray-700 disabled:opacity-50"
        >
          {CATEGORY_OPTIONS.map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="공모명 검색"
          className="flex-1 min-w-0 text-[11px] border border-gray-200 rounded px-2 py-1 bg-white text-gray-700"
        />
      </div>

      {loading && <div className="text-[11px] text-gray-500 py-1">목록 불러오는 중…</div>}
      {error && (
        <div className="text-[11px] text-red-600 bg-red-50 border border-red-200 px-2 py-1.5 rounded mb-2">
          {error}
        </div>
      )}

      {!loading && briefs && briefs.length === 0 && !error && category && (
        <div className="text-[11px] text-gray-500 py-1">이 카테고리에 해당하는 공모가 없습니다.</div>
      )}
      {!loading && briefs && briefs.length === 0 && !error && !category && (
        <div className="text-[11px] text-gray-500 py-1">
          불러올 공모지침이 없습니다. (서버의 BRIEF_DIR에 brief json 필요 —
          competition_comparison 버킷의 _briefs/ 폴더 연결)
        </div>
      )}
      {!loading && briefs && briefs.length > 0 && shown.length === 0 && (
        <div className="text-[11px] text-gray-500 py-1">"{search}"에 맞는 공모가 없습니다.</div>
      )}

      {shown.length > 0 && (
        <div className="space-y-1.5">
          {shown.map((b) => (
            <button
              key={b.file_id}
              type="button"
              onClick={() => onPick(b.file_id)}
              disabled={picking}
              className="w-full text-left border border-gray-200 rounded px-3 py-2 bg-white hover:border-gray-400 transition-colors disabled:opacity-50"
            >
              <div className="text-xs font-medium text-gray-800 truncate">{b.competition_name}</div>
              <div className="text-[10px] text-gray-500 mt-0.5 flex gap-2">
                {b.facility_type && (
                  <span className="px-1.5 py-0.5 rounded bg-gray-100">{b.facility_type}</span>
                )}
                <span>부지 {b.site_count}개</span>
                {b.analyzed_at && <span>· {b.analyzed_at.slice(0, 10)}</span>}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

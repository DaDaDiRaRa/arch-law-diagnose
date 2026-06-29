// 자매 앱 arch-law-graph 로의 조문 원문 링크아웃.
// graph 는 법령 지식 레이어(원문·인용관계·지자체 비교)의 주인이고,
// diagnose 는 graph 의 검색 딥링크(?q=)로 적용 조문 원문을 열어준다.
// graph 미배포/다운 시 링크만 안 뜨면 되도록(degrade) 호출부에서 URL 유무로 분기.

// 배포 주소는 환경변수(VITE_GRAPH_URL, 빌드타임)로 override. 미설정 시 프로덕션 graph.
// 자동배포(CI source build)는 build-arg를 안 넘기므로 기본값을 prod 로 둔다.
// 로컬에서 로컬 graph(8080)로 테스트하려면 VITE_GRAPH_URL 로 덮어쓰기.
const GRAPH_BASE = (
  import.meta.env.VITE_GRAPH_URL ||
  'https://arch-law-graph-30350777436.asia-northeast3.run.app'
).replace(/\/+$/, '')

// 진단 law_ref 이름 → graph 검색어 정제.
// 예: "건축법 제55조 (건폐율)" → "건축법 제55조"
//     "국토계획법 시행령 제84조" → "국토의계획및이용에관한법률 시행령 제84조"
// graph 노드 법령명은 정식명을 쓰므로 약칭을 펴 키워드 매칭률을 높인다.
const _ABBR = [
  ['국토계획법', '국토의계획및이용에관한법률'],
]

export function graphSearchQuery(name) {
  if (!name) return ''
  let q = String(name).replace(/\s*\([^)]*\)\s*$/, '').trim() // 끝 괄호주석 제거
  for (const [abbr, full] of _ABBR) {
    if (q.includes(abbr)) q = q.replace(abbr, full)
  }
  return q
}

// 조문명으로 graph 검색 딥링크 URL 생성. 빈 이름이면 빈 문자열(호출부에서 숨김).
export function graphSearchUrl(name) {
  const q = graphSearchQuery(name)
  if (!q) return ''
  return `${GRAPH_BASE}/?q=${encodeURIComponent(q)}`
}

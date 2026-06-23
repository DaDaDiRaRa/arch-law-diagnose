# arch-law-graph (한국판) — 새 앱 시작 프롬프트

> 이 문서를 **새 빈 폴더**(D:\APPS\arch-law-graph)에서 새 Claude Code 세션 첫 메시지로 붙여넣으세요.
> 자매 앱 `arch-law-diagnose` (D:\APPS\arch-law-diagnose) 의 법제처 연동 코드를 참고/재활용합니다.

---

## 0. 한 줄 정의

건축 관련 **법령 체계 전체를 관계 그래프로 구축**하고, 그 그래프를 **2D 인터랙티브 네트워크 그래프(force-directed)로 시각화**하는 단독 웹앱.
(ARCO `arch-law-galaxy` 가 3D 우주였던 것을, 가독성·실무성 위해 2D 네트워크로 대체.) **데이터 백본(그래프) 먼저, 시각화는 그 위에.**

핵심 원칙: 이건 **발표·교육·탐색용 시각화 자산**이다. 정확도·법적 효력을 주장하지 않는다(면책 표시). 실무 진단은 자매 앱 `arch-law-diagnose` 담당.

---

## 1. 범위 — "전체 그래프"의 현실적 정의 (중요)

"전체"는 **대한민국 전체 법령(47,225 조문)이 아니다.** 건축 인허가에 실제로 엮이는 **건축 법령군 전체**다. 1차 대상:

| 법령군 | 포함 |
|---|---|
| 건축법 계열 | 건축법 · 건축법 시행령 · 건축법 시행규칙 |
| 국토계획 계열 | 국토의 계획 및 이용에 관한 법률 · 시행령 · 시행규칙 |
| 주차 | 주차장법 · 시행령 · 시행규칙 |
| 부속 | 건축물의 분양에 관한 법률, 녹색건축물 조성 지원법, 건축물의 에너지절약설계기준(고시), 주택법(건축 관련 조문만) |
| (확장 슬롯) | 조례(서울시 도시계획조례 등) — 스키마에 자리만 두고 2차에서 채움 |

→ 노드 수백~수천 규모. 이 정도면 임팩트 충분하고, 스키마는 무한 확장 가능하게 설계.

---

## 2. 아키텍처 — 2단계

### Phase 1: 데이터 백본 (그래프 구축) ← **먼저**

```
법제처 DRF API ──fetch──> 조문 원문 ──parse──> 노드/엣지 추출 ──> graph.json (+ graph.db)
```

**노드(node) 종류**
- `law` — 법령 자체 (건축법, 건축법 시행령 …)
- `article` — 조문 (제61조 등). 항·호는 article 본문에 인라인(법제처 스키마 그대로) 또는 하위 노드(선택)

**노드 속성**
```json
{
  "id": "건축법/제61조",
  "type": "article",
  "law_nm": "건축법",
  "article_no": "006100",
  "article_no_display": "제61조",
  "title": "일조 등의 확보를 위한 건축물의 높이 제한",
  "content": "...",
  "domain_tags": ["높이", "일조"],        // 8개 진단 카테고리로 분류
  "ef_yd": "20250101",                     // 시행일자 (갱신 추적용)
  "source_url": "https://www.law.go.kr/법령/건축법"
}
```

**엣지(edge) 종류** — 그래프의 "관계 선"
- `delegates` — 위임관계: 법 → 시행령 → 시행규칙 ("대통령령으로 정하는", "국토교통부령으로")
- `references` — 조문 간 인용: 본문의 "제61조에 따라", "제2조제1항제4호"
- `cross_law` — 타 법령 참조: 「국토의 계획 및 이용에 관한 법률」 등 「」 인용
- `byeolpyo` — 별표/별지 참조: "별표 9에 따라"

**엣지 추출 방법 (Phase 1의 핵심 난이도)**
- regex 1차: 조내용 본문에서 `제\d+조(의\d+)?`, `별표\s*\d+`, `「[^」]+」`, "대통령령/국토교통부령으로 정하는" 패턴 추출
- LLM 보조: 모호하거나 묵시적 위임("따로 정한다")은 Claude로 보강 — 단 **method 필드로 regex/llm 구분**, llm 추출은 신뢰도 낮음 표시
- 자매 앱의 `ordinance_extractor.py` 의 regex+LLM fallback 패턴을 그대로 차용

**산출물**
- `data/graph.json` — 프론트가 읽는 정적 파일 (Phase 2 데이터 계약)
- `data/graph.db` (SQLite + FTS5) — 검색·증분 갱신용 (선택)
- NetworkX 로 빌드 → json export (`networkx.node_link_data`)

**graph.json 스키마 (Phase 1↔2 계약, 고정)**
```json
{
  "meta": { "built_at": "...", "law_count": 0, "node_count": 0, "edge_count": 0 },
  "nodes": [ { "id", "type", "law_nm", "title", "domain_tags", "ef_yd", ... } ],
  "edges": [ { "source", "target", "type", "method", "evidence": "인용 원문 일부" } ]
}
```

### Phase 2: 시각화 (2D 인터랙티브 네트워크 그래프)

- **표현 형태**: force-directed 2D 네트워크. 법령·조문 = 노드, 위임/참조 = 엣지.
- **노드 크기**: 법령 > 조문. 또는 들어오는 참조 수(in-degree)에 비례 → "많이 인용되는 핵심 조문"이 커 보임
- **색상**: 8개 도메인(건폐율·용적률·높이·주차·조경·설비소방·행위제한·도시계획시설)별 군집 색
- **엣지 구분**: 위임=실선, 참조=점선, 타법참조=다른 색, LLM추출=흐리게(신뢰도 낮음 표시)
- **인터랙션**:
  - 노드 클릭 → 조문 상세 패널(제목·본문·시행일·출처 URL)
  - 노드 호버/선택 → 연결된 엣지·이웃 노드만 강조, 나머지 흐리게
  - 검색(조문명/번호), 도메인·법령별 필터 토글
  - 드래그·줌·팬
- **발전 슬롯**: 노드 클릭 → 자매 앱 `arch-law-diagnose` 의 실제 법규 조회 API 연결. Phase 2에선 자리만, 연결은 나중.
- (선택) 뷰 토글: 같은 graph.json 으로 "네트워크 뷰" ↔ "계층 트리 뷰" 전환 — 위임 관계는 트리가 더 명확하므로 여유되면 추가

---

## 3. 기술 스택

| 영역 | 선택 | 비고 |
|---|---|---|
| 그래프 빌드 | Python 3.12 · NetworkX · httpx | 자매 앱 `law_go_kr_client.py` 재사용 |
| 데이터 저장 | graph.json (정적) + SQLite/FTS5 (검색) | |
| 프론트 | React + Vite + **react-force-graph-2d** | d3-force + canvas. 수천 노드까지 부드럽고 코드 최소. PoC 최적 |
| (대안 a) | **Cytoscape.js** (+fcose 레이아웃) | 필터·확장/축소·레이아웃 다양. 그래프 기능 풍부할 때 |
| (대안 b) | Sigma.js (WebGL) | 노드 만 단위 넘어 성능 필요 시 |
| 배포 | 정적 호스팅 또는 Docker→Cloud Run | graph.json만 서빙하면 백엔드 불필요 |

성능: react-force-graph-2d 는 canvas 기반이라 수천 노드까지 무난. 만 단위 넘어가면 Sigma.js(WebGL)로 교체. **데이터(graph.json)는 동일하므로 라이브러리 교체는 Phase 2 내부 일.**

---

## 4. 자매 앱에서 가져올 것 (복사 또는 참고)

`D:\APPS\arch-law-diagnose\backend\services\` 에서:
- `law_go_kr_client.py` — 법제처 DRF API 클라이언트 (search_law / get_law_articles / _parse_law_xml). **거의 그대로 재사용.** → 이미 `builder/`에 복사됨
- `ordinance_extractor.py` — regex+LLM 추출 패턴 (엣지 추출 로직의 본보기)
- `zone_use_normalizer.py` — 용도지역 표준명 (domain_tags 분류 보조)
- `llm_client.py` — Claude judge_json 래퍼 (LLM 보조 추출용)
- `.env` 의 `LAW_API_KEY`, `ANTHROPIC_API_KEY` 재사용

데이터 연동 방식: **느슨한 결합.** 자매 앱과 코드/배포는 완전 분리. 공유는 graph.json(정적 export)뿐. 나중에 실시간 조회가 필요해지면 자매 앱에 `/api/law-graph` 엔드포인트 추가.

---

## 5. 세션 운영 규칙 (자매 앱 컨벤션 승계)

- 로그·주석·커밋 메시지 한국어
- 법규 무단 해석 금지. 그래프는 **원문 인용(evidence)**을 엣지마다 보존 → 사람이 검증 가능
- LLM 추출 엣지는 `method:"llm"` 로 명시, 시각적으로도 구분(점선 등)
- 모든 화면에 면책 문구("참고용 시각화, 법적 효력 없음")
- 단순함 우선. 요청 범위 밖 추상화 금지

---

## 6. 첫 작업 (이 순서로)

1. ✅ 새 repo 초기화 + 폴더 구조 (`builder/` Python, `web/` React, `data/`)
2. ✅ `law_go_kr_client.py` 가져와서 건축법 1개 법령 조문 전체 fetch 동작 확인 (`builder/fetch_test.py`)
3. 엣지 추출 regex 프로토타입 — 건축법 본문에서 `제\d+조`·`별표`·「」 인용 뽑아 graph.json 생성 (`builder/build_graph.py`)
4. graph.json 스키마 확정 후, react-force-graph-2d 로 노드/엣지 최소 렌더 (점 + 선)
5. 1개 법령 동작 확인 → 법령군 전체로 확장 → 인터랙션(클릭/검색/필터)

**"끝났다"의 정의 (Phase 1):** 건축 법령군 전체가 graph.json 한 파일로 빌드되고, 노드/엣지 수가 meta에 찍히며, 엣지마다 evidence 원문이 보존됨.
**"끝났다"의 정의 (Phase 2):** 브라우저에서 graph.json 을 2D 네트워크로 띄우고, 노드 클릭 시 조문 본문이 보이며, 도메인별 색·이웃 강조·검색·필터가 동작함.

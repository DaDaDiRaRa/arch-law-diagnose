# arch-law-diagnose

건축 법규 자동 진단 시스템 — 사내 전용. 주소 + 건물 정보를 입력받아 8개 카테고리를 자동 검토하고 GREEN/YELLOW/RED 신호와 종합 점수를 반환.

---

## 기술 스택

- **Backend**: FastAPI (Python 3.12), SQLite, port 8000
- **Frontend**: React + Vite + Tailwind, port 5173
- **DB**: `./data/arch_law.db` (CacheManager 관리)
- **AI**: Anthropic Claude (설비·소방 정성 판단 + 자연어 질의)

---

## 외부 API (.env 키 5종)

| 서비스 | 환경변수 | 용도 |
|---|---|---|
| VWorld | `VWORLD_API_KEY` | 좌표 변환·용도지역·지적도·도로폭 |
| Kakao Local | `KAKAO_API_KEY` | 주소 자동완성 |
| 공공데이터포털 | `LURIS_API_KEY` 또는 `DATA_GO_KR_API_KEY` | LURIS 행위제한 (legacy) |
| 토지이음 | `EUM_ID`, `EUM_KEY` | 법령정보·고시·개발인허가·행위제한·쉬운규제안내서 (Phase 0~3 작업 예정) |
| Anthropic | `ANTHROPIC_API_KEY` | Claude API |
| Slack (선택) | `SLACK_WEBHOOK_URL` | 시니어 검토 요청 |

시작 시 `main.py` 가 5개 API 활성 상태를 ✅/❌ 로깅. 누락된 API는 graceful degrade — 해당 항목만 "확인필요(YELLOW)" 처리.

---

## 진단 8개 카테고리

| 코드 | 계산기 | 출처 |
|---|---|---|
| 행위제한 | `land_use_act.py` | LURIS API |
| 도시계획시설 | `urban_facility.py` | VWorld 지적도 ∩ 시설 SHP |
| 건폐율 | `coverage.py` | 조례 우선 → 시행령 (zone_limits.json) |
| 용적률 | `far.py` | 동일 + 4종 완화 (녹색·에너지·지능형·장수명) |
| 높이·일조 | `height.py` | §60·§61 자동 판정 (정북 이격거리 입력 시) |
| 주차 | `parking.py` | 주차장법 시행령 |
| 조경 | `landscape.py` | 건축법 §42 + 시행령 §27 |
| 설비·소방 | `fire_safety.py` | Claude AI 정성 판단 |

---

## 신호 판정 로직

- **RED**: `pass=False` 항목 존재
- **YELLOW**: `pass=None` 항목 존재 OR 종합점수 < 7.0
- **GREEN**: 모든 항목 통과 + 종합점수 ≥ 7.0

종합점수 — 가중평균 0~10. 가중치는 `backend/config/law_scoring_weights.json`.

---

## 핵심 설계 원칙

### 정확도
- **용도지역 정규화 필수** — `services/zone_use_normalizer.py` 의 `normalize()`/`category_of()` 통과한 표준명만 사용. 부분매칭 금지 ("주거지역"이 "준주거지역"으로 잘못 매칭되는 버그 방지). 매칭 실패 시 None → "확인필요"
- **AI 단독 판정 금지** — 결정론적 룰로 처리할 수 있는 건 코드로. LLM은 정성 영역(설비·소방) 또는 보조 의견만. 환각으로 가짜 판례 인용 위험.
- **부분 매칭 제거됨** — `coverage._get_limit`, `far._get_limit`, `multi_parcel._get_zone_limit`, `diagnose_engine._get_default_far_limit`, `landscape._required_ratio` 모두 정규화기 사용

### 신뢰성
- **모든 진단 응답에 `data_quality` 필드** — 어떤 API가 사용됐는지, fallback인지, stale 캐시인지 명시. 프론트의 `DataQualityBanner` 가 사용자에게 표시.
- **Stale 캐시 fallback** — `land_use_resolver.py` 에서 VWorld 재조회 실패 시 stale 캐시 사용 (빈 결과보다 낫다는 원칙)
- **조례 seed DB** — `config/ordinance_seed.json` 의 서울특별시 도시계획조례 §54·§55 값을 시작 시 idempotent 적재. API 장애 시에도 안정적.

### 편의성
- **자동 채움** — 주소 선택 시 토지이용계획(VWorld) 자동 조회 → 용도지역/지역지구/도로폭 자동 입력
- **수동 입력 우선** — 사용자가 입력한 값은 항상 자동 조회값보다 우선

---

## 진행 중 / 보류 작업

### Phase 0~3 — 토지이음 5개 API 통합 (예정)
- Phase 0: `EumClient` 신설 (5개 API + XML 파싱)
- Phase 1: 법령정보 → 진단 카드에 조문 본문 펼쳐보기
- Phase 2: 고시정보 → `law_change_tracker.py` 보강
- Phase 3: 개발행위허가정보 → 주변 개발 동향 섹션
- 쉬운규제안내서: API 통합 안 함, 참고 자료로 활용

### 보류
- **도로폭 자동 조회** (5.3) — VWorld `lt_l_sprd` 레이어가 도로명만 반환 (폭 속성 없음). `lt_l_moctlink` 도 NOT_FOUND. 인프라(코드/DB 컬럼/UI)는 구축 완료, 데이터 소스만 보류 상태. 토지이음 API 도입 후 재검토.

---

## 자주 하는 작업

### 서버 시작
```
start-servers.bat
```
- 백엔드(`uvicorn --reload`) + 프론트엔드(`npm run dev`) 별도 cmd창에서 시작
- `--reload` 옵션 있어서 backend `.py` 수정 시 자동 재시작
- `.env` 변경은 자동 감지 안 함 → 수동 재시작

### 백엔드만 수동 재시작
```
cd backend
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 캐시 초기화 (특정 PNU)
SQLite 직접 조작:
```sql
DELETE FROM land_info_cache WHERE pnu='...';
```
또는 전체 재시작은 `./data/arch_law.db` 삭제 (조례 seed 32건은 자동 재적재됨).

---

## 디버깅 팁

### LLM JSON 파싱
- `llm_client._extract_json()` 가 3단계 자동 복구 (strict → 콤마 보정 → truncation 절단)
- 복구 성공 시 INFO 로그 (`자동 복구 성공`)
- 모두 실패 시 WARNING 에 에러 위치 앞뒤 100자 컨텍스트 출력

### VWorld 응답 디버깅
- 도로폭 호출 시 `[VWorld 도로 응답 샘플] 첫 feature properties = {...}` 로그로 응답 구조 확인 가능

### 브라우저 캐시
- `frontend/src/utils/api.js` 에 `cache: 'no-store'` 적용됨
- 백엔드 `/api/address/search` 응답에도 `Cache-Control: no-store` 헤더
- 그래도 문제 시 Ctrl+Shift+R (강력 새로고침)

---

## 코딩 컨벤션 (이 프로젝트)

- **새 zone_use 매칭 로직 작성 금지** — 무조건 `services.zone_use_normalizer` 사용
- **LLM 응답 파싱은 `llm_client.judge_json()` 거치기** — 자동 복구 파이프라인 통과
- **API 키 누락은 graceful degrade** — `if not self._key: return None` 패턴, 예외 던지지 않음
- **진단 결과 응답에 새 필드 추가 시** — `cache_manager` 의 land_info_cache 스키마도 함께 ALTER (구버전 DB 호환)
- **로그는 한국어** — 사용자/운영자가 직접 읽음

---

## 참고 자료 (앱 외부)

- 토지이음 쉬운규제안내서 API (`OP/ebGuideBookList`) — **API 통합은 안 함**. 사용자가 어려운 법규 검토할 때, 또는 개발자가 신규 기능 만들 때 참고용으로 호출.

---

## 면책

자동 진단 결과는 **참고용**. 실제 인허가 책임은 시니어 건축사/설계자에게. 모든 진단서 푸터와 LegalReviewReport 에 면책 문구 표시.

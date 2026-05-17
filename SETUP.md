# SETUP — 새 PC / 다른 장소에서 셋업

집·회사 양쪽에서 동일 환경으로 돌리기 위한 가이드.
**전략: 회사 클라우드 공유 폴더에 데이터를 두고, 양쪽 PC 가 junction 으로 같은 데이터를 바라보게 한다.**

---

## 매번 새로 받아야 하는가?

**No.** 데이터·DB·시크릿을 회사 클라우드 한 폴더에 모아두면, 새 PC 셋업은 git clone + junction 연결 + 의존성 설치만 하면 됩니다.

| 항목 | 크기 | 어디에? | 비고 |
|---|---|---|---|
| 소스 코드 | ~수 MB | git | `git clone` |
| `files/3/shp/` 도시계획시설 SHP | ~900MB | **공유 폴더** | 토지이음 원본, 월간 갱신 |
| `data/arch_law.db` 조례·캐시·이력 | ~수십 MB | **공유 폴더** | 진단할 때마다 업데이트됨 |
| `.env` API 키 8종 | <1KB | **공유 폴더** | 양쪽 PC 동일하게 사용 |
| `KUNWON_DB/cases/` 사내 케이스 | 가변 | **공유 폴더** | 수작업 입력 데이터 |
| `backend/.venv/` | ~수백 MB | 로컬만 | OS·Python 버전 따라 재생성 |
| `frontend/node_modules/` | ~수백 MB | 로컬만 | 동일 사유 |

`.venv`·`node_modules` 는 PC 마다 재생성이 더 안전 (Windows·Python·Node 버전 차이).

---

## 공유 폴더 트리

회사 클라우드 안에 다음 구조로 만듭니다. 예시 경로: `\\company-cloud\arch-law-shared\` 또는 `C:\Users\...\OneDrive - 회사명\arch-law-shared\`.

```
arch-law-shared/
├── README.md                     ← 이 폴더 운영 규칙·금지사항
├── .env                          ← API 키 8종 (양쪽 PC 동일하게 사용)
├── data/
│   ├── arch_law.db               ← SQLite (조례 + 진단 캐시 + 이력)
│   └── review_requests.log       ← 시니어 검토 요청 로그
├── files/
│   └── 3/
│       └── shp/                  ← 토지이음 도시계획시설 SHP (~900MB)
│           ├── KLIP_003_*_11000/
│           ├── KLIP_003_*_26000/
│           └── ... (17개 시·도)
├── cases/                        ← 사내 케이스 DB 본체
├── backups/
│   ├── arch_law.db.2026-05-17    ← 주간 백업 (사고 대비)
│   └── ...
├── lock/
│   └── in_use.lock               ← 동시 진단 방지 락 (수동/스크립트)
└── docs/                         ← UQ 코드표·운영 메모 등 참고자료 (선택)
```

---

## ⚠️ 시작 전 반드시 확인

### 1. 클라우드 종류에 따른 SQLite 안전성

| 클라우드 형태 | DB 안전성 | 비고 |
|---|---|---|
| OneDrive·Dropbox·Google Drive 비즈니스 (로컬 동기화형) | ✅ 안전 | DB 가 로컬 디스크에 있고 클라우드는 백업처럼 동작 |
| SMB 네트워크 드라이브 (`\\fileserver\...`) | ⚠️ 위험 | SQLite 락이 네트워크 위에서 깨질 수 있음 |
| SharePoint 웹 마운트·WebDAV | ❌ 위험 | 락 지원 빈약, 동시 쓰기 시 DB 손상 가능 |

**위험 등급이면** — `data/arch_law.db` 만 로컬 디스크에 두고 나머지(SHP·`.env`·cases)만 공유. DB 는 매일 종료 시 공유 폴더로 백업 복사.

### 2. 동시 진단 금지

양쪽 PC 가 같은 SQLite 파일을 동시에 쓰면 깨집니다. `lock/in_use.lock` 으로 운영 규칙 만들기 — 작업 시작 시 락 생성, 종료 시 삭제. 누군가 락을 잡고 있으면 다른 PC 는 진단 금지.

---

## 셋업 — 메인 PC (최초 1회)

데이터를 한 번 모아 공유 폴더에 올리는 작업.

### 1. 공유 폴더에 디렉터리 골격 만들기

탐색기에서 `arch-law-shared/` 안에 `data/`, `files/3/`, `cases/`, `backups/`, `lock/`, `docs/` 폴더 생성.

### 2. 기존 데이터 이동

```powershell
$shared = "C:\Users\<USER>\OneDrive - 회사명\arch-law-shared"
$proj   = "c:\Users\kim junghyun\arch-law-diagnose"

# 데이터 이동 (move, 복사 아님)
move "$proj\files\3"        "$shared\files\3"
move "$proj\data\arch_law.db" "$shared\data\arch_law.db"
move "$proj\.env"           "$shared\.env"
move "$proj\KUNWON_DB\cases" "$shared\cases"
```

`data/` 폴더 자체는 비워두고 폴더만 유지 (다음 단계에서 junction 으로 대체).

### 3. junction 만들기 (관리자 권한 `cmd`)

PowerShell 말고 `cmd` 권장 — `mklink` 가 cmd 내장 명령.

```cmd
mklink /J  "c:\Users\kim junghyun\arch-law-diagnose\files\3"          "C:\...\arch-law-shared\files\3"
mklink /J  "c:\Users\kim junghyun\arch-law-diagnose\data"             "C:\...\arch-law-shared\data"
mklink /J  "c:\Users\kim junghyun\arch-law-diagnose\KUNWON_DB\cases"  "C:\...\arch-law-shared\cases"
mklink     "c:\Users\kim junghyun\arch-law-diagnose\.env"             "C:\...\arch-law-shared\.env"
```

- `/J` = directory junction (폴더용). 파일(`.env`)은 옵션 없이 symbolic link
- junction 은 git 이 일반 폴더처럼 인식 → 이미 `.gitignore` 된 경로라 문제 없음
- 기존 폴더·파일이 그 자리에 있으면 mklink 실패 → 먼저 비우거나 이동 후 시도

### 4. 클라우드 동기화 완료 대기

900MB+ 첫 업로드는 시간 소요. OneDrive 라면 트레이 아이콘에서 진행률 확인.

### 5. 동작 확인

```powershell
cd "c:\Users\kim junghyun\arch-law-diagnose"
.\start-servers.bat
```

백엔드 로그에 8개 API ✅ 표시 + 프론트(http://localhost:5173) 진단 정상 동작 확인.

---

## 셋업 — 다른 PC (회사)

1. `git clone` 으로 소스 받기
2. 클라우드 클라이언트(OneDrive 등) 설치 + 로그인 → `arch-law-shared/` 동기화 완료 대기
3. 위 **3번 단계** 와 동일하게 junction 생성 (경로만 회사 PC 기준으로 변경)
4. 의존성 설치:
   ```powershell
   cd backend
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   cd ..\frontend
   npm install
   ```
5. `start-servers.bat` 실행

---

## 운영 규칙 (`arch-law-shared/README.md` 에 적어둘 것 권장)

1. **동시 진단 금지** — 진단 시작 전 `lock/in_use.lock` 확인. 비어있으면 본인 PC 이름·시작 시각 적은 파일 생성. 종료 시 삭제.
2. **주간 DB 백업** — 매주 월요일(또는 자동 스크립트) 에 `data/arch_law.db` 를 `backups/arch_law.db.YYYY-MM-DD` 로 복사. 4주 이상 된 백업은 정리.
3. **시드 재실행 전 백업** — `seed_municipal_ordinances --commit` 같은 대규모 작업 전 DB 백업 필수.
4. **OneDrive "이 장치에 항상 유지"** — 데이터 폴더 우클릭 → "이 장치에 항상 유지" 체크. 안 그러면 진단마다 클라우드에서 다운로드해서 느림.
5. **시크릿 회전** — `.env` 의 API 키 노출 의심 시 양쪽 PC 동시 회전 (공유 파일이라 한 곳만 바꿔도 모두 반영됨).

---

## 셋업 검증 체크리스트

- [ ] junction 정상: `dir /AL` 로 `<JUNCTION>` 표시 확인
- [ ] `start-servers.bat` → 백엔드 로그 8개 API ✅
- [ ] 프론트 진단 실행 → 8개 카테고리 모두 결과
- [ ] `data/arch_law.db` 에 조례 레코드 존재 (없으면 시드 재실행)
- [ ] `files/3/shp/` 17개 시·도 폴더 + 각각 9개 카테고리 SHP
- [ ] `.env` 의 API 키들이 정상 로드 (백엔드 시작 로그 확인)

---

## 자주 막히는 지점

- **`mklink` "권한 거부"** → 관리자 권한 `cmd` 필요
- **OneDrive "온라인 전용 파일"** → "이 장치에 항상 유지" 체크 안 함. 데이터 폴더 우클릭 메뉴
- **DB 락 에러 (`database is locked`)** → 다른 PC 가 진단 중이거나, 클라우드가 SQLite 비친화적 (위 ⚠️ 표 참조)
- **junction 만든 뒤 git 이 폴더를 추적하려 함** → `.gitignore` 에 이미 등록된 경로(`data/`, `files/3/`, `.env`) 라서 추적 안 됨. 만약 새 경로면 `.gitignore` 추가
- **회사 PC ↔ 집 PC 의 OneDrive 경로 차이** → junction 만 PC 별로 다시 만들면 됨. 코드·git 내용은 동일

---

## 대안 (참고)

### 외장 SSD (클라우드 차단된 경우)
같은 junction 방식, 대상이 USB SSD. SSD 안 꽂으면 junction 깨진 폴더로 보임. USB 드라이브 문자 일치 권장.

### 매번 재다운로드 (최후의 수단)
1. `git clone`
2. SHP: 토지이음 https://www.eum.go.kr/web/op/da/daDownload.jsp?layerType=ubi&dataNo=UBI003 → SHP 자료유형 전국 zip → `files/3/shp/` 압축 해제
3. `.env`: `.env.example` 복사 → 키 8종 채우기 (비번관리자에서 가져오기)
4. DB 시드: `cd backend; python -m scripts.seed_municipal_ordinances --commit` (~수 분 + LLM 비용)
5. `.venv` + `node_modules` 재생성

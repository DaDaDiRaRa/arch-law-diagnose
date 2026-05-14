# files/3/ — 토지이음 도시계획시설 결정도형정보

> 이 폴더의 원본 데이터(SHP/CSV)는 GitHub 100MB 한도 초과로 git 저장소에서 **추적하지 않습니다**.
> 새 환경에서 작업 시 아래 안내에 따라 직접 다운로드하세요.

## 다운로드

1. 토지이음 데이터개방 페이지 접속
   https://www.eum.go.kr/web/op/da/daDownload.jsp?layerType=ubi&dataNo=UBI003
2. **자료유형: SHP** 선택
3. 최신 `(도시계획)시설정보_*_전국.zip` 다운로드 (~500MB)
4. 이 폴더(`files/3/shp/`)에 압축 해제

## 폴더 구조 (정상 동작 시)

```
files/3/
├── README.md                       ← 이 파일
└── shp/
    ├── KLIP_003_*_11000/           ← 서울특별시 (또는 UPIS_003_*)
    ├── KLIP_003_*_26000/           ← 부산광역시
    ├── ... (시·도별 17개 폴더)
    └── KLIP_003_*_52000/           ← 전라북도
        ├── KLIP_C_UQ151.shp        ← 교통시설
        ├── KLIP_C_UQ152.shp        ← 공간시설
        ├── ... (UQ151~UQ159, 9개 카테고리)
        └── KLIP_C_UQ159.shp
```

각 시·도 폴더에 9개 카테고리 SHP 세트(`.shp`/`.dbf`/`.shx`/`.prj`/`.fix`).

## 메타정보

| 항목 | 값 |
|---|---|
| 좌표계 | EPSG:5174 (Bessel 보정된 중부 좌표계) |
| 갱신주기 | 월간 |
| 제공기관 | 국토교통부 / 토지이음 |
| 활용 위치 | [backend/services/urban_facility/](../../backend/services/urban_facility/) — SHP→R-tree 인덱스, 좌표 변환, 대지 폴리곤 교차 |

## 활용 기능

- **B1**: 도시계획시설 저촉 검사 (점 검사) — [services/calculator/urban_facility.py](../../backend/services/calculator/urban_facility.py)
- **B7**: 대지면적 자동 보정 (폴리곤 교차) — [services/urban_facility/lookup.py](../../backend/services/urban_facility/lookup.py)

## CSV 파일 (선택)

`KP_CTPL_FCLT_DSWE.csv`, `KP_OPTN_PLAN_CNFM.csv`, `TN_UBPLFC_WTNNC.csv`는
결정고시 속성 테이블입니다. **현재 진단에는 미사용** (공간 좌표 없음 — SHP만 사용).
필요 시 같은 페이지에서 자료유형 CSV로 다운로드 가능합니다.

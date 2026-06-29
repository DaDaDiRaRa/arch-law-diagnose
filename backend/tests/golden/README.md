# 골든 회귀 케이스 (실 인허가 사례)

실제 인허가/심의를 거친 프로젝트의 **건축개요서**에서 추출한 정답값으로,
진단 엔진이 그 산정값(건폐율·용적률 등)을 그대로 재현하는지 고정한다.
리팩터·재빌드가 정답을 깨면 CI가 잡는다. 실행: `test_golden_cases.py`.

## 익명화 규칙 (필수)

> 이 폴더는 git 에 커밋된다. **식별정보 금지, 숫자만.**

- ❌ 사업명·주소·지번·발주처·블록번호·설계자 등 **식별정보 일체 제외**
- ✅ 용도지역·면적·층수·높이·건폐율·용적률 등 **수치와 용도지역만** 보존
- `id`/`label` 은 용도·용도지역 기반의 **일반 명칭**으로 (예: `office_general_commercial_01`)

## 스키마

```jsonc
{
  "id": "<영문 슬러그>",
  "label": "<용도+용도지역 일반 명칭>",
  "source": "<어떤 문서에서·무엇을 제외했는지>",
  "input": {                       // 엔진에 그대로 투입
    "building_use": "오피스텔",
    "zone_use": "일반상업지역",      // zone_use_normalizer 표준명
    "site_area": 4667.60,
    "building_area": 3175.89,
    "total_floor_area": 47629.22,
    "floor_area_above": 32663.79,  // 용적률 산정 연면적(부속주차 등 제외 후)
    "floors_above": 39, "floors_below": 5, "height": 134.7,
    "landscape_area": 774.86,             // 선택
    "provided_parking_spaces": 323        // 선택
  },
  "applied_ordinance": {           // 그 사례에 실제 적용된 조례 한도(없으면 생략 → 시행령 기본값)
    "building_coverage_ratio": 70.0,
    "floor_area_ratio": 700.0,
    "landscape_ratio": 15.0
  },
  "expected": {                    // 검증할 정답
    "건폐율": {"actual_pct": 68.04, "limit_pct": 70.0, "pass": true},
    "용적률": {"actual_pct": 699.80, "limit_pct": 700.0, "pass": true},
    "signal_not": "RED"            // 신호가 이 값이면 실패(오반려 방지)
  }
}
```

## 검증 원칙

- **결정론적 산정값(`actual_pct`)이 핵심** — 면적 입력만으로 정해지며 조례·완화와 무관. 가장 단단한 정답.
- `limit_pct`·`pass` 는 `applied_ordinance` 로 실제 한도를 주입해 검증.
- 외부 API(VWorld·LURIS·EUM·AI)는 **호출하지 않음**(좌표 미제공 + skip_ai). 그래서 행위제한·도시계획시설·설비소방은 오프라인에서 "확인필요(YELLOW)"가 정상 — 신호는 `signal_not: RED` 로만 느슨히 본다.
- **완화·공개공지를 입력에 넣으면** 한도가 올라가 면도날 통과 검증이 흐려질 수 있음 → 그런 항목은 `context_recorded_not_asserted` 에 기록만 하고 별도 케이스에서 검증.

## 현재 커버리지 (10건, 2026-06-29)

용도지역 6종 × 다양한 유형. 다수가 법정/허용/상한 **면도날 통과**를 정확 재현.

| 케이스 | 용도지역 | 유형 | 건폐율(계획/한도) | 용적률(계획/한도) |
| --- | --- | --- | --- | --- |
| office_general_commercial_01 | 일반상업 | 오피스텔 | 68.04 / 70 | 699.80 / 700 |
| office_redevelopment_general_commercial_01 | 일반상업 | 업무(재개발) | 58.21 / 60 | 799.51 / 800 |
| apartment_rebuild_general_commercial_01 | 일반상업 | 주상복합 재건축 | 38.35 / 60 | 489.99 / 490 |
| mixed_residential_junjugeo_01 | 준주거 | 주거복합 | 59.84 / 60 | 377.14 / 377.5 |
| apartment_redevelopment_2nd_residential_01 | 제2종일반주거 | 아파트(재개발) | 20.05 / 60 | 229.70 / 241.97 |
| apartment_rebuild_2nd_residential_01 | 제2종일반주거 | 아파트(재건축) | 25.05 / 50 | 299.87 / 300 |
| apartment_rebuild_3rd_residential_01 | 제3종일반주거 | 아파트(재건축) | 24.08 / 50 | 299.99 / 300 |
| school_3rd_residential_01 | 제3종일반주거 | 교육연구시설 | 29.99 / 50 | 117.83 / 290 |
| mixed_use_central_commercial_01 | 중심상업 | 주상복합 | 56.48 / 80 | 800.50 / 1300 |
| mixed_use_district_plan_01 | 지구단위(업무복합용지) | 주상복합 | 59.95 / 60 | 269.57 / 270 |

**남은 용도지역**(미수집): 제1종일반주거·전용주거·근린상업·유통상업·준공업·일반/전용공업·보전/생산/자연녹지.
**남은 시설**(미수집): 근린생활·숙박·의료·노유자·물류·공장·단독/다세대.
> 참고: 건폐율·용적률 정답값은 *용도지역*이 좌우하고 building_use(시설)는 거의 무관(주차만 영향). 다양성 우선순위는 용도지역.

## 새 케이스 추가

`golden/` 에 위 스키마의 JSON 하나 더 넣으면 끝(자동 수집·파라미터화). M드라이브 건축개요 PDF 후보 카탈로그는 scratchpad `m_cat2.tsv`·`m_gaeyo.tsv`·`m_hits.tsv` 참조.

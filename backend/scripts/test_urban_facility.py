"""도시계획시설 저촉 검사 테스트.

부산 시내 임의 좌표로 SHP 인덱싱 + 검사 흐름 검증.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from services.urban_facility.lookup import check_facility_conflict


def main():
    # 부산시청 좌표 (WGS84) — 청사면 UQ154 저촉 가능
    print("=== 케이스 1: 부산시청 인근 (WGS84) ===")
    t0 = time.perf_counter()
    r = check_facility_conflict(
        lat=35.179554,
        lng=129.075642,
        sido_code="26000",
    )
    elapsed = time.perf_counter() - t0
    print(f"  로딩+조회 {elapsed:.2f}s | checked={r['checked']} | severity={r['severity']}")
    print(f"  note: {r['note']}")
    for c in r["conflicts"][:5]:
        print(f"    · {c['category']} | {c['facility_name']} ({c['uq_code']}) | 면적 {c['area_sqm']}")

    # 같은 시도 재호출 — 캐시 효과
    print("\n=== 케이스 2: 동일 시도 재호출 (캐시 적중) ===")
    t0 = time.perf_counter()
    r = check_facility_conflict(
        lat=35.158068,
        lng=129.160354,  # 부산 해운대 인근
        sido_code="26000",
    )
    elapsed = time.perf_counter() - t0
    print(f"  재조회 {elapsed:.3f}s | severity={r['severity']}")
    print(f"  note: {r['note']}")
    for c in r["conflicts"][:3]:
        print(f"    · {c['category']} | {c['facility_name']}")

    # 좌표 없음 — fallback
    print("\n=== 케이스 3: 좌표 없음 ===")
    r = check_facility_conflict(lat=None, lng=None, sido_code="26000")
    print(f"  checked={r['checked']} | note: {r['note']}")

    # PNU로 시도 추정
    print("\n=== 케이스 4: PNU로 시도 추정 (서울) ===")
    t0 = time.perf_counter()
    r = check_facility_conflict(
        lat=37.566535,
        lng=126.977969,  # 서울시청
        pnu="1114011500100010000",
    )
    elapsed = time.perf_counter() - t0
    print(f"  소요 {elapsed:.2f}s | checked={r['checked']} | severity={r['severity']}")
    print(f"  note: {r['note']}")

    print("\n✅ 도시계획시설 저촉 검사 통합 테스트 완료")


if __name__ == "__main__":
    main()

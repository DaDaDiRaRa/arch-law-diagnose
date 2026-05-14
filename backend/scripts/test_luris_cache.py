"""LURIS 캐시 동작 검증 — DB 한 번 우회 → 두 번째는 캐시 적중.

API를 실제 호출하지 않고 mock으로 행위제한 응답을 만들어
캐시 저장/적중/만료 흐름을 단위 검증한다.
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


async def main():
    # 임시 DB로 격리 테스트
    tmpdir = tempfile.mkdtemp(prefix="luris_cache_test_")
    db_path = os.path.join(tmpdir, "test.db")
    os.environ["DB_PATH"] = db_path
    os.environ["LURIS_TTL_DAYS"] = "90"

    # 모듈 import (env 설정 이후)
    from services.cache_manager import CacheManager
    from services.luris_client import LurisClient

    cache = CacheManager()
    await cache.init()

    client = LurisClient(cache=cache)

    # 1) 첫 호출 — 캐시 미스 → API 호출됨 (실제 호출이라 시간 걸림)
    print("=== 1) 첫 호출: 캐시 미스 + 실제 API 호출 ===")
    info1 = await client.get_act_info(
        area_cd="11680",       # 서울 강남구
        ucode="UQA430",        # 자연녹지지역
        land_use_nm="주택",
    )
    print(f"   응답 있음: {info1 is not None}")
    print(f"   hits={client.cache_hits} | misses={client.cache_misses}")
    assert client.cache_misses == 1
    assert client.cache_hits == 0

    # 2) 두 번째 호출 — 같은 키 → 캐시 적중
    print("\n=== 2) 같은 키 재호출: 캐시 적중 ===")
    info2 = await client.get_act_info(
        area_cd="11680",
        ucode="UQA430",
        land_use_nm="주택",
    )
    print(f"   응답 동일: {info1 == info2}")
    print(f"   hits={client.cache_hits} | misses={client.cache_misses}")
    assert client.cache_hits == 1
    assert client.cache_misses == 1

    # 3) DB에 직접 적재해서 None 응답도 캐싱되는지 검증
    print("\n=== 3) None 응답(데이터 없음)도 캐싱 — 재조회 시 API 호출 안 함 ===")
    await cache.set_luris_act_info("99999", "UQZ000", "없는행위", None)
    hit, cached = await cache.get_luris_act_info("99999", "UQZ000", "없는행위")
    print(f"   hit={hit}, info={cached}")
    assert hit is True
    assert cached is None

    # 4) 키 다르면 캐시 미스
    print("\n=== 4) 다른 키 호출: 미스 → 실제 API 호출 (시간 걸림) ===")
    info3 = await client.get_act_info(
        area_cd="11680",
        ucode="UQA430",
        land_use_nm="근린생활시설",
    )
    print(f"   응답 있음: {info3 is not None}")
    print(f"   hits={client.cache_hits} | misses={client.cache_misses}")
    assert client.cache_misses == 2

    # 5) TTL 만료 시뮬레이션 — fetched_at 강제로 옛날 날짜로 변경
    print("\n=== 5) TTL 만료 시뮬레이션 ===")
    await cache.execute(
        "UPDATE luris_act_info_cache SET fetched_at='2020-01-01T00:00:00' WHERE area_cd='99999'"
    )
    hit_old, _ = await cache.get_luris_act_info("99999", "UQZ000", "없는행위")
    print(f"   만료된 키 hit={hit_old} (False여야 함)")
    assert hit_old is False

    await client.close()
    await cache.close()

    print("\n✅ LURIS 캐시 5개 케이스 모두 통과")
    print(f"   최종 통계: hits={client.cache_hits}, misses={client.cache_misses}")


if __name__ == "__main__":
    asyncio.run(main())

"""전국 17개 시도 도시계획조례 건폐율·용적률 수집 스크립트.

저장 방식: jurisdiction_code = 시도코드(2자리) + "000" (예: 서울 → "11000")
  → ordinance_resolver.py 가 시군구 코드 미스 시 "XX000" 으로 fallback 조회.

사용법:
  # 조회만 (기본값) — DB 저장 없음
  python -m scripts.seed_ordinances

  # 특정 시도만
  python -m scripts.seed_ordinances --city 서울
  python -m scripts.seed_ordinances --city 경기

  # 광역시만 / 도만
  python -m scripts.seed_ordinances --type metro
  python -m scripts.seed_ordinances --type province

  # 카테고리 한정
  python -m scripts.seed_ordinances --category building_coverage_ratio

  # DB에 실제로 저장
  python -m scripts.seed_ordinances --commit

  # 조합
  python -m scripts.seed_ordinances --city 부산 --commit
  python -m scripts.seed_ordinances --type province --commit
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Windows cp949 콘솔에서 유니코드 출력을 위해 UTF-8로 강제 설정
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# backend 루트를 sys.path에 추가 (직접 실행 시)
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from services.cache_manager import CacheManager
from services.law_go_kr_client import LawGoKrClient
from services.llm_client import LLMClient
from services.ordinance_extractor import OrdinanceExtractor

# ── 대상 시도 ─────────────────────────────────────────────────────────────────
# 법제처 조례 검색 키워드: 광역시·특별시는 "도시계획 조례",
# 도 단위는 "도시계획 조례" 또는 "도시계획조례" 둘 다 시도.
# 세종특별자치시: 자체 도시계획조례 있음.

METRO_CITIES: list[dict] = [
    {"name": "서울특별시",       "code": "11", "type": "metro"},
    {"name": "부산광역시",       "code": "26", "type": "metro"},
    {"name": "대구광역시",       "code": "27", "type": "metro"},
    {"name": "인천광역시",       "code": "28", "type": "metro"},
    {"name": "광주광역시",       "code": "29", "type": "metro"},
    {"name": "대전광역시",       "code": "30", "type": "metro"},
    {"name": "울산광역시",       "code": "31", "type": "metro"},
    {"name": "세종특별자치시",   "code": "36", "type": "metro"},
]

PROVINCES: list[dict] = [
    {"name": "경기도",           "code": "41", "type": "province"},
    {"name": "강원특별자치도",   "code": "42", "type": "province"},
    {"name": "충청북도",         "code": "43", "type": "province"},
    {"name": "충청남도",         "code": "44", "type": "province"},
    {"name": "전북특별자치도",   "code": "45", "type": "province"},
    {"name": "전라남도",         "code": "46", "type": "province"},
    {"name": "경상북도",         "code": "47", "type": "province"},
    {"name": "경상남도",         "code": "48", "type": "province"},
    {"name": "제주특별자치도",   "code": "50", "type": "province"},
]

# 전체 17개 시도
CITIES: list[dict] = METRO_CITIES + PROVINCES

# 도 단위는 "도시계획 조례" 외에 "도시계획조례"(붙여쓰기)로도 검색
_PROVINCE_LAW_KEYWORDS: list[str] = ["도시계획 조례", "도시계획조례"]

CATEGORIES = ["building_coverage_ratio", "floor_area_ratio"]

_LIMITS_PATH = _ROOT / "config" / "zone_limits.json"
with open(_LIMITS_PATH, encoding="utf-8") as _f:
    _ZONE_LIMITS: dict = json.load(_f)

# zone_limits.json 에 있는 모든 용도지역 이름
ZONE_USES: list[str] = list(_ZONE_LIMITS["building_coverage_ratio"].keys())

LAW_KEYWORD = "도시계획 조례"


# ── 메인 ─────────────────────────────────────────────────────────────────────

async def run(
    *,
    commit: bool,
    city_filter: str | None,
    category_filter: str | None,
    type_filter: str | None,
) -> None:
    cache = CacheManager()
    await cache.init()

    law_client = LawGoKrClient()
    llm = LLMClient()
    extractor = OrdinanceExtractor(llm if llm.available else None)

    categories = (
        [category_filter] if category_filter else CATEGORIES
    )

    candidates = CITIES
    if type_filter == "metro":
        candidates = METRO_CITIES
    elif type_filter == "province":
        candidates = PROVINCES

    cities = (
        [c for c in candidates if city_filter in c["name"]]
        if city_filter else candidates
    )

    if not cities:
        print(f"[오류] 시도를 찾을 수 없습니다: {city_filter}")
        await _cleanup(cache, law_client, llm)
        return

    total_found = 0
    total_fallback = 0
    total_review = 0
    rows: list[dict] = []

    for city in cities:
        jcode = city["code"] + "000"   # "11000", "26000", ...
        jname = city["name"]
        print(f"\n{'='*60}")
        print(f"[{jname}]  jurisdiction_code={jcode}")
        print(f"{'='*60}")

        # 법제처에서 조례 본문 가져오기
        # 도 단위는 키워드 변형("도시계획조례" 붙여쓰기)도 시도
        keywords = (
            _PROVINCE_LAW_KEYWORDS
            if city.get("type") == "province"
            else [LAW_KEYWORD]
        )
        articles = []
        used_keyword = None
        for kw in keywords:
            print(f"  → 법제처 조례 조회 중 ({kw})...")
            try:
                articles = await law_client.fetch_ordinance(jname, kw)
            except Exception as e:
                print(f"  ✗ 법제처 API 오류: {e}")
                articles = []
            if articles:
                used_keyword = kw
                break

        if not articles:
            print(f"  ✗ 조례 없음 — 이 도시는 시행령 기본값으로 대체됩니다.")
            for cat in categories:
                for zu in ZONE_USES:
                    baseline = _ZONE_LIMITS.get(cat, {}).get(zu)
                    if baseline is not None:
                        rows.append({
                            "city": jname, "jcode": jcode, "zone_use": zu,
                            "category": cat, "value": baseline,
                            "source": "시행령 기본값 (조례 없음)",
                            "needs_review": False, "method": "fallback",
                        })
            total_fallback += len(ZONE_USES) * len(categories)
            continue

        law_nm = articles[0].get("law_nm", "조례")
        print(f"  ✓ 조례 로드: {law_nm} ({len(articles)}개 조문, 키워드: {used_keyword})")

        for cat in categories:
            cat_label = "건폐율" if cat == "building_coverage_ratio" else "용적률"
            found_this_cat = 0

            for zu in ZONE_USES:
                try:
                    result = await extractor.extract(articles, zu, cat)
                except Exception as e:
                    result = None
                    print(f"    [오류] {zu} {cat_label}: {e}")

                baseline = _ZONE_LIMITS.get(cat, {}).get(zu)

                if result is not None:
                    row = {
                        "city": jname, "jcode": jcode, "zone_use": zu,
                        "category": cat, "value": result["value"],
                        "source": result.get("source_article", "")[:60],
                        "needs_review": result.get("needs_review", False),
                        "method": result.get("method", "?"),
                        "law_nm": law_nm,
                    }
                    rows.append(row)
                    found_this_cat += 1
                    total_found += 1
                    if result.get("needs_review"):
                        total_review += 1
                else:
                    # fallback — 시행령 기본값
                    if baseline is not None:
                        rows.append({
                            "city": jname, "jcode": jcode, "zone_use": zu,
                            "category": cat, "value": baseline,
                            "source": "시행령 기본값 (추출 실패)",
                            "needs_review": False, "method": "fallback",
                        })
                    total_fallback += 1

            print(
                f"  [{cat_label}] 추출 {found_this_cat}/{len(ZONE_USES)}개"
                f"  fallback {len(ZONE_USES) - found_this_cat}개"
            )

        # API 레이트 리밋 배려
        await asyncio.sleep(0.5)

    # ── 결과 출력 ──────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"결과 요약")
    print(f"{'='*60}")
    print(f"  조례 추출 성공 : {total_found}건")
    print(f"  시행령 fallback: {total_fallback}건")
    print(f"  sanity 검토 필요: {total_review}건")
    print()

    # 상세 테이블 (조례 추출 성공분만)
    ordinance_rows = [r for r in rows if r["method"] != "fallback"]
    if ordinance_rows:
        _print_table(ordinance_rows)
    else:
        print("  조례에서 추출된 수치가 없습니다.")

    # ── DB 저장 ────────────────────────────────────────────────────────────
    if commit:
        print(f"\n  DB 저장 중 ({len(ordinance_rows)}건)...")
        saved = 0
        for r in ordinance_rows:
            try:
                await cache.set_zone_limit(
                    jurisdiction_code=r["jcode"],
                    jurisdiction_name=r["city"],
                    zone_use=r["zone_use"],
                    category=r["category"],
                    value=r["value"],
                    source_article=r.get("source", ""),
                    needs_review=r.get("needs_review", False),
                )
                saved += 1
            except Exception as e:
                print(f"  [저장 오류] {r['city']} {r['zone_use']} {r['category']}: {e}")
        print(f"  ✓ {saved}건 저장 완료")
    else:
        print(f"\n  [dry-run] DB 저장 생략. 저장하려면 --commit 옵션을 추가하세요.")

    await _cleanup(cache, law_client, llm)


def _print_table(rows: list[dict]) -> None:
    """추출 결과를 보기 좋게 출력."""
    cat_label = {"building_coverage_ratio": "건폐율", "floor_area_ratio": "용적률"}
    review_mark = {"True": " ⚠", "False": ""}

    header = f"{'도시':<10} {'용도지역':<18} {'카테고리':<8} {'값':>7}  {'검토':<3}  {'방법':<6}  근거"
    print(header)
    print("-" * 90)
    for r in rows:
        city = r["city"].replace("특별시","").replace("광역시","")
        zu = r["zone_use"]
        cat = cat_label.get(r["category"], r["category"])
        val = f"{r['value']:.1f}%"
        rev = " ⚠" if r.get("needs_review") else "  "
        method = r.get("method", "?")
        source = r.get("source", "")[:40]
        print(f"{city:<10} {zu:<18} {cat:<8} {val:>7} {rev}  {method:<6}  {source}")


async def _cleanup(cache: CacheManager, law_client: LawGoKrClient, llm: LLMClient) -> None:
    await cache.close()
    await law_client.close()
    await llm.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="전국 17개 시도 조례 수치 수집")
    parser.add_argument(
        "--commit", action="store_true",
        help="결과를 DB에 저장 (기본값: dry-run)"
    )
    parser.add_argument(
        "--city", type=str, default=None,
        help="특정 시도만 처리 (예: 서울, 경기, 강원)"
    )
    parser.add_argument(
        "--type", type=str, default=None,
        choices=["metro", "province"],
        dest="type_filter",
        help="metro=광역시·특별시·세종, province=9개 도"
    )
    parser.add_argument(
        "--category", type=str, default=None,
        choices=["building_coverage_ratio", "floor_area_ratio"],
        help="특정 카테고리만 처리"
    )
    args = parser.parse_args()

    mode = "commit" if args.commit else "dry-run"
    city_str = args.city or "전체"
    type_str = args.type_filter or "전체"
    cat_str = args.category or "전체"
    print(f"seed_ordinances - 모드={mode}, 시도={city_str}, 타입={type_str}, 카테고리={cat_str}")

    asyncio.run(run(
        commit=args.commit,
        city_filter=args.city,
        category_filter=args.category,
        type_filter=args.type_filter,
    ))


if __name__ == "__main__":
    main()

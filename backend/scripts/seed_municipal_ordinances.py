"""시군구 도시계획조례 수집 스크립트 (전국 시군구 대상).

기존 seed_ordinances.py(17개 시도)와 분리. 시군구는:
  - 법제처 자치법규 검색 결과에서 '{시군구명} 도시계획 조례' 정확 매칭 우선
  - 비슷한 이름 조례(예: '수원시 도시계획변경 사전협상...')와 구분 필요
  - 결과는 ordinance_zone_limits 에 시군구 5자리 코드로 저장
  - 자치구(parent 있는 항목)는 시 단위 조례 값을 그대로 broadcast 저장

매핑 표(시군구 5자리 ↔ 이름)는 config/municipal_codes.json 참조.
  - parent=null  → 시 단위 (조례 fetch 대상)
  - parent="..." → 자치구 (시 코드의 조례 값 broadcast)

사용법:
  # 시범 (수원시 1곳, dry-run)
  python -m scripts.seed_municipal_ordinances --city 수원시

  # 경기도 전체, dry-run
  python -m scripts.seed_municipal_ordinances --sido 경기도

  # 실제 저장
  python -m scripts.seed_municipal_ordinances --city 수원시 --commit
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from services.cache_manager import CacheManager
from services.law_go_kr_client import LawGoKrClient
from services.llm_client import LLMClient
from services.ordinance_extractor import OrdinanceExtractor

_LIMITS_PATH = _ROOT / "config" / "zone_limits.json"
with open(_LIMITS_PATH, encoding="utf-8") as _f:
    _ZONE_LIMITS: dict = json.load(_f)

ZONE_USES: list[str] = list(_ZONE_LIMITS["building_coverage_ratio"].keys())
CATEGORIES = ["building_coverage_ratio", "floor_area_ratio"]

_MUNI_PATH = _ROOT / "config" / "municipal_codes.json"


def _load_municipalities() -> list[dict]:
    """시군구 매핑 표 로드.

    municipal_codes.json 포맷:
      [{"code": "41115", "name": "수원시", "sido": "경기도"}, ...]
    """
    if not _MUNI_PATH.exists():
        return []
    with open(_MUNI_PATH, encoding="utf-8") as f:
        return json.load(f)


async def _find_exact_ordinance(
    law_client: LawGoKrClient, muni_name: str
) -> tuple[str, str] | None:
    """시군구의 정확한 '도시계획 조례'(시) 또는 '군계획 조례'(군) 검색.

    Args:
      muni_name: 예 "수원시", "연천군"

    매칭 우선순위:
      1) law_nm 공백 제거 == f"{muni_name}{키워드}" (정확 일치)
      2) law_nm 공백 제거.endswith(키워드) (시군구명 포함된 결과 중)
      3) 첫 번째 결과 폴백
    """
    # 시·군별 키워드 — 일부 군은 '관리계획 조례'(예: 장흥·무안) 사용
    if muni_name.endswith("군"):
        keywords = ["군계획 조례", "도시계획 조례", "관리계획 조례"]
        target_keywords = ["군계획조례", "도시계획조례", "관리계획조례"]
    else:
        keywords = ["도시계획 조례", "관리계획 조례"]
        target_keywords = ["도시계획조례", "관리계획조례"]

    seen_law_ids: set[str] = set()
    laws_all: list[dict] = []
    for kw in keywords:
        laws = await law_client.search_law(f"{muni_name} {kw}", law_type="CST")
        for l in laws:
            lid = l.get("law_id", "")
            if lid and lid not in seen_law_ids:
                seen_law_ids.add(lid)
                laws_all.append(l)

    if not laws_all:
        return None

    candidates_endswith: list[dict] = []
    for l in laws_all:
        # law_nm 정규화: 대괄호 메타텍스트 제거 (예: "...조례 [제명개정 2020.10.5.]")
        raw_nm = l.get("law_nm", "") or ""
        clean_nm = re.sub(r"\[[^\]]*\]", "", raw_nm).strip()
        nm_compact = clean_nm.replace(" ", "")
        org = l.get("org", "") or ""
        if muni_name not in org and muni_name not in nm_compact:
            continue
        for tk in target_keywords:
            if nm_compact == f"{muni_name}{tk}":
                return l["law_id"], raw_nm
            if nm_compact.endswith(tk):
                candidates_endswith.append(l)
                break
    if candidates_endswith:
        c = candidates_endswith[0]
        return c["law_id"], c["law_nm"]
    return None


async def _extract_for_city(
    muni: dict,
    law_client: LawGoKrClient,
    extractor: OrdinanceExtractor,
) -> tuple[str, list[dict]] | None:
    """시 단위 1곳에 대해 조례 fetch + 추출 → (law_nm, rows).

    rows 의 code/name 은 입력 시 단위 muni 기준. 자치구 broadcast 는 호출자에서.
    """
    code = muni["code"]
    name = muni["name"]
    found = await _find_exact_ordinance(law_client, name)
    if not found:
        print(f"  ✗ '{name} 도시계획 조례' 미발견 — 시도 fallback 으로 진단됨")
        return None
    law_id, law_nm = found
    print(f"  ✓ 조례 발견: {law_nm} (law_id={law_id})")

    arts = await law_client.get_law_articles(law_id, law_type="CST")
    if not arts:
        print(f"  ✗ 본문 0건 — 추출 불가")
        return None

    whole = "\n".join(a.get("content","") for a in arts)
    pct_count = len(re.findall(r"\d+퍼센트", whole))
    print(f"  본문 {len(arts)}개 조문, 퍼센트 패턴 {pct_count}회")

    rows: list[dict] = []
    for cat in CATEGORIES:
        cat_label = "건폐율" if cat == "building_coverage_ratio" else "용적률"
        cat_found = 0
        for zu in ZONE_USES:
            try:
                result = await extractor.extract(arts, zu, cat)
            except Exception as e:
                print(f"    [추출 오류] {zu} {cat_label}: {e}")
                result = None
            if result is not None:
                rows.append({
                    "code": code, "name": name, "zone_use": zu, "category": cat,
                    "value": result["value"],
                    "source_article": (result.get("source_article") or "")[:120],
                    "needs_review": bool(result.get("needs_review", False)),
                })
                cat_found += 1
        print(f"  [{cat_label}] {cat_found}/{len(ZONE_USES)}개 추출")
    return law_nm, rows


async def _save_rows(rows: list[dict], cache: CacheManager) -> int:
    saved = 0
    for r in rows:
        try:
            await cache.set_zone_limit(
                jurisdiction_code=r["code"],
                jurisdiction_name=r["name"],
                zone_use=r["zone_use"],
                category=r["category"],
                value=r["value"],
                source_article=r["source_article"],
                needs_review=r["needs_review"],
                is_estimate=False,
            )
            saved += 1
        except Exception as e:
            print(f"  [저장 오류] {r['code']} {r['zone_use']} {r['category']}: {e}")
    return saved


async def run(*, commit: bool, city: str | None, sido: str | None,
              limit: int | None) -> None:
    munis_all = _load_municipalities()
    if not munis_all:
        print(f"[오류] {_MUNI_PATH} 가 없습니다.")
        print("       시군구 매핑 표를 먼저 작성하세요.")
        return

    # 필터링 — 부모(시)와 자식(자치구) 함께 유지
    filtered = munis_all
    if city:
        filtered = [m for m in filtered if city in m["name"]]
    if sido:
        filtered = [m for m in filtered if sido in m.get("sido", "")]
    if limit:
        filtered = filtered[:limit]
    if not filtered:
        print(f"[오류] 시군구를 찾을 수 없습니다: city={city} sido={sido}")
        return

    # 시 단위만 처리 대상 (parent=null). 자치구는 broadcast.
    cities = [m for m in filtered if m.get("parent") is None]
    # 코드 → 자치구 리스트 매핑 (broadcast 용)
    children_map: dict[str, list[dict]] = {}
    for m in munis_all:
        if m.get("parent"):
            children_map.setdefault(m["parent"], []).append(m)

    print(f"대상 시 단위: {len(cities)}개, "
          f"자치구 broadcast 포함  모드: {'COMMIT' if commit else 'dry-run'}")

    cache = CacheManager()
    await cache.init()
    law_client = LawGoKrClient()
    llm = LLMClient()
    extractor = OrdinanceExtractor(llm if llm.available else None)

    summary = []
    for m in cities:
        print(f"\n{'='*60}")
        print(f"[{m.get('sido','')} {m['name']}] code={m['code']}")
        print(f"{'='*60}")
        try:
            res = await _extract_for_city(m, law_client, extractor)
        except Exception as e:
            print(f"  [예외] {e}")
            summary.append({"name": m["name"], "code": m["code"],
                            "status": f"error: {e}",
                            "extracted": 0, "broadcast": 0})
            continue

        if res is None:
            summary.append({"name": m["name"], "code": m["code"],
                            "status": "no_ordinance",
                            "extracted": 0, "broadcast": 0})
            continue

        law_nm, rows = res
        # 자치구 broadcast — 시 코드 row 를 자식 코드로 복제
        kids = children_map.get(m["code"], [])
        all_rows = list(rows)
        for r in rows:
            for kid in kids:
                all_rows.append({
                    **r,
                    "code": kid["code"], "name": kid["name"],
                })

        if commit and all_rows:
            saved = await _save_rows(all_rows, cache)
            print(f"  ✓ DB 저장 {saved}건 (시 {len(rows)} + 자치구 {len(all_rows)-len(rows)})")

        summary.append({
            "name": m["name"], "code": m["code"], "status": "ok",
            "extracted": len(rows), "broadcast": len(all_rows) - len(rows),
            "law_nm": law_nm,
        })
        await asyncio.sleep(0.3)

    print(f"\n{'='*60}\n결과 요약\n{'='*60}")
    for s in summary:
        print(f"  {s['code']} {s['name']:<10} {s['status']:<14} "
              f"추출={s['extracted']:>3}, broadcast={s.get('broadcast',0):>3}")

    ok_count = sum(1 for s in summary if s['status'] == 'ok')
    print(f"\n  ✓ 성공: {ok_count}/{len(cities)}")

    await cache.close()
    await law_client.close()
    await llm.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--commit", action="store_true")
    p.add_argument("--city", type=str, default=None, help="시군구명 (예: 수원시)")
    p.add_argument("--sido", type=str, default=None, help="시도명 (예: 경기도)")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()
    asyncio.run(run(commit=args.commit, city=args.city, sido=args.sido,
                    limit=args.limit))


if __name__ == "__main__":
    main()

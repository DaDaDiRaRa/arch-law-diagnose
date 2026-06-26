"""법규 그래프 자동 수확 (Step 11 #1).

법제처 DRF API로 시드 조문의 본문을 가져와 상호참조(「법」 제N조 / 제N조 / 별표 N)를
추출하고, config/law_graph_auto.json 으로 저장한다. law_graph._build()가 이 파일이
있으면 자동 병합한다(origin="auto"로 태깅 → UI에서 시드(검증)와 구분 표시).

⚠ 본문 정규식 추출은 부정확할 수 있다. 자동 병합된 엣지는 모두 origin="auto"·rel="참조"로
표시되며, 검증된 시드 관계와 시각적으로 구분된다.

실행(온디맨드, LAW_API_KEY 필요):
    cd backend && python -m services.law_graph_harvest
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_SEED_PATH = Path(__file__).parent.parent / "config" / "law_graph_seed.json"
_AUTO_PATH = Path(__file__).parent.parent / "config" / "law_graph_auto.json"

# 시드 statute 노드의 law 이름 → 법제처 검색 키워드 (정식 명칭)
_LAW_SEARCH_KEYWORD = {
    "건축법": "건축법",
    "건축법 시행령": "건축법 시행령",
    "국토계획법": "국토의 계획 및 이용에 관한 법률",
    "국토계획법 시행령": "국토의 계획 및 이용에 관한 법률 시행령",
    "주차장법": "주차장법",
    "녹색건축물 조성 지원법": "녹색건축물 조성 지원법",
}

_NAMED = re.compile(r"「([^」]{2,40})」\s*제(\d+)조(?:의(\d+))?")
_BARE = re.compile(r"제(\d+)조(?:의(\d+))?")
_BYP = re.compile(r"별표\s*(\d+)")


def _art(num: str, sub: str | None) -> str:
    return f"제{num}조" + (f"의{sub}" if sub else "")


def _art_key(article_no: str) -> tuple[int, int]:
    """법제처 6자리 조문번호 → (조, 의). 예) '005600'→(56,0), '005302'→(53,2)."""
    s = article_no.zfill(6)
    return (int(s[:4]), int(s[4:]))


def extract_refs(text: str, current_law: str, self_article: str | None = None) -> list[dict]:
    """조문 본문 → 상호참조 목록 [{law, article, kind}].

    kind: named(「법」 제N조) | same(같은 법 제N조) | byp(별표 N).
    self_article: 해당 조문 자신(자기참조 제외용).
    """
    refs: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(law: str, art: str, kind: str) -> None:
        key = (law, art)
        if key in seen:
            return
        seen.add(key)
        refs.append({"law": law, "article": art, "kind": kind})

    for m in _NAMED.finditer(text or ""):
        add(m.group(1).strip(), _art(m.group(2), m.group(3)), "named")

    # 명시 법령 참조를 지운 뒤 같은 법 내 조문 참조 스캔(중복 방지)
    wo_named = _NAMED.sub("  ", text or "")
    for m in _BARE.finditer(wo_named):
        art = _art(m.group(1), m.group(2))
        if art != self_article:
            add(current_law, art, "same")

    for m in _BYP.finditer(text or ""):
        add(current_law, f"별표 {m.group(1)}", "byp")

    return refs


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _seed_index(seed: dict) -> dict[tuple[str, str], str]:
    """(정규화 law, 정규화 article) → 시드 노드 id."""
    idx = {}
    for n in seed.get("nodes", []):
        if n.get("article"):
            idx[(_norm(n["law"]), _norm(n["article"]))] = n["id"]
    return idx


async def harvest(client) -> dict:
    """시드 statute 조문 본문에서 상호참조를 수확 → {nodes, edges} (origin=auto).

    client: LawGoKrClient 인스턴스.
    """
    with open(_SEED_PATH, encoding="utf-8") as f:
        seed = json.load(f)
    seed_idx = _seed_index(seed)

    # 수확 대상: 시드의 법률/시행령 노드, law별로 묶기
    statutes: dict[str, list[dict]] = {}
    for n in seed.get("nodes", []):
        if n.get("kind") in ("법률", "시행령") and n.get("article", "").startswith("제"):
            statutes.setdefault(n["law"], []).append(n)

    auto_nodes: dict[str, dict] = {}
    auto_edges: list[dict] = []
    seen_edges: set[tuple[str, str]] = set()

    for law, nodes in statutes.items():
        keyword = _LAW_SEARCH_KEYWORD.get(law)
        if not keyword:
            continue
        found = await client.search_law(keyword, law_type="LAW")
        if not found:
            logger.warning("[harvest] 검색 실패: %s", law)
            continue
        articles = await client.get_law_articles(found[0]["law_id"], "LAW")
        # 조문번호는 6자리 인코딩: 앞 4=조, 뒤 2=의(서브). 예) 제56조=005600, 제53조의2=005302
        by_key = {
            _art_key(a["article_no"]): a
            for a in articles if (a.get("article_no") or "").isdigit()
        }

        for node in nodes:
            m = re.match(r"제(\d+)조(?:의(\d+))?", node["article"])
            if not m:
                continue
            art = by_key.get((int(m.group(1)), int(m.group(2) or 0)))
            if not art or not art.get("content"):
                continue
            refs = extract_refs(art["content"], law, self_article=node["article"])
            for r in refs:
                tgt_id = seed_idx.get((_norm(r["law"]), _norm(r["article"])))
                if tgt_id is None:
                    # 새 자동 노드
                    tgt_id = "auto_" + _norm(f"{r['law']}_{r['article']}")
                    auto_nodes.setdefault(tgt_id, {
                        "id": tgt_id, "kind": "법률" if "시행령" not in r["law"] else "시행령",
                        "law": r["law"], "article": r["article"], "title": "",
                        "url": f"https://www.law.go.kr/법령/{r['law']}/{r['article']}",
                        "origin": "auto",
                    })
                if tgt_id == node["id"]:
                    continue
                ek = (node["id"], tgt_id)
                if ek in seen_edges:
                    continue
                seen_edges.add(ek)
                auto_edges.append({
                    "source": node["id"], "target": tgt_id,
                    "rel": "참조", "note": f"본문 자동 추출({r['kind']})", "origin": "auto",
                })

    return {"nodes": list(auto_nodes.values()), "edges": auto_edges}


def write_auto(data: dict, path: Path = _AUTO_PATH) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[harvest] 자동 그래프 저장: 노드 %d · 엣지 %d → %s",
                len(data.get("nodes", [])), len(data.get("edges", [])), path)


async def _main() -> None:
    logging.basicConfig(level="INFO")
    from services.law_go_kr_client import LawGoKrClient
    client = LawGoKrClient()
    try:
        data = await harvest(client)
        write_auto(data)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(_main())

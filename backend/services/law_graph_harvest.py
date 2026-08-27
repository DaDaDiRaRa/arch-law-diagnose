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

# 법령 앵커 — 「법령명」 / "같은 법"(직전 명시 법령) / "법"(시행령 본문의 모법 약칭).
# 마지막 대안은 뒤에 "제N조"가 붙을 때만, 그리고 앞 글자가 한글이 아닐 때만 잡는다
# (안 그러면 "건축법"·"주차장법"의 꼬리 '법'이 걸린다).
_ANCHOR = re.compile(
    r"「([^」]{2,40})」"
    r"|(같은\s*법)"
    r"|(?<![가-힣])(법)(?=\s*제\d+조)"
)
_ART = re.compile(r"제(\d+)조(?:의(\d+))?")
_BYP = re.compile(r"별표\s*(\d+)")

# 조문 나열의 연결부 — 이것만 사이에 있으면 앞의 법령 문맥이 계속된다.
# 예) "「건축법」 제60조 및 제61조", "제6조, 제7조, 제7조의2 및 제8조"
_CONNECTOR = re.compile(
    r"^[\s,，、·ㆍ]*(?:(?:및|과|와|또는|내지|부터|까지)[\s,，、·ㆍ]*)*$"
)


# 정식명칭 → 시드 약칭. 위 검색 키워드 표를 뒤집어 쓴다(표가 유일한 출처).
# 본문 인용은 정식명칭(「국토의 계획 및 이용에 관한 법률」), 시드는 약칭(국토계획법)이라
# 정규화하지 않으면 같은 조문이 노드 둘로 갈라진다.
_LAW_ALIAS = {
    re.sub(r"\s+", "", formal): short
    for short, formal in _LAW_SEARCH_KEYWORD.items()
    if re.sub(r"\s+", "", formal) != re.sub(r"\s+", "", short)
}


def _canon_law(law: str) -> str:
    """법령명을 시드 표기로 통일. 표에 없으면 원문 그대로."""
    return _LAW_ALIAS.get(re.sub(r"\s+", "", law or ""), law)


def _parent_act(law: str) -> str:
    """시행령·시행규칙 → 모법. 그 외는 자기 자신.

    시행령 본문의 "법 제N조"는 모법 조문을 가리킨다(입법 관행). 이걸 모르면
    "건축법 시행령 제13조의2"처럼 실재하지 않는 조문이 만들어진다.
    """
    return re.sub(r"\s*(시행령|시행규칙)$", "", law).strip() or law


def _art(num: str, sub: str | None) -> str:
    return f"제{num}조" + (f"의{sub}" if sub else "")


def _art_key(article_no: str) -> tuple[int, int]:
    """법제처 6자리 조문번호 → (조, 의). 예) '005600'→(56,0), '005302'→(53,2)."""
    s = article_no.zfill(6)
    return (int(s[:4]), int(s[4:]))


def extract_refs(text: str, current_law: str, self_article: str | None = None) -> list[dict]:
    """조문 본문 → 상호참조 목록 [{law, article, kind}].

    kind: named(다른 법령 조문) | same(같은 법 조문) | byp(별표 N).
    self_article: 해당 조문 자신(자기참조 제외용).

    법령 문맥을 좌→우로 이어가며 조문을 귀속시킨다. 앵커(「법령명」·"같은 법"·
    시행령의 "법") 이후 **연결부(, · 및 …)로만 이어진 조문은 그 법령 소속**이다.
    나열 중 첫 조문만 법령에 붙이면 뒤따르는 조문이 현재 법으로 잘못 떨어진다
    (예: "「건축법」 제60조 및 제61조" → 제61조가 녹색건축물법 제61조가 됨).
    """
    text = text or ""
    refs: list[dict] = []
    seen: set[tuple[str, str]] = set()
    current_law = _canon_law(current_law)
    parent = _canon_law(_parent_act(current_law))

    def add(law: str, art: str, kind: str) -> None:
        key = (law, art)
        if key in seen:
            return
        seen.add(key)
        refs.append({"law": law, "article": art, "kind": kind})

    # 앵커·조문을 위치 순으로 병합 주사
    events: list[tuple[int, int, str, str]] = []  # (start, end, type, payload)
    last_named = ""
    for m in _ANCHOR.finditer(text):
        if m.group(1):
            law = _canon_law(m.group(1).strip())
            last_named = law
        elif m.group(2):
            law = last_named or current_law      # "같은 법" = 직전 명시 법령
        else:
            law = parent                         # 시행령의 "법" = 모법
        events.append((m.start(), m.end(), "anchor", law))
    for m in _ART.finditer(text):
        events.append((m.start(), m.end(), "art", _art(m.group(1), m.group(2))))
    events.sort(key=lambda e: (e[0], 0 if e[2] == "anchor" else 1))

    active_law = ""      # 현재 이어지는 법령 문맥
    active_end = 0       # 그 문맥이 끝난 위치(여기부터 조문까지가 연결부여야 이어짐)
    for start, end, typ, payload in events:
        if typ == "anchor":
            active_law, active_end = payload, end
            continue
        # 조문 — 앞 문맥과 연결부로만 이어져 있으면 그 법령, 아니면 현재 법
        if active_law and _CONNECTOR.match(text[active_end:start]):
            law = active_law
        else:
            law = current_law
        active_law, active_end = law, end
        if law == current_law:
            if payload == self_article:
                continue
            add(law, payload, "same")
        else:
            add(law, payload, "named")

    for m in _BYP.finditer(text):
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
    from services.law_graph_curate import load_rejected_sets

    with open(_SEED_PATH, encoding="utf-8") as f:
        seed = json.load(f)
    seed_idx = _seed_index(seed)
    # 이미 시드에 있는 엣지·반려된 항목은 재수확하지 않음(승격/반려 결과 유지)
    seed_edges = {(e.get("source"), e.get("target")) for e in seed.get("edges", [])}
    rejected_nodes, rejected_edges = load_rejected_sets()

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
                    # 새 자동 노드 후보 (반려된 노드면 건너뜀)
                    tgt_id = "auto_" + _norm(f"{r['law']}_{r['article']}")
                    if tgt_id in rejected_nodes:
                        continue
                    auto_nodes.setdefault(tgt_id, {
                        "id": tgt_id, "kind": "법률" if "시행령" not in r["law"] else "시행령",
                        "law": r["law"], "article": r["article"], "title": "",
                        "url": f"https://www.law.go.kr/법령/{r['law']}/{r['article']}",
                        "origin": "auto",
                    })
                if tgt_id == node["id"]:
                    continue
                ek = (node["id"], tgt_id)
                if ek in seen_edges or ek in seed_edges or ek in rejected_edges:
                    continue  # 중복·이미 승격(seed)·반려된 엣지는 제외
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

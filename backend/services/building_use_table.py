"""건축법 시행령 [별표 1] 「용도별 건축물의 종류」 파서 + 조회.

⚠ **런타임에 PDF를 파싱하지 않는다.** CLAUDE.md 가드레일에 따라 별표 PDF 에서
뽑은 값은 `config/building_use_seed.json` 으로 **전사**해 두고, 코드는 그 seed 만
읽는다. seed 가 현행 별표와 일치하는지는 `scripts/verify_building_use_seed.py`
가 재다운로드해 전수 대조한다.

파서(`parse_byeolpyo1`)를 여기 두는 이유는 build/verify 두 스크립트가 **같은 파서**를
써야 대조가 의미 있기 때문이다(빌드용·검증용 파서가 따로면 둘이 같이 틀린다).

분류 원칙 — 애매하면 자동 채움 안 함(`zone_use_normalizer` 와 같은 태도):
  · safe        단일 용도군 + 무조건  → 자동 채움 가능
  · conditional 면적·제외규정에 걸림   → 힌트만(예: 보건소는 1천㎡ 미만이면 제1종근생,
                                       넘으면 업무시설. 이름만으론 못 정한다)
  · ambiguous   2개 이상 용도군에 등장 → 힌트만(예: 학원 = 교육연구시설 or 제2종근생)
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

_SEED_PATH = Path(__file__).parent.parent / "config" / "building_use_seed.json"

# ── 파서 ─────────────────────────────────────────────────────────────────────
# PDF 는 단어 중간에서 줄을 끊는다("단\n독주택"). 항목 마커로 시작하는 줄에서만
# 끊고 나머지는 공백 없이 이어 붙여야 단어가 복원된다.
_MARK = re.compile(r"^(?:\d{1,2}\.|[가-힣]\.|\d\))\s")
_GROUP = re.compile(r"^(\d{1,2})\.\s*(.+)$")
_SUB = re.compile(r"^(?:[가-힣]\.|\d\))\s*(.+)$")      # "가." 와 "1)" 둘 다
_SEP = re.compile(r"\s*(?:,|·|ᆞ|ㆍ|및|또는)\s*")
# 이름이 아니라 설명·단서인 조각을 걸러낸다
_DROP = re.compile(
    r"제외|해당하지|아니하는|비슷한|그 밖에|말한다|포함한다|다음|요건|이하|이상|미만"
    r"|경우|것으로서|위하여|한정|각 목|준하는"
)
# 이 표현이 있으면 그 항목의 이름들은 조건부(면적·용도 단서에 걸림)
_COND = re.compile(r"바닥면적|제곱미터|미만|이상|이하|제외|해당하지\s*아니|한정")
_BAD = re.compile(r"[0-9「」()\[\]%]")
_GROUPS_EXPECTED = 29


def _clean_head(s: str) -> str:
    """용도군명 = '시설|주택|공장' 으로 끝나는 최단 접두.

    헤딩 뒤에 본문이 붙어 나오는 항목이 있다("공장물품의 제조·가공" → "공장").
    """
    m = re.search(r"^(.*?(?:시설|주택|공장))", s)
    return (m.group(1) if m else s).strip()


def _strip_ref(x: str) -> str:
    x = re.sub(r"「[^」]*」", " ", x)          # 인용 법령명 제거
    x = re.sub(r"\s*에\s*따른\s*", " ", x)
    return x


def _clean_name(x: str) -> str:
    x = _strip_ref(x)
    x = re.split(r"으로서|로서|(?<=[가-힣])\s+중\s+", x)[0]
    x = x.strip().strip(".,·ᆞ:; ").strip()
    return re.sub(r"^(?:그|이|해당|각종)\s+", "", x)


# 괄호 안은 "A, B, C 그 밖에 …에 해당하지 아니하는 것을 말한다" 꼴이 흔하다.
# 뒷부분은 **제외 대상**이라 그대로 긁으면 남의 용도군 이름이 딸려 들어온다
# (노유자시설 괄호의 "단독주택, 공동주택"이 노유자시설 시설명이 돼 버렸다).
_ENUM_CUT = re.compile(r"그\s*밖에|으로서|로서|에\s*해당하지|[을를]\s*제외|[은는]\s*제외")


def _enum_head(inner: str) -> str:
    """괄호 안 열거에서 **실제 열거 부분만** 남긴다(제외·유사 문구 앞에서 자른다)."""
    m = _ENUM_CUT.search(inner)
    if m:
        inner = inner[:m.start()]
    return re.sub(r"(을|를)\s*(말한다|포함한다).*$", "", inner)


def _is_name(x: str) -> bool:
    return (2 <= len(x) <= 14 and not _BAD.search(x) and not _DROP.search(x)
            and re.fullmatch(r"[가-힣\s]+", x) is not None)


def parse_byeolpyo1(text: str) -> dict:
    """별표1 PDF 텍스트 → {groups, names, conditional}.

    Returns:
      groups: {번호(int): 용도군명}  — 29개
      names:  {시설명: [용도군명, ...]}
      conditional: [면적·제외규정에 걸린 시설명]
    """
    lines: list[str] = []
    buf = ""
    for raw in (text or "").split("\n"):
        ln = raw.strip()
        if not ln:
            continue
        if _MARK.match(ln):
            if buf:
                lines.append(buf)
            buf = ln
        else:
            buf += ln                      # 단어 중간 줄바꿈 → 공백 없이 이어 붙임
    if buf:
        lines.append(buf)

    groups: dict[int, str] = {}
    subs: dict[int, list[str]] = defaultdict(list)
    cur: int | None = None
    for ln in lines:
        m = _GROUP.match(ln)
        if m and 1 <= int(m.group(1)) <= _GROUPS_EXPECTED and int(m.group(1)) not in groups:
            cur = int(m.group(1))
            groups[cur] = _clean_head(m.group(2))
            continue
        m = _SUB.match(ln)
        if m and cur:
            subs[cur].append(m.group(1).strip())

    names: dict[str, set[str]] = defaultdict(set)
    conditional: set[str] = set()
    for n, items in subs.items():
        g = groups[n]
        for raw in items:
            cond = bool(_COND.search(raw))
            cands = [re.split(r"[:(\[]", raw)[0]]                    # "X: ..." / "X(...)"
            for inner in re.findall(r"[(\[]([^)\]]*)[)\]]", raw):    # 괄호 안 열거
                if re.search(r"말한다|포함한다", inner):
                    cands += _SEP.split(_enum_head(inner))
            m = re.match(r"^([^:(\[]{2,150}?)\s*등\s", raw)          # "A, B, C 등 ..."
            if m:
                cands += _SEP.split(m.group(1))
            for c in cands:
                c = _clean_name(c)
                if _is_name(c):
                    names[c].add(g)
                    if cond:
                        conditional.add(c)

    return {
        "groups": {str(k): v for k, v in sorted(groups.items())},
        "names": {k: sorted(v) for k, v in sorted(names.items())},
        "conditional": sorted(conditional),
    }


# ── seed 조회 ────────────────────────────────────────────────────────────────
_CACHE: dict | None = None


def load_seed() -> dict:
    """전사된 seed 로드. 파일이 없으면 빈 구조(호출부는 graceful degrade)."""
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _CACHE = {"groups": {}, "names": {}, "conditional": []}
    return _CACHE


def use_groups() -> list[str]:
    """29개 용도군명. 긴 이름 우선 정렬 — 부분매칭 시 더 구체적인 것이 먼저 잡힌다."""
    g = list(load_seed().get("groups", {}).values())
    return sorted(g, key=len, reverse=True)


def safe_names() -> dict[str, str]:
    """{시설명: 용도군} — 단일 용도군 + 무조건인 것만. 자동 채움에 쓸 수 있다."""
    seed = load_seed()
    cond = set(seed.get("conditional", []))
    return {k: v[0] for k, v in seed.get("names", {}).items()
            if len(v) == 1 and k not in cond}


def hint_names() -> dict[str, list[str]]:
    """{시설명: [용도군,...]} — 조건부이거나 복수 용도군. 힌트로만 보여준다."""
    seed = load_seed()
    cond = set(seed.get("conditional", []))
    return {k: v for k, v in seed.get("names", {}).items()
            if len(v) > 1 or k in cond}

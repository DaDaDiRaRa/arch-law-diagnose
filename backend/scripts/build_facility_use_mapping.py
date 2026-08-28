"""시설용도 매핑표 재료 추출 — brief facilities 어휘 ↔ 건축법 시행령 별표1 대조.

목적: `brief_importer._BUILDING_USES`(우리 자동감지 목록)가 못 잡는 어휘를 모아
시니어가 채울 CSV 를 만든다. 산출물 → `data/facility_use_mapping.csv`.

⚠ `feasibility_export.building_law_uses` 를 읽으면 안 된다 — competition_comparison
추출 규칙이 "괄호 안 + '시설'로 끝나거나 '주택' 포함"만 취해 대부분을 버린다.
매핑표는 그 버려지는 어휘를 메우는 물건이라 `sites[].facilities` **원본**을 본다.
(그쪽 확인, 2026-08-28: 그 필드만 읽으면 12종 중 2종만 나온다.)

⚠ 공모 단위로 중복 제거한다. prod 30건은 실제로 **공모 8종**이고, 영등포 1건이
14회·대전 1건이 10회 재분석된 것이다. 파일 수로 세면 표본이 4배 부풀어 보인다.

분류:
  0. 이미 자동감지          — `_detect_building_uses` 가 잡음. 할 일 없음.
  A. 별표1에 있음            — 법정 시설명. **코드로 해결 가능**(별표1 파싱), 시니어 불필요.
  B. 별표1에 없음            — 공모지침 관용어(주민편의시설·부대복리시설 등). 진짜 사람 판단.
  C. 건축물 아님             — 도로·공원. 매핑 대상 아님.

실행 (LAW_API_KEY 필요 — 별표1 PDF 를 법제처에서 받는다):
    cd backend && .venv\Scripts\python.exe scripts\build_facility_use_mapping.py
"""
import csv, glob, json, os, re, sys
from collections import Counter, defaultdict
sys.path.insert(0, r'D:\APPS\arch-law-diagnose\backend')
from services.brief_importer import _BUILDING_USES, _detect_building_uses

byp1 = open(os.path.join(os.environ["TEMP"], "byp1.txt"), encoding="utf-8").read()

# 공모 어휘 수집 — 공모 단위 중복 제거(같은 공모 재분석분은 1회로)
PATS = [os.path.join(os.environ["TEMP"], "prod_briefs", "*.json"),
        r"C:\Temp\CompTestDB\_briefs\*.json",
        r"D:\APPS\arch-law-diagnose\data\briefs\*.json"]
by_comp = defaultdict(list); seen = set()
for pat in PATS:
    for p in sorted(glob.glob(pat)):
        k = os.path.basename(p)
        if k in seen: continue
        try: d = json.load(open(p, encoding="utf-8"))
        except Exception: continue
        pi = d.get("brief_project_info")
        if not isinstance(pi, dict): continue
        seen.add(k)
        by_comp[(pi.get("competition_name") or f"(무명){k}").strip()].append(pi.get("sites") or [])

vocab = Counter(); comps = defaultdict(set)
for name, runs in by_comp.items():
    terms = set()
    for sites in runs:
        for s in sites:
            if isinstance(s, dict):
                for f in s.get("facilities") or []:
                    if isinstance(f, str) and f.strip(): terms.add(f.strip())
    for t in terms:
        vocab[t] += 1; comps[t].add(name)

NOT_BUILDING = {"도로", "공원", "공원(어린이공원/소공원)"}

rows = []
for term, n in vocab.most_common():
    core = re.sub(r"\(.*?\)", "", term).strip()
    auto = _detect_building_uses([term])
    auto1 = auto[0] if len(auto) == 1 else ""
    inner = re.findall(r"\(([^)]*)\)", term)
    probe = [core] + [i.strip() for i in inner]
    in_byp1 = next((x for x in probe if x and x in byp1), "")
    if term in NOT_BUILDING:
        cls = "C. 건축물 아님(매핑 불필요)"
    elif auto1:
        cls = "0. 이미 자동감지"
    elif in_byp1:
        cls = "A. 별표1에 있음(코드로 해결 가능)"
    else:
        cls = "B. 별표1에 없음 — 시니어 판단 필요"
    rows.append([term, n, cls, auto1, in_byp1, ""])

out = os.path.join(os.environ["TEMP"], "facility_use_mapping.csv")
with open(out, "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["원문어휘", "공모수", "분류", "현재_자동감지", "별표1_매칭어", "건축법_용도(시니어 기입)"])
    w.writerows(rows)

print(f"공모 {len(by_comp)}종 · 고유어휘 {len(vocab)}종\n")
for cls in ["0. 이미 자동감지", "A. 별표1에 있음(코드로 해결 가능)",
            "B. 별표1에 없음 — 시니어 판단 필요", "C. 건축물 아님(매핑 불필요)"]:
    sel = [r for r in rows if r[2] == cls]
    print(f"[{cls}] {len(sel)}종")
    for r in sel: print(f"    {r[0]}" + (f"   →별표1:{r[4]}" if r[4] and not r[3] else ""))
    print()

# 우리 _BUILDING_USES 커버리지
heads = set()
for m in re.finditer(r"^\s*(\d{1,2})\.\s*([^\n\[(:]{2,20})", byp1, re.M):
    h = m.group(2).strip().rstrip("[(")
    if len(h) >= 2: heads.add((int(m.group(1)), h))
groups = sorted({n for n, _ in heads if 1 <= n <= 29})
print(f"별표1 용도군 번호 {len(groups)}개 확인 · 우리 _BUILDING_USES {len(_BUILDING_USES)}종")
print("CSV:", out)

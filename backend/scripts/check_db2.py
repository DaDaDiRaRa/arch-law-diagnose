import sqlite3, sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

conn = sqlite3.connect('./data/arch_law.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
    SELECT jurisdiction_code, jurisdiction_name, zone_use, category, value
    FROM ordinance_zone_limits
    WHERE jurisdiction_code = '11000'
    ORDER BY category, zone_use
""")
rows = cur.fetchall()
print(f"Seoul (11000) records: {len(rows)}")
for r in rows:
    print(f"  {r['jurisdiction_code']} | {r['category']} | {r['zone_use']} = {r['value']}")

print()
# 일반상업지역 직접 검색
cur.execute("""
    SELECT * FROM ordinance_zone_limits
    WHERE zone_use = '일반상업지역'
""")
rows2 = cur.fetchall()
print(f"일반상업지역 rows: {len(rows2)}")
for r in rows2:
    print(f"  {r['jurisdiction_code']} | {r['category']} | {r['zone_use']} = {r['value']}")

conn.close()

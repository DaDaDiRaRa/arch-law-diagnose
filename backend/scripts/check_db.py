import sqlite3

conn = sqlite3.connect('./data/arch_law.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
    SELECT DISTINCT jurisdiction_code, jurisdiction_name, zone_use
    FROM ordinance_zone_limits
    WHERE jurisdiction_code LIKE '11%'
    LIMIT 20
""")
rows = cur.fetchall()
print(f"Seoul records: {len(rows)}")
for r in rows:
    print(dict(r))

cur.execute("SELECT COUNT(*) as cnt FROM ordinance_zone_limits")
print(f"\nTotal rows: {cur.fetchone()['cnt']}")
conn.close()

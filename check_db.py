import sqlite3
import pandas as pd

DB_PATH = "flights_snapshot_raw.db"
conn = sqlite3.connect(DB_PATH)

df = pd.read_sql("""
SELECT snapshot_time, COUNT(*) AS num_planes
FROM flight_snapshots
GROUP BY snapshot_time
ORDER BY snapshot_time DESC
""", conn)

conn.close()

print(df)
import time

from opensky_api import OpenSkyApi
import pandas as pd
import sqlite3
from datetime import datetime, timezone
import requests

api = OpenSkyApi()

states = None

for i in range(3):

    try:
        states = api.get_states()
        if states and states.states:

            break

    except requests.exceptions.RequestException:

        pass

    print(f"Retry {i+1}...")

    time.sleep(10)

if states is None or states.states is None:

    print("No data received after retries")

    exit()




snapshot_time = datetime.now(timezone.utc)
records = []

for s in states.states:

    records.append({

        "icao24": s.icao24,

        "callsign": s.callsign.strip() if s.callsign else None,

        "origin_country": s.origin_country,

        "time_position": s.time_position,

        "last_contact": s.last_contact,

        "longitude": s.longitude,

        "latitude": s.latitude,

        "geo_altitude": s.geo_altitude,

        "on_ground": s.on_ground,

        "velocity": s.velocity,

        "true_track": s.true_track,

        "vertical_rate": s.vertical_rate,

        "sensors": s.sensors,

        "baro_altitude": s.baro_altitude,

        "squawk": s.squawk,

        "spi": s.spi,

        "position_source": s.position_source,

        "category": s.category,

        "snapshot_time": snapshot_time

    })

df = pd.DataFrame(records)

DB_PATH = "flights_snapshot_raw.db"

conn = sqlite3.connect(DB_PATH)

df.to_sql("flight_snapshots", conn, if_exists="append", index=False)

conn.close()

print(f"Saved {len(df)} rows to database")


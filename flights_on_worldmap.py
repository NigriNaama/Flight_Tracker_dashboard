import pandas as pd
import sqlite3
import json
import plotly.express as px

#load the flight data
conn = sqlite3.connect("flights_processed.db")
flights = pd.read_sql("SELECT * FROM flights", conn)
conn.close()

sample_flights = flights.sample(40, random_state=42) # sample 20 flights

all_points = [] # list to store all points

for _, row in sample_flights.iterrows():

    points = json.loads(row["route_points"])

    for i, p in enumerate(points):

        all_points.append({
            "icao24": row["icao24"],
            "flight_id": row["flight_count_per_plane"],
            "lat": p["lat"],
            "lon": p["lon"],
            "time": p["time"],
            "velocity": p["velocity"],
            "true_track": p["true_track"],
            "point_index": i
        })

points_df = pd.DataFrame(all_points) # convert list to dataframe

points_df["time"] = pd.to_datetime(points_df["time"]) # convert time to datetime

points_df["flight_label"] = (points_df["icao24"] + "_" + points_df["flight_id"].astype(str)) # create a unique label for each flight

fig = px.line_geo(
    points_df.sort_values(["flight_label", "time"]),
    lat="lat",
    lon="lon",
    color="flight_label",
    hover_data={
        "time": True,
        "velocity": True,
        "true_track": True,
        "lat": False,
        "lon": False
    },
    title="20 Random Flight Paths"
)

fig.add_scattergeo(
    lat=points_df["lat"],
    lon=points_df["lon"],
    mode="markers",
    marker=dict(size=3),
    text=points_df["time"],
    name="Flight points"
)


start_points = points_df.sort_values("time").groupby("flight_label").first().reset_index()
end_points = points_df.sort_values("time").groupby("flight_label").last().reset_index()

# start point (green)
fig.add_scattergeo(
    lat=start_points["lat"],
    lon=start_points["lon"],
    mode="markers",
    marker=dict(size=8, color="green"),
    name="Start"
)

# end point (red)
fig.add_scattergeo(
    lat=end_points["lat"],
    lon=end_points["lon"],
    mode="markers",
    marker=dict(size=8, color="red"),
    name="End"
)



fig.update_geos(
    projection_type="natural earth",
    showland=True,
    showcountries=True,
    showocean=True
)

fig.show()
import json
import sqlite3

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

# load data
results_df = pd.read_csv("airport_validation_results.csv")
detected_airports = pd.read_csv("detected_airports.csv")

st.set_page_config(page_title="Airport Detection Dashboard", layout="wide")

st.title("Detected Airports Dashboard")
st.markdown("### Overview")

st.markdown("""
This dashboard analyzes real flight data to detect airport locations based on clusters of takeoff and landing coordinates.  
Detected clusters are compared to real-world airport data to evaluate how accurately the algorithm identifies actual airports.  
The map visualizes both the estimated airport locations and their nearest real counterparts, along with validation metrics.
""")
# --- MAP ---
fig = go.Figure()

# add the detected airports (blue circles)
fig.add_scattergeo(
    lat=detected_airports["lat"],
    lon=detected_airports["lon"],
    mode="markers",
    marker=dict(
        size=detected_airports["count"],
        sizemode="area",
        sizeref=2 * detected_airports["count"].max() / (50 ** 2),
        color="steelblue"
    ),
    name="Detected airports",
    text=detected_airports["count"],
    hovertemplate="Detected flights: %{text}<extra></extra>"
)

# add the nearest real airports (red x)
fig.add_scattergeo(
    lat=results_df["airport_lat"],
    lon=results_df["airport_lon"],
    mode="markers",
    marker=dict(size=10, color="orangered", symbol="x", line=dict(color="gray", width=1)),
    name="Nearest real airports",
    text=results_df["nearest_airport"],
    hovertemplate="%{text}<extra></extra>"
)

# map appearance
fig.update_geos(
    showland=True,
    landcolor="#d6e4f0",
    showcountries=True,
    countrycolor="grey",
    showocean=True,
    oceancolor="#f8fbff",
    showlakes=True,
    lakecolor="#f8fbff"

)
fig.update_layout(title="Detected Airports", height=650)

st.plotly_chart(fig, use_container_width=True)


# --- QUALITY + STATS ---
left, right = st.columns([1.2, 1])

quality_counts = (
    results_df["quality"]
    .value_counts()
    .reindex(["excellent", "good", "okay", "bad"], fill_value=0)
    .reset_index()
)

quality_counts.columns = ["quality", "count"]

fig_quality = px.bar(
    quality_counts,
    x="quality",
    y="count",
    title="Validation Quality"
)

fig_quality.update_traces(width=0.35)
fig_quality.update_layout(height=350)

with left:
    st.plotly_chart(fig_quality, use_container_width=True)

with right:
    validation_rate = results_df["is_correct"].mean()
    st.metric("Validation rate", f"{validation_rate:.2%}")
    st.metric("Detected clusters", len(results_df))
    st.metric("Correct detections", int(results_df["is_correct"].sum()))
    st.metric("Average distance", f"{results_df['distance_km'].mean():.2f} km")

st.subheader("Validation Results")
st.dataframe(results_df, use_container_width=True)




########################################################################################################################


# =========================

# Load data

# =========================

flights_with_airports = pd.read_csv("flights_with_airports.csv")

# =========================

# Page setup

# =========================

st.set_page_config(

    page_title="Flight Route Explorer",

    layout="wide"

)

st.title("Flight Route Explorer")

st.markdown("""

Explore reconstructed flight routes by choosing an airport with recorded traffic.  

Airports are ranked by the number of detected flights in the dataset, so every option shown has available routes.

""")

# =========================

# User controls

# =========================

direction = st.radio(

    "Show flights",

    ["Departures", "Arrivals"],

    horizontal=True

)

min_flights = st.slider(

    "Minimum number of flights per airport",

    min_value=1,

    max_value=50,

    value=5

)

# =========================

# Build airport options

# =========================

if direction == "Departures":

    airport_counts = (

        flights_with_airports

        .groupby(["origin_icao", "origin_name", "origin_country"])

        .size()

        .reset_index(name="flight_count")

        .rename(columns={

            "origin_icao": "icao",

            "origin_name": "name",

            "origin_country": "country"

        })

    )

else:

    airport_counts = (

        flights_with_airports

        .groupby(["dest_icao", "dest_name", "dest_country"])

        .size()

        .reset_index(name="flight_count")

        .rename(columns={

            "dest_icao": "icao",

            "dest_name": "name",

            "dest_country": "country"

        })

    )

airport_counts = airport_counts[

    airport_counts["flight_count"] >= min_flights

].sort_values("flight_count", ascending=False)

if airport_counts.empty:

    st.warning("No airports found with the selected minimum number of flights.")

    st.stop()

airport_counts["label"] = (

    airport_counts["name"].astype(str)

    + " | "

    + airport_counts["icao"].astype(str)

    + " | "

    + airport_counts["country"].astype(str)

    + " | "

    + airport_counts["flight_count"].astype(str)

    + " flights"

)

selected_label = st.selectbox(

    "Choose airport",

    airport_counts["label"].tolist()

)

selected_airport = airport_counts.loc[

    airport_counts["label"] == selected_label,

    "icao"

].iloc[0]

selected_airport_name = airport_counts.loc[

    airport_counts["label"] == selected_label,

    "name"

].iloc[0]

# =========================

# Select flights

# =========================

if direction == "Departures":

    selected_flights = flights_with_airports[

        flights_with_airports["origin_icao"] == selected_airport

    ]

else:

    selected_flights = flights_with_airports[

        flights_with_airports["dest_icao"] == selected_airport

    ]

st.metric(

    label=f"{direction} found for {selected_airport}",

    value=len(selected_flights)

)

# =========================

# Convert route_points to map points

# =========================

all_route_points = []

for _, flight_row in selected_flights.iterrows():

    if pd.isna(flight_row["route_points"]):

        continue

    route_points = json.loads(flight_row["route_points"])

    for point_index, point in enumerate(route_points):

        all_route_points.append({

            "flight_label": f"{flight_row['icao24']}_{flight_row['flight_count_per_plane']}",
            "lat": point["lat"],
            "lon": point["lon"],
            "time": point["time"],
            "velocity": point["velocity"],
            "true_track": point["true_track"],
            "point_index": point_index,
            "origin": f"{flight_row['origin_country']}, {flight_row['origin_name']}",
            "destination": f"{flight_row['dest_country']}, {flight_row['dest_name']}"
        })

route_points_df = pd.DataFrame(all_route_points)

if route_points_df.empty:

    st.warning("No route points found for this airport.")

    st.stop()

# =========================

# Plot routes

# =========================

fig_routes = px.line_geo(
    route_points_df.sort_values(["flight_label", "point_index"]),
    lat="lat",
    lon="lon",
    color="flight_label",
    hover_data={
        "time": True,
        "velocity": True,
        "true_track": True,
        "origin": True,
        "destination": True,
        "flight_label": False
    },
    labels={
        "time": "Time (UTC)",
        "velocity": "Speed (m/s)",
        "true_track": "Heading (°)",
        "origin": "Origin Airport",
        "destination": "Destination Airport"
    },
    title=f"{direction} for {selected_airport}"
)

fig_routes.update_geos(
    showland=True,
    landcolor="#d6e4f0",
    showcountries=True,
    countrycolor="white",
    showocean=True,
    oceancolor="#f8fbff"
)

fig_routes.update_layout(

    height=700,

    margin=dict(l=0, r=0, t=50, b=0),

    showlegend=False

)

st.plotly_chart(fig_routes, width="stretch")

# =========================

# Optional table

# =========================

with st.expander("Show selected flights table"):

    st.dataframe(selected_flights, use_container_width=True)



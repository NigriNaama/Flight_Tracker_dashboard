import sqlite3
import pandas as pd
import json
import numpy as np


DB_PATH = "flights_snapshot_raw.db"
# flights_snapshot_raw.db: ['icao24', 'callsign', 'origin_country', 'time_position', 'last_contact', 'longitude', 'latitude', 'geo_altitude', 'on_ground', 'velocity', 'true_track', 'vertical_rate', 'sensors', 'baro_altitude', 'squawk', 'spi', 'position_source', 'category', 'snapshot_time']


def load_snapshot_data(snapshot_file):
    conn = sqlite3.connect(DB_PATH)

    df = pd.read_sql("""
    SELECT icao24, latitude, longitude, velocity, on_ground, true_track, category, snapshot_time
    FROM flight_snapshots
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL 
    """, conn)

    conn.close()

    df["snapshot_time"] = pd.to_datetime(df["snapshot_time"])  # to_datetime converts the string to datetime

    return df



def find_approx_takeoff_and_landing(df):

    df = df.sort_values(["icao24", "snapshot_time"]).copy() # sort by icao24 and snapshot_time

    df["prev_on_ground"] = df.groupby("icao24")["on_ground"].shift() # shift the on_ground column by 1

    df["takeoff"] = ((df["prev_on_ground"] == True) &(df["on_ground"] == False)) # locate approx takeoff

    df["landing"] = ((df["prev_on_ground"] == False) &(df["on_ground"] == True)) # locate approx landing

    df["flight_count_per_plane"] = df.groupby("icao24")["takeoff"].cumsum() # assign a unique flight count to each plane

    return df

def build_flights_table(df):
    df = df.sort_values(["icao24", "flight_count_per_plane", "snapshot_time"])

    # group by icao24 and flight_id and calculate the start and end times of each flight
    flights = df.groupby(["icao24", "flight_count_per_plane"]).agg(
        start_time=("snapshot_time", "min"),
        end_time=("snapshot_time", "max"),
        num_snapshots=("snapshot_time", "count"),
        has_takeoff=("takeoff", "any"),
        has_landing=("landing", "any"),

        # takeoff coordinates
        start_latitude=("latitude", "first"),
        start_longitude=("longitude", "first"),

        # landing coordinates
        end_latitude=("latitude", "last"),
        end_longitude=("longitude", "last"),

        avg_velocity=("velocity", "mean"),
        avg_true_track=("true_track", "mean"),

        category=("category", "first")
    ).reset_index()

    flights = flights[flights["flight_count_per_plane"] > 0 & (flights["has_takeoff"]) & (flights["has_landing"]) & (flights["num_snapshots"] >= 3)] # filter out flights that do not have takeoff or landing
    flights["duration_hours"] = (flights["end_time"] - flights["start_time"]).dt.total_seconds() / 3600 # calculate flight duration in hours

    return flights

def build_route_points(flight):
    # build a list of points for a single flight

    points = []

    for _, row in flight.iterrows():
        points.append({
            "time": str(row["snapshot_time"]),
            "lat": row["latitude"],
            "lon": row["longitude"],
            "velocity": row["velocity"],
            "true_track": row["true_track"]
        })

    return json.dumps(points)

def add_route_points(df, flights):

    df = df.sort_values(["icao24", "flight_count_per_plane", "snapshot_time"])

    route_points_df = (df.groupby(["icao24", "flight_count_per_plane"]).apply(build_route_points, include_groups=False).reset_index(name="route_points"))

    flights = flights.merge(
        route_points_df,
        on=["icao24", "flight_count_per_plane"],
        how="left"
    )

    return flights


def calculate_distance_coordinates(lat1, lon1, lat2, lon2):
    # Calculate the distance between two points using the Haversine formula

    R = 6371 #Earth radius in km

    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2)

    return R * 2 * np.arcsin(np.sqrt(a))


def calculate_total_distance(route_points):
    # Calculate the total distance of a flight route

    points = json.loads(route_points)

    total_distance = 0

    for i in range(len(points)-1): # loop through each point in the route

        p1 = points[i]
        p2 = points[i+1]

        # Check if both points have latitude and longitude values
        if p1["lat"] is None or p2["lat"] is None or p1["lon"] is None or p2["lon"] is None:
            continue

        # Calculate the distance between the two points
        distance = calculate_distance_coordinates(p1["lat"], p1["lon"], p2["lat"], p2["lon"])

        # Calculate the time difference between the two points
        t1 = pd.to_datetime(p1["time"])
        t2 = pd.to_datetime(p2["time"])
        time_diff = (t2 - t1).total_seconds() / 3600

        if time_diff == 0: # skip points with time difference of 0
            continue


        speed = distance / time_diff

        if speed < 1200:  # threshold no plane can fly faster than 1200 km/h so probably gps error
            total_distance += distance


        total_distance += distance

    return total_distance


def add_total_distance(df):

    df["total_distance_km"] = df["route_points"].apply(calculate_total_distance)

    # filter out flights with total distance less than 50 km (probably gps error)
    df = df[df["total_distance_km"] > 50]

    return df

data = load_snapshot_data(DB_PATH)

data = find_approx_takeoff_and_landing(data)

flights = build_flights_table(data)

flights = add_route_points(data, flights)

flights = add_total_distance(flights)

conn = sqlite3.connect("flights_processed.db")

flights.to_sql("flights", conn, if_exists="replace", index=False)

conn.close()

#flights.columns: 'icao24', 'flight_count_per_plane', 'start_time', 'end_time', 'num_snapshots', 'has_takeoff', 'has_landing',
                # 'start_latitude', 'start_longitude', 'end_latitude', 'end_longitude',
                # 'avg_velocity', 'avg_true_track', 'category', 'duration_hours', 'route_points', 'total_distance_km'

# flights table columns description

# icao24 (str): Unique identifier of the aircraft

# flight_count_per_plane (int): Sequential flight index for each aircraft, generated based on detected takeoff events. Used to distinguish between multiple flights of the same plane.

# start_time (datetime): Estimated start time of the flight, based on the change of on_ground status to False.

# end_time (datetime): Estimated end time of the flight, based on the change of on_ground status to True.

# duration_hours (float): Total duration of the flight in hours, calculated as (end_time - start_time).

# num_snapshots (int): Number of recorded observations (snapshots) for this flight.

# has_takeoff (bool): Indicates whether a takeoff event (ground → air transition) was detected.

# has_landing (bool): Indicates whether a landing event (air → ground transition) was detected.

# start_latitude (float): Latitude of the first recorded point of the flight.
# start_longitude (float): Longitude of the first recorded point of the flight.

# end_latitude (float): Latitude of the last recorded point of the flight.
# end_longitude (float): Longitude of the last recorded point of the flight.

# avg_velocity (float): Average velocity of the aircraft during the flight (in meters per second).

# avg_true_track (float): Average heading direction of the aircraft (in degrees, where 0° = north).

# category (int): Aircraft category code representing the type/size of the aircraft. (e.g., light, small, large, heavy, helicopter, etc.).

# route_points (str / JSON): Ordered list of all observed points during the flight.

# Each point contains:
#   - time (str): timestamp of the observation
#   - lat (float): latitude
#   - lon (float): longitude
#   - velocity (float): instantaneous velocity
#   - true_track (float): heading direction

# Stored as a JSON string for compact storage and easy reconstruction.

# total_distance_km (float): Total distance covered by the flight (in kilometers).
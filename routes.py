import pandas as pd
import numpy as np
import sqlite3

from find_airports import find_nearest_airport

#load the flight data
conn = sqlite3.connect("flights_processed.db")
flights = pd.read_sql("SELECT * FROM flights", conn)
conn.close()

# load airport data and clean lon lat null values
columns = ["AirportID", "Name", "City", "Country","IATA", "ICAO", "Latitude", "Longitude", "Altitude", "Timezone", "DST", "Tz", "Type", "Source"]

airports = pd.read_csv("airports.csv", header=None, names=columns)
airports["Latitude"] = pd.to_numeric(airports["Latitude"], errors="coerce")
airports["Longitude"] = pd.to_numeric(airports["Longitude"], errors="coerce")
airports = airports.dropna(subset=["Latitude", "Longitude"])


# find the nearest airport for each flight
records = []

for _, row in flights.iterrows():

    # find the nearest airport to the start of flight
    origin_airport, dist_origin = find_nearest_airport(row["start_latitude"], row["start_longitude"], airports)

    # find the nearest airport to the end of flight
    dest_airport, dist_dest = find_nearest_airport(row["end_latitude"], row["end_longitude"], airports)

    records.append({
        "icao24": row["icao24"],
        "flight_count_per_plane": row["flight_count_per_plane"],

        "origin_name": origin_airport["Name"],
        "origin_icao": origin_airport["ICAO"],
        "origin_lat": origin_airport["Latitude"],
        "origin_lon": origin_airport["Longitude"],
        "origin_country": origin_airport["Country"],
        "origin_distance_km": dist_origin,

        "dest_name": dest_airport["Name"],
        "dest_icao": dest_airport["ICAO"],
        "dest_lat": dest_airport["Latitude"],
        "dest_lon": dest_airport["Longitude"],
        "dest_country": dest_airport["Country"],
        "dest_distance_km": dist_dest,

        "route_points": row["route_points"]
    })

# create a dataframe
flights_with_airports = pd.DataFrame(records)


# filter out flights that are more than 30 km away from the true airport (count as false positive)
THRESHOLD = 30
flights_with_airports = flights_with_airports[(flights_with_airports["origin_distance_km"] < THRESHOLD) &(flights_with_airports["dest_distance_km"] < THRESHOLD)]

flights_with_airports.to_csv("flights_with_airports.csv", index=False)





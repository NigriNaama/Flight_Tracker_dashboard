import sqlite3
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
import plotly.express as px
import plotly.graph_objects as go

#load the flight data
conn = sqlite3.connect("flights_processed.db")
flights = pd.read_sql("SELECT * FROM flights", conn)
conn.close()

# find the takeoff and landing airports for each flight (approximate)
takeoff_airports = flights[["start_latitude", "start_longitude"]].rename(columns={"start_latitude": "lat", "start_longitude": "lon"})
landing_airports = flights[["end_latitude", "end_longitude"]].rename(columns={"end_latitude": "lat", "end_longitude": "lon"})

airport_candidate_points = pd.concat([takeoff_airports, landing_airports]) # combine takeoff and landing airports
airports_coords = np.radians(airport_candidate_points[["lat", "lon"]])


kms_per_radian = 6371.0088
epsilon = 15 / kms_per_radian

# run DBSCAN clustering algorithm to find clusters of airports
db = DBSCAN(eps=epsilon,min_samples=5,algorithm='ball_tree',metric='haversine').fit(airports_coords)

airport_candidate_points["cluster"] = db.labels_

clusters = airport_candidate_points[airport_candidate_points["cluster"] != -1] # filter out points that are not in a cluster

# calculate the average latitude and longitude of each cluster
detected_airports = clusters.groupby("cluster").agg(lat=("lat", "mean"), lon=("lon", "mean"), count=("lat", "count")).reset_index()

detected_airports = detected_airports[detected_airports["count"] >= 20] # filter out clusters with less than 20 points (at least 20 planes took off or landed in the cluster)


# load the true airports data
columns = ["AirportID", "Name", "City", "Country", "IATA", "ICAO", "Latitude", "Longitude", "Altitude", "Timezone", "DST", "Tz", "Type", "Source"]
true_airports = pd.read_csv("airports.csv", header=None, names=columns)

# convert Latitude and Longitude columns to numeric
true_airports["Latitude"] = pd.to_numeric(true_airports["Latitude"], errors="coerce")
true_airports["Longitude"] = pd.to_numeric(true_airports["Longitude"], errors="coerce")

# drop rows with missing Latitude or Longitude values
true_airports = true_airports.dropna(subset=["Latitude", "Longitude"])

def find_nearest_airport(lat, lon, airports_df):
    # find the nearest airport to the given coordinates (cluster centroid)

    lat1 = np.radians(lat)
    lon1 = np.radians(lon)

    lat2 = np.radians(airports_df["Latitude"].values)
    lon2 = np.radians(airports_df["Longitude"].values)

    # haversine formula to calculate the distance between two points

    dis_lat = lat2 - lat1
    dis_lon = lon2 - lon1

    a = np.sin(dis_lat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dis_lon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))

    distances = 6371 * c  # km

    idx = np.argmin(distances) # the index of the nearest airport

    return airports_df.iloc[idx], distances[idx]


# find the nearest airport to each cluster centroid
results = []

for _, row in detected_airports.iterrows():
    airport, dist = find_nearest_airport(row["lat"], row["lon"], true_airports)

    results.append({
        "cluster_id": row["cluster"],
        "detected_lat": row["lat"],
        "detected_lon": row["lon"],
        "detected_count": row["count"],
        "nearest_airport": airport["Name"],
        "airport_lat": airport["Latitude"],
        "airport_lon": airport["Longitude"],
        "distance_km": dist
    })

results_df = pd.DataFrame(results)
# filter out airports that are more than 15 km away from the true airport (count as false positive)
THRESHOLD = 15
results_df["is_correct"] = results_df["distance_km"] < THRESHOLD

# compute the accuracy of the clustering
accuracy = results_df["is_correct"].mean()


def classify(dist):
    # classify the estimated airports locations based on the distance from the true airport

    if dist < 5:
        return "excellent"
    elif dist < 15:
        return "good"
    elif dist < 30:
        return "okay"
    else:
        return "bad"

results_df["quality"] = results_df["distance_km"].apply(classify)





import folium
from geopy.geocoders import Nominatim
from folium import Circle
import webbrowser
import os
import requests
from tqdm import tqdm
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

# Using the Overpass API for mapping
OVERPASS_URL = "http://overpass-api.de/api/interpreter"

# Generate coordinates from an address
def get_coordinates(address):
    geolocator = Nominatim(user_agent="geoapi")
    location = geolocator.geocode(address)
    if location:
        return (location.latitude, location.longitude)
    else:
        return None

# Using coordinates, find walkable areas using a query
def FindWalkableAreas(lat, lon, rad):

    # Query for areas around highways
    query = f"""
    [out:json];
    (
      way["highway"](around:{rad * 1000},{lat},{lon})
        ["highway"!~"motorway|motorway_link"];
    );
    out center tags;
    """
    try:
        response = requests.get(OVERPASS_URL, params={'data': query}, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("Overpass API error:", e)
        return []

    # Parse the JSON file to put walkable locations in a list
    walkable_areas = []
    for el in data.get('elements', []):
        center = el.get('center')
        if center:
            lat_center = center.get('lat')
            lon_center = center.get('lon')
            if lat_center is not None and lon_center is not None:
                highway_type = el['tags'].get('highway', 'unknown')
                name = el['tags'].get('name', f"Walkable Area ({highway_type})")
                walkable_areas.append((name, lat_center, lon_center, f"highway={highway_type}", "walkable"))
    return walkable_areas

# Create the map of walkable locations
def create_map(center_lat, center_lon, radius_km, walkable_areas):
    Map = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    folium.Marker([center_lat, center_lon], popup="Center Location").add_to(Map)

    # Radius chosen by user
    Circle(
        location=(center_lat, center_lon),
        radius=radius_km * 1000,
        color='blue',
        fill=True,
        fill_opacity=0.2
    ).add_to(Map)

    # Take all the walkable areas and show them on the map
    for name, lat, lon, tags, _ in walkable_areas:
        folium.CircleMarker(
            location=[lat, lon],
            radius=3,
            color='black',
            fill=True,
            fill_opacity=1,
            popup=f"{name}\n{tags}"
        ).add_to(Map)

    Map.save("Walkable_Map.html")
    webbrowser.open('file://' + os.path.realpath("Walkable_Map.html"))

# Write to a text file all the found walkable locations
def save_to_file(points, filename="Walkable.txt"):
    with open(filename, "w", encoding="utf-8") as f:
        f.write("Walkable areas:\n\n")
        for name, lat, lon, tags, status in points:
            f.write(f"{name}: ({lat}, {lon})\n")

# Harversine formula for finding the distance between two coordinates
# https://www.geeksforgeeks.org/haversine-formula-to-find-distance-between-two-points-on-a-sphere/
def CalculateDistance(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lat2_rad = np.radians(lat2)
    lon2_rad = np.radians(lon2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    distance = R * c
    return distance 

def main():
    # From the user get an address or coordinates for their chosen location
    ch = input("Type 'Address' or 'Coordinates': ").strip().lower()
    if ch == 'address':
        address = input("Enter address: ")
        coords = get_coordinates(address)
        if not coords:
            print("Address not found")
            return
    elif ch == 'coordinates':
        try:
            lat = float(input("Latitude: "))
            lon = float(input("Longitude: "))
            coords = (lat, lon)
        except ValueError:
            print("Invalid Coordinates")
            return
    else:
        print("Invalid Entry")
        return

    # From the user get the radius of the circle
    try:
        radius = float(input("Radius (KM): "))
    except ValueError:
        print("Invalid Radius")
        return
    
    # From the user get the number of runs
    try:
        num_runs = int(input("Enter number of points to keep: "))
    except ValueError:
        print("Invalid number of points")
        return

    print("Finding walkable areas using Overpass API...")
    total_walkable_areas = FindWalkableAreas(coords[0], coords[1], radius)

    if not total_walkable_areas:
        print("No walkable areas found.")
        return
    
    walkable_areas = []
    utility_values = []
    privacy_values = []

    if len(total_walkable_areas) < num_runs:
        num_runs = len(total_walkable_areas)

    # For each iteration, calculate the privacy and utility values and save them
    for x in range(num_runs):
        chosen = total_walkable_areas[x]
        walkable_areas.append(chosen)

        utility = 0.0
        privacy = 0.0

        # Privacy is the distance from the centroid of all current POIs in the iteration to the chosen location
        lat_sum = sum(p[1] for p in walkable_areas)
        lon_sum = sum(p[2] for p in walkable_areas)
        centroid_lat = lat_sum / len(walkable_areas)
        centroid_lon = lon_sum / len(walkable_areas)
        privacy = CalculateDistance(coords[0], coords[1], centroid_lat, centroid_lon)

        total = 0
        for _, lat, lon, *_ in walkable_areas:
            total += CalculateDistance(coords[0], coords[1], lat, lon)
        utility = total / x

        utility_values.append(utility)
        privacy_values.append(privacy)

        print(f"Iteration {x + 1}")
        print(f"Privacy = {privacy}")
        print(f"Utility = {utility}")
        print("")

    # Create the map and text files
    save_to_file(walkable_areas)
    create_map(coords[0], coords[1], radius, walkable_areas)

    # Plot the privacy and utility vs iteration
    plt.figure(figsize=(12, 5))

    plt.subplot(1, 2, 1)
    plt.plot(range(1, num_runs + 1), utility_values, marker='o', color='green')
    plt.title('Utility vs Iteration')
    plt.xlabel('Iteration')
    plt.ylabel('Utility (Avg Distance to Chosen POIs)')

    plt.subplot(1, 2, 2)
    plt.plot(range(1, num_runs + 1), privacy_values, marker='o', color='red')
    plt.title('Privacy vs Iteration')
    plt.xlabel('Iteration')
    plt.ylabel('Privacy (Distance to Centroid of POIs)')

    plt.tight_layout()
    plt.savefig("Walkable_Utility_Privacy_Graph")
    plt.show()

    

if __name__ == "__main__":
    main()

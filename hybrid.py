import folium
from geopy.geocoders import Nominatim
from folium import Circle # helps create the interactive map
import webbrowser 
import os
import requests # making http request to OpenStreetMaps
import re
import random
from collections import defaultdict
import warnings
import math
import matplotlib.pyplot as plt
import pandas as pd

OVERPASS_URL = "http://overpass-api.de/api/interpreter"
os.environ["OMP_NUM_THREADS"] = "1"
warnings.filterwarnings(
    "ignore",
    message="Could not find the number of physical cores*",
    category=UserWarning
)

# converts a text address into latitude and longitude 
def GetCoordinates(address):
    # Nominatim is a geocoding service
    geolocator = Nominatim(user_agent="geoapi")
    location = geolocator.geocode(address)
    if location:
        return (location.latitude, location.longitude)
    else:
        return None

# Queiries OpenStreetMaps Overpass API to find POIs
def FindPOIs(lat, lon, rad):
    # finds amentities, tourism, leisure, and shop tags 
    query = f"""
    [out:json];
    (
      node["amenity"](around:{rad * 1000},{lat},{lon});
      node["tourism"](around:{rad * 1000},{lat},{lon});
      node["leisure"](around:{rad * 1000},{lat},{lon});
      node["shop"](around:{rad * 1000},{lat},{lon});

      way["amenity"](around:{rad * 1000},{lat},{lon});
      way["tourism"](around:{rad * 1000},{lat},{lon});
      way["leisure"](around:{rad * 1000},{lat},{lon});
      way["shop"](around:{rad * 1000},{lat},{lon});

      relation["amenity"](around:{rad * 1000},{lat},{lon});
      relation["tourism"](around:{rad * 1000},{lat},{lon});
      relation["leisure"](around:{rad * 1000},{lat},{lon});
      relation["shop"](around:{rad * 1000},{lat},{lon});
    );
    out center tags;
    """
    # puts the pois found into a lists
    response = requests.get(OVERPASS_URL, params={'data': query})
    data = response.json()
    pois = []
    for el in data['elements']:
        name = el.get('tags', {}).get('name', 'Unnamed POI')
        lat = el.get('lat')
        lon = el.get('lon')

        if lat is None or lon is None:
            center = el.get('center')
            if center:
                lat = center.get('lat')
                lon = center.get('lon')

        if lat is not None and lon is not None and name != 'Unnamed POI':
            pois.append((name, lat, lon, "poi"))

    # returns the lists of pois
    return pois

# querires OpenStreetMaps for walkable areas along a road or trail
def FindWalkableAreas(lat, lon, rad):
    query = f"""
    [out:json];
    (
      way["highway"](around:{rad * 1000},{lat},{lon})
        ["highway"!~"motorway|motorway_link"];
    );
    out center tags;
    """
    response = requests.get(OVERPASS_URL, params={'data': query})
    data = response.json()
    # puts the walkable locations into a list with longitude and latitude
    walkable_areas = []
    for el in data['elements']:
        center = el.get('center')
        if center:
            lat_center = center.get('lat')
            lon_center = center.get('lon')
            if lat_center and lon_center:
                highway_type = el['tags'].get('highway', 'unknown')
                name = el['tags'].get('name', f"Walkable Area ({highway_type})")
                walkable_areas.append((name, lat_center, lon_center, "walkable"))
    # returns all the walkable locations
    return walkable_areas

# calculates the distance between to points using longitude and latitude
def calculate_distance(lat1, lon1, lat2, lon2):
    # uses the Haversine formula
    R = 6371  # radius of earth
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2) * math.sin(dLat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon/2) * math.sin(dLon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c
    return distance

# calculates a center location of a set of locations
def calculate_centroid(locations):
    if not locations:
        return (0, 0)
    
    centroid_lat = sum(float(loc[1]) for loc in locations) / len(locations)
    centroid_lon = sum(float(loc[2]) for loc in locations) / len(locations)
    return (centroid_lat, centroid_lon)

# calculates the distance between a user's location and the centriod of chosen locations
# higher the number is than the more privacy
def calculate_privacy_distance(user_lat, user_lon, chosen_locations):
    if not chosen_locations:
        return 0
    # calculate the centriod longitude and latitude
    centroid_lat, centroid_lon = calculate_centroid(chosen_locations)
    # calculate distance between user and centriod
    privacy_distance = calculate_distance(user_lat, user_lon, centroid_lat, centroid_lon)
    return privacy_distance

# calculates the distance that the user would have to walk to pickup/dropoff location
# lower number is more ideal for user but also lowers the privacy
def calculate_utility_distance(user_lat, user_lon, chosen_locations):
    if not chosen_locations:
        return 0
    # calculates the first distance
    if len(chosen_locations) == 1:
        loc = chosen_locations[0]
        return calculate_distance(user_lat, user_lon, float(loc[1]), float(loc[2]))
    # calculate the centriod longitude and latitude
    centroid_lat, centroid_lon = calculate_centroid(chosen_locations)
    # calculate distance between user and centriod
    distances = [calculate_distance(centroid_lat, centroid_lon, float(loc[1]), float(loc[2])) 
                 for loc in chosen_locations]
    utility_distance = sum(distances) / len(distances) if distances else 0
    return utility_distance

# this creates an interactive map showing users location and chosen locations, and radius
def CreateMap(lat, lon, rad, locations, location_counter):
    Map = folium.Map(location=[lat, lon], zoom_start=13)
    # sets the users location
    folium.Marker([lat, lon], popup="User Location", icon=folium.Icon(color='red')).add_to(Map)
    # this creates the radius around the users location
    Circle(
        location=(lat, lon),
        radius=rad * 1000,
        color='blue',
        fill=True,
        fill_opacity=0.3
    ).add_to(Map)
    chosen_locations = []
    # creates the map markers for chosen locations
    for location in locations:
        name, lat_loc, lon_loc, loc_type = location
        location_key = f"{name} ({lat_loc}, {lon_loc})"
        count = location_counter.get(location_key, 0)
        
        if count > 0:
            # sets the chosen locations colors 
            chosen_locations.append(location)
            marker_color = 'green' if loc_type == 'poi' else 'orange'
            # adds the chosen locations to the map
            folium.Marker(
                location=[float(lat_loc), float(lon_loc)],
                popup=f"{name}<br>Visits: {count}",
                icon=folium.Icon(color=marker_color, icon='info-sign' if loc_type == 'poi' else 'road')
            ).add_to(Map)
    # saves the map as an html file that is opened in a browser
    Map.save("hybrid_map.html")
    webbrowser.open('file://' + os.path.realpath("hybrid_map.html"))
    
    return chosen_locations

# this creates a graph from the cvs data showing the privacy vs. utility over multiple runs
def make_graph(csv_file):
    try:
        # 
        df = pd.read_csv(csv_file)
        # creates the graph with the privacy and utility
        plt.figure(figsize=(10, 6))
        plt.plot(df['Run'], df['Privacy(km)'], marker='o', linestyle='-', color='blue', label='Privacy')
        plt.plot(df['Run'], df['Utility(km)'], marker='s', linestyle='-', color='green', label='Utility')
        plt.title('Privacy and Utility Metrics Over Multiple Runs', fontsize=14)
        plt.xlabel('Number of Locations Chosen', fontsize=12)
        plt.ylabel('Distance (km)', fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend()
        # saves the graph a png file
        plt.savefig('hybrid_graph.png', dpi=300)
        plt.close()
    # if the graph was not created then it returns an error
    except Exception as e:
        print(f"Error creating graphs: {e}")

# this reads a text file for location data needed
def parse_config_file(filename):
    try:
        config = {}
        with open(filename, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            # gets the longitude and latitude
            if key == 'location_type':
                config[key] = value.lower()
            elif key in ['latitude', 'longitude', 'radius', 'noise']:
                config[key] = float(value)
            elif key == 'address':
                config[key] = value
            elif key == 'num_runs':
                config[key] = int(value)
                
        return config
    # if the file was not read returns error
    except Exception as e:
        print(f"Error parsing config file: {e}")
        return None

def Main():
    # read the day in the life file
    config = parse_config_file("hybrid_day_in_life.txt")
    if not config:
        print("Failed to read file.")
        return
        
    # gets the location data 
    if 'location_type' in config and config['location_type'] == 'address':
        if 'address' not in config:
            print("Address not specified in config file.")
            return
            
        coords = GetCoordinates(config['address'])
        if not coords:
            print("Address not found")
            return
    elif 'latitude' in config and 'longitude' in config:
        coords = (config['latitude'], config['longitude'])
    else:
        print("Invalid location information in config file.")
        return
        
    # gets the radius for how far to find a location from user
    radius = config.get('radius', 1.0)
    # gets the num of times this would be ran for that one location
    num_runs = config.get('num_runs', 10)
    
    print(f"Using coordinates: {coords}")
    print(f"Radius: {radius} km")
    print(f"Number of runs: {num_runs}")
    
    # finds all the pois and walkable locations in the radius
    pois = FindPOIs(coords[0], coords[1], radius)
    walkable_areas = FindWalkableAreas(coords[0], coords[1], radius)
    
    print(f"Found {len(pois)} POIs and {len(walkable_areas)} walkable areas.")
    
    locations_to_use = []
    location_keys = []
    
    # when there are not atleast 20 pois then it picks pois
    if len(pois) >= 20:
        print("Using only POIs since there at at least 20 in area!")
        locations_to_use = pois
    else:
        # if there arent 20 pois it picks between pois and walkable locations
        print(f"Only {len(pois)} POIs found. Adding walkable areas.")
        locations_to_use = pois + walkable_areas
        
        # when there are not enough walkable locations or pois in the radius
        if len(locations_to_use) < 5:
            print(f"Not enough locations to use")
    # cant be used if no locations other than the users to pick from
    if not locations_to_use:
        print("No locations found within the specified radius.")
        return
    
    # Create location keys for the counter and a dictionary to map keys back to locations
    location_dict = {}
    for loc in locations_to_use:
        key = f"{loc[0]} ({loc[1]}, {loc[2]})"
        location_keys.append(key)
        location_dict[key] = loc
    
    # creates a file to store the data of each location found and privacy and utility
    with open("hybrid_data.csv", "w", encoding="utf-8") as metrics_file:
        metrics_file.write("Run,Location,Utility(km),Privacy(km)\n")
        
        # creates empty list of locations picked
        chosen_locations = []
        location_counter = defaultdict(int)
        
        # runs for the number of times they want a location
        for run in range(1, num_runs + 1):
            # picks random location
            chosen_key = random.choice(location_keys)
            chosen_location = location_dict[chosen_key]
            location_counter[chosen_key] += 1
            
            # adds chosen location to lists
            chosen_locations.append(chosen_location)
            
            #  calculates utility and privacy
            utility = calculate_utility_distance(
                coords[0], coords[1], chosen_locations
            )
            privacy = calculate_privacy_distance(
                coords[0], coords[1], chosen_locations
            )
            # writes the utility and privacy to file after each new location
            metrics_file.write(
                f'{run},"{chosen_key}",{utility:.4f},{privacy:.4f}\n'
            )
            
            print(f"Run {run}: Selected {chosen_location[0]}")
            print(f"  - Utility: {utility:.4f} km")
            print(f"  - Privacy: {privacy:.4f} km")
    
    # creates a map of the each suggested location 
    CreateMap(coords[0], coords[1], radius, locations_to_use, location_counter)

    # creates a graph of the privacy vs utility
    make_graph("hybrid_data.csv")
    
    # calculates the utility and privacy scores based on chosen locations
    final_utility = calculate_utility_distance(coords[0], coords[1], chosen_locations)
    final_privacy = calculate_privacy_distance(coords[0], coords[1], chosen_locations)
    
    # saves the final results to a file
    with open("hybrid_locations.txt", "w", encoding="utf-8") as file:
        file.write("Final Utility and Privacy Metrics:\n")
        file.write(f"Utility: {final_utility:.4f} km\n")
        file.write(f"Privacy: {final_privacy:.4f} km\n\n")
        # adds in every suggested location generated and the amount of times that the location was suggested
        file.write("Suggested locations:\n")
        for loc_key, count in location_counter.items():
            if count > 0:
                file.write(f"{loc_key} -> suggested {count} times\n")

if __name__ == "__main__":
    Main()

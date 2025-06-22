import subprocess
import time
import math
import re
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import statistics
import matplotlib.pyplot as plt

# Generate coordinates from an address
def get_coordinates(address):
    geolocator = Nominatim(user_agent="geoapi")
    location = geolocator.geocode(address)
    return (location.latitude, location.longitude) if location else (None, None)

# Get coordinates from a file
def extract_coords_from_file(filepath):
    coords = []
    with open(filepath, 'r', encoding='utf-8') as file:
        # Use regex to match a line in the file to a coordinate
        for line in file:
            match = re.search(r"\(([-\d.]+), ([-\d.]+)\)", line)
            if match:
                lat = float(match.group(1))
                lon = float(match.group(2))
                coords.append((lat, lon))
    return coords

# Find the average distance between two coordinates
def average_distance(from_coord, to_coords):
    if not to_coords:
        return float('inf')
    total = sum(geodesic(from_coord, point).km for point in to_coords)
    return total / len(to_coords)

# Determine the centroid from a list of coordinates
def centroid(coords):
    if not coords:
        return (None, None)
    lat = sum(point[0] for point in coords) / len(coords)
    lon = sum(point[1] for point in coords) / len(coords)
    return (lat, lon)


# def run_program(command):
#     subprocess.run(command, shell=True)

def main():
    # Use the text file as input
    with open("day_in_a_life.txt", "r", encoding="utf-8") as file:
        lines = [line.strip() for line in file if line.strip()]

    show_popups = False
    if (lines[0] == 'y' or lines[0] == 'Y'):
        show_popups = True

    results = []
    num_runs = lines[1]
    for i in range(2, len(lines), 2):
        # Parse the text file for the required input
        address = lines[i]
        radius = float(lines[i + 1])
        coords = get_coordinates(address)

        if not coords[0]:
            print(f"Skipping invalid address: {address}")
            continue

        print(f"\nProcessing location: {address} (radius {radius} km)")

        # Run the poi.py method using the input from text file
        print("Running POI-based method...")
        proc = subprocess.Popen(
            f'python poi.py',
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=show_popups
        )
        proc.communicate(input=f"address\n{address}\n{radius}\n0.002\n{num_runs}\n")
        time.sleep(2)

        # Determine the privacy and utility for a single location for POI method
        poi_coords = extract_coords_from_file("POIs.txt")
        utility_poi = average_distance(coords, poi_coords)
        centroid_poi = centroid(poi_coords)
        privacy_poi = geodesic(coords, centroid_poi).km if centroid_poi[0] is not None else float('inf')
        results.append((address, "POI", utility_poi, privacy_poi)) 

        # Run the walkable.py method using input from text file
        print("Running Walkable method...")
        proc = subprocess.Popen(
            f'python walkable.py',
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=show_popups
        )
        proc.communicate(input=f"address\n{address}\n{radius}\n{num_runs}\n")
        time.sleep(2)

        # Determine the privacy and utility for a single location for walkable method
        walkable_coords = extract_coords_from_file("Walkable.txt")
        utility_osrm = average_distance(coords, walkable_coords)
        centroid_osrm = centroid(walkable_coords)
        privacy_osrm = geodesic(coords, centroid_osrm).km if centroid_osrm[0] is not None else float('inf')
        results.append((address, "Walkable", utility_osrm, privacy_osrm)) 

    # Print summary
    total_utility_poi = []
    total_privacy_poi = []
    total_utility_osrm = []
    total_privacy_osrm = []

    # Show privacy/utility tradeoff for each location, for each method
    print("\n==== Privacy vs Utility Summary ====")
    for address, method, utility, privacy in results:
        print(f"Address: {address}")
        print(f"  Method: {method}")
        print(f"  Utility: {utility:.4f} km")
        print(f"  Privacy: {privacy: .4f} km")
        print()
        if method == "POI":
            total_utility_poi.append(utility)
            total_privacy_poi.append(privacy)
        if method == "Walkable":
            total_utility_osrm.append(utility)
            total_privacy_osrm.append(privacy)

    # Show average privacy/utility tradeoff for each method
    print(f"Average Utility for POI: {statistics.mean(total_utility_poi):.4f} km")
    print(f"Average Privacy for POI: {statistics.mean(total_privacy_poi):.4f} km")
    print(f"Average Utility for Walkable: {statistics.mean(total_utility_osrm):.4f} km")
    print(f"Average Privacy for Walkable: {statistics.mean(total_privacy_osrm):.4f} km")

    # Create a summary plot of privacy/utility tradeoff for each location, for each method
    plt.figure(figsize=(12, 7))
    for address, method, utility, privacy in results:
        color = 'blue' if method == "POI" else 'green'
        marker = 'o' if method == "POI" else '^'
        plt.scatter(privacy, utility, color=color, marker=marker, label=method if address == results[0][0] else "")

        # Annotate each point with the address
        plt.annotate(
            address,
            (privacy, utility),
            textcoords="offset points",
            xytext=(5, 5),
            ha='left',
            fontsize=8,
            alpha=0.7
        )
    plt.xlabel("Privacy (Distance from centroid to true location) [km]")
    plt.ylabel("Utility (Avg distance from true location) [km]")
    plt.title("Privacy vs Utility Tradeoff")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("Privacy_Utility_Tradeoff.png")
    plt.show()


if __name__ == "__main__":
    main()

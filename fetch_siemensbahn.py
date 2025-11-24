import requests
import geopandas as gpd
from pathlib import Path


def fetch_siemensbahn(relation_id=7382983, output_crs="EPSG:25833"):
    """
    Fetch Siemensbahn relation from OpenStreetMap via Overpass API.

    Args:
        relation_id: OSM relation ID (default: 7382983 for Siemensbahn)
        output_crs: Target CRS (default: EPSG:25833 for Berlin/UTM33)
    """
    print(f"Fetching OSM relation {relation_id} from Overpass API...")

    # Overpass API query
    overpass_url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:25];
    relation({relation_id});
    out geom;
    """

    response = requests.post(overpass_url, data={"data": query})
    response.raise_for_status()

    # Save raw JSON
    raw_json = Path("siemensbahn_raw.json")
    raw_json.write_text(response.text)
    print(f"Saved raw response to {raw_json}")

    # Convert to GeoDataFrame using OSM JSON format
    # We need to convert Overpass JSON to GeoJSON first
    data = response.json()

    # For now, let's use OSMnx to properly parse this
    import osmnx as ox

    # Alternative: fetch directly with OSMnx
    print("Converting to GeoDataFrame...")
    gdf = ox.graph_from_place("Siemensbahn, Berlin", network_type="all", which_result=1)

    return gdf


def main():
    """Download Siemensbahn alignment as GeoJSON and Shapefile."""
    import osmnx as ox
    import time

    # Download using OSM API
    print("Fetching Siemensbahn (OSM relation 7382983)...")

    # Try alternative Overpass instances
    overpass_urls = [
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass-api.de/api/interpreter",
        "https://overpass.openstreetmap.ru/api/interpreter",
    ]

    # Use Overpass to get the relation
    query = """
    [out:json][timeout:60];
    relation(7382983);
    (._;>;);
    out geom;
    """

    data = None
    for overpass_url in overpass_urls:
        try:
            print(f"Trying {overpass_url}...")
            response = requests.post(overpass_url, data={"data": query}, timeout=90)
            response.raise_for_status()
            data = response.json()
            print(f"Success!")
            break
        except Exception as e:
            print(f"Failed: {e}")
            time.sleep(2)
            continue

    if data is None:
        raise Exception("All Overpass instances failed")

    # Extract ways from the relation
    ways = [elem for elem in data["elements"] if elem["type"] == "way"]

    print(f"Found {len(ways)} way segments in the relation")

    # Convert to GeoJSON features
    features = []
    for way in ways:
        if "geometry" in way:
            coords = [[node["lon"], node["lat"]] for node in way["geometry"]]
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords
                },
                "properties": {
                    "osm_id": way["id"],
                    "name": way.get("tags", {}).get("name", ""),
                }
            })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame.from_features(geojson, crs="EPSG:4326")

    # Reproject to Berlin CRS
    gdf_utm = gdf.to_crs("EPSG:25833")

    # Save outputs
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    # GeoJSON (WGS84)
    geojson_file = output_dir / "siemensbahn_wgs84.geojson"
    gdf.to_file(geojson_file, driver="GeoJSON")
    print(f"Saved GeoJSON (EPSG:4326): {geojson_file}")

    # GeoJSON (UTM33)
    geojson_utm_file = output_dir / "siemensbahn_utm33.geojson"
    gdf_utm.to_file(geojson_utm_file, driver="GeoJSON")
    print(f"Saved GeoJSON (EPSG:25833): {geojson_utm_file}")

    # Shapefile (UTM33)
    shapefile = output_dir / "siemensbahn_utm33.shp"
    gdf_utm.to_file(shapefile, driver="ESRI Shapefile")
    print(f"Saved Shapefile (EPSG:25833): {shapefile}")

    print(f"\nDataset info:")
    print(f"  Features: {len(gdf)}")
    print(f"  Bounds (WGS84): {gdf.total_bounds}")
    print(f"  Bounds (UTM33): {gdf_utm.total_bounds}")

    # Create HTML map visualization
    import folium

    print("\nCreating interactive HTML map...")

    # Calculate center
    bounds = gdf.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    # Create map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles="OpenStreetMap"
    )

    # Add the Siemensbahn line
    folium.GeoJson(
        gdf,
        name="Siemensbahn",
        style_function=lambda x: {
            "color": "#0066cc",
            "weight": 4,
            "opacity": 0.8
        },
        tooltip=folium.GeoJsonTooltip(fields=["name", "osm_id"], aliases=["Name:", "OSM ID:"])
    ).add_to(m)

    # Add layer control
    folium.LayerControl().add_to(m)

    # Save map
    map_file = output_dir / "siemensbahn_map.html"
    m.save(str(map_file))
    print(f"Saved HTML map: {map_file}")


if __name__ == "__main__":
    main()

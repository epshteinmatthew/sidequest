#objectid = 64
import geopandas
import numpy as np
from shapely.geometry import Point
import stateplane
import overpy
from geopy.distance import geodesic
import json


# Check if the point is within tolerance of any way node
def onRoad(point, way, tolerance_m=15) -> bool:
    for node in way.get_nodes(resolve_missing=True):
        print(geodesic(point, (node.lat, node.lon)).meters)
        if geodesic(point, (node.lat, node.lon)).meters <= tolerance_m:
            return True
    return False

#run once at 3pm daily
def writeRandomCoords() -> bool:
    try:
        gdf = geopandas.read_file("Neighborhood_Map_Atlas_Districts/Neighborhood_Map_Atlas_Districts.shp")
        shape = gdf.geometry.iloc[19]
        #minx, miny, maxx, maxy
        bounds = shape.bounds
        point = Point()
        inbounds = False
        while inbounds == False:
            point = Point(np.random.uniform(bounds[0], bounds[2]), np.random.uniform(bounds[1], bounds[3]))
            inbounds = geopandas.GeoSeries([shape]).contains(point).item()
        coordinates = stateplane.to_latlon(point.x, point.y, 2285)
        with open("coordinates.json", "w") as file:
            file.write(
                '{"lat": ' + coordinates[0].__str__()
                + ', "long": ' + coordinates[1].__str__()
                + '}'
            )
        return True
    except:
        return False


def writeSelectedCoords(lat: float, lon: float) -> bool:
    try:
        gdf = geopandas.read_file("Neighborhood_Map_Atlas_Districts/Neighborhood_Map_Atlas_Districts.shp")
        shape = geopandas.GeoSeries([gdf.geometry.iloc[19]])
        fll = stateplane.from_latlon(lat, lon, 2285)
        point = Point(fll[0], fll[1])
        if(shape.contains(point)):
            with open("coordinates.json", "w") as file:
                file.write(
                    '{"lat": ' + fll[0].__str__()
                    + ', "long": ' + fll[1].__str__()
                    + '}'
                )
            return True
        else:
            return False
    except:
        return False

def block_road(lat, lon, name):
    blockedList = []
    with open("blocked.json", "r") as file:
        blockedList = json.loads(file.read())
    if name in blockedList:
        return False
    api = overpy.Overpass()
    radius = 10  # meters

    # Query for any way with a highway tag around the point
    query = f"""
    (
      way(around:{radius},{lat},{lon})["highway"];
    );
    out body;
    """

    result = api.query(query)

    for way in result.ways:
        if(way.tags.get("name", "Unnamed") == name ):
            if(onRoad((lat, lon), way)):
                try:
                    blockedList.append(name)
                    with open("blocked.json", "w") as file:
                        json.dump(blockedList, file)
                    return True
                except:
                    return False
    return False




print(block_road(47.653231, -122.312107, "15th Avenue Northeast"))






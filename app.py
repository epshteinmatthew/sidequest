#objectid = 64
import geopandas
import numpy as np
from shapely.geometry import Point
import stateplane
import overpy
from geopy.distance import geodesic
import json
from flask import Flask,jsonify
import pytz
from datetime import datetime

pst = pytz.timezone('America/Los_Angeles')


# Check if the point is within tolerance of any way node
def onRoad(point, way, tolerance_m=15) -> bool:
    #check each node (point) in the road path
    for node in way.get_nodes(resolve_missing=True):
        #if we're within 15 meters of the node return true
        if geodesic(point, (node.lat, node.lon)).meters <= tolerance_m:
            return True
    return False

#run once at 3pm daily
def writeRandomCoords() -> bool:
    try:
        #load shapefile and select u district shape
        gdf = geopandas.read_file("Neighborhood_Map_Atlas_Districts/Neighborhood_Map_Atlas_Districts.shp")
        shape = gdf.geometry.iloc[19]
        #minx, miny, maxx, maxy -- the rectangular bounds of the shape
        bounds = shape.bounds
        point = Point()
        inbounds = False
        while inbounds == False:
            #generate a random point between the bounds
            point = Point(np.random.uniform(bounds[0], bounds[2]), np.random.uniform(bounds[1], bounds[3]))
            #check if the random point is in the shape
            inbounds = geopandas.GeoSeries([shape]).contains(point).item()
        #convert from stateplane to normal coordinates
        coordinates = stateplane.to_latlon(point.x, point.y, 2285)
        with open("coordinates.json", "w") as file:
            #wrtie coordinates to file
            file.write(
                '{"lat": ' + coordinates[0].__str__()
                + ', "long": ' + coordinates[1].__str__()
                + '}'
            )
        return True
    except:
        return False


def writeSelectedCoords(lat: float, lon: float) -> bool:
    #same as previous function but you pass in the coordinates
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
    #check if road is already blocked
    with open("blocked.json", "r") as file:
        blockedList = json.loads(file.read())
    if name in blockedList:
        return False

    #get overpass API
    api = overpy.Overpass()
    radius = 10  # meters

    # Query for roads within 10m of coordinates
    query = f"""
    (
      way(around:{radius},{lat},{lon})["highway"];
    );
    out body;
    """

    result = api.query(query)

    for way in result.ways:
        #get the road with the passed in name
        if(way.tags.get("name", "Unnamed") == name ):
            #if we're on the road then add the name of the road to file and write it to disk
            if(onRoad((lat, lon), way)):
                try:
                    blockedList.append(name)
                    with open("blocked.json", "w") as file:
                        json.dump(blockedList, file)
                    return True
                except:
                    return False
    return False




#print(block_road(47.653231, -122.312107, "15th Avenue Northeast"))
app = Flask(__name__)

@app.route("/")
def hello_world():
    return "hello world"

@app.route("/coordinates")
def get_coordinates():
    if (datetime.now(pst).time().hour >= 15):
        with open("coordinates.json", "r") as file:
            #needs to be optimized
            return jsonify(json.loads(file.read()))
    return "Too early!"

#https://dev.to/mar1anna/flask-app-login-with-google-3j24
#do this






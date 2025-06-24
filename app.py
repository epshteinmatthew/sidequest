#objectid = 64
import math
import time

import geopandas
import numpy as np
from shapely.geometry import Point
import stateplane
import overpy
from geopy.distance import geodesic
import json
from flask import Flask, jsonify, url_for, session, request, flash
import pytz
from datetime import datetime
from authlib.integrations.flask_client import OAuth
import os
import setup
from google.oauth2 import id_token
from google.auth.transport import requests
import jwt



from setup import GOOGLE_CLIENT_ID

pst = pytz.timezone('America/Los_Angeles')

def validate(encoded):
    decoded = jwt.decode(encoded, setup.GOOGLE_CLIENT_SECRET, algorithms=["HS256"])
    if(decoded['org'] == "uw.edu" and decoded['exp'] >= time.time() and decoded['cid'] == GOOGLE_CLIENT_ID):
        return True
    else:
        return False

#run once at 3pm daily
def startGame():
    writeRandomCoords()
    with open("blocked.json", "w") as file:
        json.dump([], file)
    if(os.path.isfile("top3/winner")):
        os.unlink("top3/winner")


# Check if the point is within tolerance of any way node
def onRoad(point, way, tolerance_m=15) -> bool:
    #check each node (point) in the road path
    for node in way.get_nodes(resolve_missing=True):
        #if we're within 15 meters of the node return true
        if geodesic(point, (node.lat, node.lon)).meters <= tolerance_m:
            return True
    return False

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
app.secret_key = os.urandom(12)

oauth = OAuth(app)


@app.route("/")
def hello_world():
    return "hello world"

@app.route("/coordinates")
def get_coordinates():
    #maybe remove this gate
    if(validate(request.args['jwt'])):
        if (datetime.now(pst).time().hour >= 15):
            with open("coordinates.json", "r") as file:
                #needs to be optimized
                return jsonify(json.loads(file.read()))
        return "Too early!"
    else:
        return "log in!"


@app.route("/blockroad", methods = ['POST'])
def blockreq():
    if (validate(request.args['jwt'])):
            rjson = request.args
            if (block_road(rjson["lat"], rjson['long'], rjson['name'])):
                with open("blocked.json", "r") as file:
                    # needs to be optimized
                    return jsonify(json.loads(file.read())), 200
            else:
                with open("blocked.json", "r") as file:
                    # needs to be optimized
                    return jsonify(json.loads(file.read())), 400
    else:
        return "log in!"


@app.route("/gamestate")
def gamestate():
    if(validate(request.args['jwt'])):
        coords = (0.0, 0.0)
        with open("coordinates.json", "r") as file:
            j = json.loads(file.read())
            coords = (j["lat"], j["long"])
        blockedList = []
        # check if road is already blocked
        with open("blocked.json", "r") as file:
            blockedList = json.loads(file.read())
        won = os.path.isfile("top3/winner")
        return jsonify(
            {"coords" : coords, "blocked": blockedList, "won": won}
        )
    else:
        return "log in!"

@app.route("/win", methods=['POST'])
def win():
    if (validate(request.args['jwt'])):
        coords = (0.0,0.0)
        with open("coordinates.json", "r") as file:
            j = json.loads(file.read())
            coords = (j["lat"], j["long"])
        rargs = request.args
        dist = 1000
        try:
            dist = math.sqrt((float(rargs['lat']) - float(coords[0])) ** 2 + (float(rargs['long']) - float(coords[0])))
        except:
            return "bad arguments", 400
        if(dist <= 15):
            if 'file' not in request.files:
                return 'No file', 400
            file = request.files['file']
            # If the user does not select a file, the browser submits an
            # empty file without a filename.
            if file.filename == '':
                return 'No selected file', 400
            if file:
                #change?
                filename = "winner"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                return "file saved", 200
        else:
            return "not winner", 400
    else:
        return "log in!"

@app.route('/google', methods=['POST'])
def google():
    CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'
    try:
        # Specify the WEB_CLIENT_ID of the app that accesses the backend:
        idinfo = id_token.verify_oauth2_token(request.args['token'], requests.Request(), GOOGLE_CLIENT_ID)
        if (idinfo['aud'] == GOOGLE_CLIENT_ID and 'accounts.google.com' in idinfo['iss'] and idinfo['hd'] == "uw.edu" and idinfo['exp'] >= time.time()):
            #plus one day
            encoded_jwt = jwt.encode({'org': idinfo['hd'], 'cid': idinfo['aud'], 'exp': time.time() + 86400}, setup.GOOGLE_CLIENT_SECRET, algorithm="HS256")
            return encoded_jwt, 200
        else:
            return "not allowed", 403
    except:
        return "not allowed", 403









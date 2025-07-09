#objectid = 64
import math
import time

import geopandas
import numpy as np
from numpy.ma.core import arctan
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


def vincenty(lat1, long1,lat2, long2):
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    l1 = math.radians(long1)
    l2 = math.radians(long2)
    a = 6378137.0
    f = 1/298.257223563
    b = 6356752.314245
    u1 = arctan((1-f) * math.tan(p1))
    u2 = arctan((1-f) * math.tan(p2))
    bigL = l2 - l1
    lmd = bigL
    deltalmd = 100
    sinsigma, cossigma, sigma, sinalpha, cossquaredalpha, cos2sigmasubm, C = 0,0,0,0,0,0,0
    while deltalmd > (10**-12):
        sinsigma = math.sqrt(
            (math.cos(u2) * math.sin(lmd)) ** 2 +
            (math.cos(u1) * math.sin(u2) - math.sin(u1) * math.cos(u2) * math.cos(lmd)) ** 2
        )
        cossigma = math.sin(u1) * math.sin(u2) +  math.cos(u1) * math.cos(u2) * math.cos(lmd)
        sigma = np.arctan2(sinsigma, cossigma)
        sinalpha = math.cos(u1) * math.cos(u2) * math.sin(lmd) / sinsigma
        cossquaredalpha = 1 - sinalpha ** 2
        cos2sigmasubm = cossigma - 2 * math.sin(u1) * math.sin(u2)/cossquaredalpha
        C = (f/16)*cossquaredalpha*(4+f*(4-3*cossquaredalpha))
        olmd = lmd
        lmd = bigL + (1-C)*f*sinalpha * (sigma + C*sinsigma*(cos2sigmasubm + C*cossigma * (-1 + 2*(cos2sigmasubm**2))))
        deltalmd = math.fabs(lmd - olmd)
    usqared = cossquaredalpha * (a**2 - b**2)/(b**2)
    A = 1 + (usqared/16384)*(4096+usqared*(-768 + usqared *(320-175*usqared)))
    B = (usqared/1024) * (256 + usqared * (-128 + usqared * (74 - 47*usqared)))
    deltasigma = B * sinsigma * (cos2sigmasubm + (B/4)*(cossigma * (-1+2*(cos2sigmasubm ** 2)) - (B/6)*cos2sigmasubm*(-3+4*(sinsigma ** 2))*(-3*4*(cos2sigmasubm ** 2))))
    distance = b * A *(sigma - deltasigma)
    print(distance)
    return distance

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
    if(validate(request.headers['Authorization'])):
        if (datetime.now(pst).time().hour >= 15):
            with open("coordinates.json", "r") as file:
                    #needs to be optimized
                return jsonify(json.loads(file.read()))
        return "Too early!"
    else:
        return "log in!"


@app.route("/blockable_roads")
def get_blockable_roads():
    if (validate(request.headers['Authorization'])):
        blockedList = []
        # check if road is already blocked
        with open("blocked.json", "r") as file:
            blockedList = json.loads(file.read())
        # get overpass API
        api = overpy.Overpass()
        radius = 10  # meters

        # Query for roads within 10m of coordinates
        query = f"""
                (
                  way(around:{radius},{request.args['lat']},{request.args['long']})["highway"];
                );
                out body;
                """

        result = api.query(query)

        return jsonify([way.tags.get("name", "Unnamed") for way in result.ways if
                way.tags.get("name", "Unnamed") not in blockedList])
    else:
        return "log in!"


@app.route("/blockroad", methods = ['POST'])
def blockreq():
    if (validate(request.headers['Authorization'])):
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
    if(validate(request.headers['Authorization'])):
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
    if (validate(request.headers['Authorization'])):
        coords = (0.0,0.0)
        with open("coordinates.json", "r") as file:
            j = json.loads(file.read())
            coords = (j["lat"], j["long"])
        rargs = request.args
        dist = 1000
        try:
            dist = vincenty(float(rargs['lat']), float(rargs['long']), float(coords[0]), float(coords[1]))
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



@app.route("/gamestate_dist", methods=['GET'])
def dist_and_direction():
    if (validate(request.headers['Authorization'])):
        coords = (0.0,0.0)
        with open("coordinates.json", "r") as file:
            j = json.loads(file.read())
            coords = (j["lat"], j["long"])
        rargs = request.args
        dist = 1000
        try:
            dist = vincenty(float(rargs['lat']), float(rargs['long']), float(coords[0]), float(coords[1]))
        except:
            return "bad arguments", 400
        return jsonify({
            "dist": dist,
            "direction": math.degrees(arctan((float(rargs['long'])-float(coords[1]))/(float(rargs['lat'])-float(coords[0])))),
            "won": os.path.isfile("top3/winner")
        })
    else:
        return "log in!"










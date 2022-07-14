#!/usr/bin/python3
from flask import Flask,render_template,request
import os
import gpx_splitter
from simplejson import JSONEncoder
import sys

app = Flask(__name__)

@app.route("/")
def hello_world():
    return(render_template("index.html"))

@app.route("/load", methods=['GET', 'POST'])
def load_gpx():
    json = {}
    if (request.method == "POST"):
        json = request.get_json()
        gpx_data = gpx_splitter.load_gpx(json['gpx'])
        gpx_info = gpx_splitter.json_get_gpx_info(gpx_data)

    if (request.method == "GET"):
        json = {'gpx': "nothing to see here"}

    return(gpx_info)

@app.route("/process", methods=['GET', 'POST'])
def process_gpx():
    json = {}
    gpx_xml = ""
    if (request.method == "POST"):
        json = request.get_json()
        gpx_data = gpx_splitter.load_gpx(json['gpx'])
        gpx_xml = gpx_splitter.xml_get_split_gpx(gpx_data,json['attributes'])

    if (request.method == "GET"):
        json = {'gpx': "nothing to see here"}

    return(JSONEncoder().encode({'gpx':gpx_xml}))


@app.route("/update_airports", methods=['GET'])
def update_airports():
    url = "https://davidmegginson.github.io/ourairports-data/airports.csv"
    os.system(f"curl -o airports.csv {url}")
    
    return(JSONEncoder().encode({'msg':f"Airports updated from {url}"}))


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(sys.argv[1]), debug=False)
    
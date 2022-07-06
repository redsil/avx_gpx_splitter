#!/usr/bin/python3
from flask import Flask,render_template,request
import gpx_splitter

app = Flask(__name__)

@app.route("/")
def hello_world():
    return(render_template("index.html"))

@app.route("/process", methods=['GET', 'POST'])
def process_gpx():
    json = {}
    if (request.method == "POST"):
        json = request.get_json()
        gpx_data = gpx_splitter.load_gpx(json['gpx'])
        gpx_info = gpx_splitter.json_get_gpx_info(gpx_data)

    if (request.method == "GET"):
        json = {'gpx': "nothing to see here"}


    
    return(gpx_info)

#!/usr/bin/python3
from flask import Flask,render_template,request
import os
import gpx_splitter
from simplejson import JSONEncoder
import sys
from fs_track import fs_track

app = Flask(__name__)

# Instance Tracker
fstracker = fs_track(outdir="tracks")
fstracker.start_thread()

@app.route("/")
def index():
    return(render_template("index.html"))

@app.route("/load", methods=['POST'])
def load_gpx():
    json = {}
    if (request.method == "POST"):
        json = request.get_json()
        gpx_data = gpx_splitter.load_gpx(json['gpx'])
        gpx_info = gpx_splitter.json_get_gpx_info(gpx_data)

        return(gpx_info)



@app.route("/process", methods=['GET', 'POST'])
def process_gpx():
    json = {}
    gpx_xml = ""
    if (request.method == "POST"):
        json = request.get_json()
        gpx_data = gpx_splitter.load_gpx(json['gpx'])
        gpx_xml = gpx_splitter.xml_get_split_gpx(gpx_data,json['attributes'])

        if (gpx_xml == ""):
            json = {'error':'Failed to process gpx - airports database may need update'} 
        else:
            json = {'gpx':gpx_xml}


    if (request.method == "GET"):
        json = {'gpx': "nothing to see here"}

    return(JSONEncoder().encode(json))


@app.route("/update_airports", methods=['GET'])
def update_airports():
    url = "https://davidmegginson.github.io/ourairports-data/airports.csv"
    os.system(f"curl -o airports.csv {url}")
    
    return(JSONEncoder().encode({'msg':f"Airports updated from {url}"}))


@app.route("/tracker", methods=['GET'])
def tracker():
    ret_val = {};
    if (request.method == "GET"):
        args = request.args
        if 'is_connected' in args:
            ret_val['connected'] = fstracker.is_connected()
        if 'is_tracking' in args:
            ret_val['tracking'] = fstracker.is_tracking()
        if 'is_running' in args:
            ret_val['running'] = fstracker.is_running()
        if 'get_gpx' in args:
            if 'filename' in args:
                ret_val['gpx_data']  = fstracker.read_gpx(args['filename'])
        if 'list_files' in args:
            ret_val['files'] = fstracker.list_files()
        if 'command' in args:
            if args['command'] == 'pause':
                ret_val['status'] = True
                if fstracker.enabled:
                    fstracker.disable()
                else:
                    fstracker.enable()
            if args['command'] == 'flush':
                fstracker.close_gpx()
            if args['command'] == 'delete_gpx':
                if 'filename' in args:
                    print("deleting ${args['filename']}")
                    ret_val['status']  = fstracker.delete_gpx(args['filename'])
    return(JSONEncoder().encode(ret_val))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(sys.argv[1]), debug=False)
 

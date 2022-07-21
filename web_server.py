#!/usr/bin/python3
from flask import Flask,render_template,request,Response
import os
import gpx_splitter
from simplejson import JSONEncoder
import sys
from fs_track import fs_track
import queue

# https://maxhalford.github.io/blog/flask-sse-no-deps/
class MessageAnnouncer:

    def __init__(self):
        self.listeners = []

    def listen(self):
        q = queue.Queue(maxsize=10)
        self.listeners.append(q)
        return q

    def announce(self, msg):
        for i in reversed(range(len(self.listeners))):
            try:
                self.listeners[i].put_nowait(msg)
            except queue.Full:
                del self.listeners[i]

    def format_sse(self,data: str, event=None) -> str:
        msg = f'data: {data}\n\n'
        if event is not None:
            msg = f'event: {event}\n{msg}'
        return msg


app = Flask(__name__)

announcer = MessageAnnouncer()

def get_message(data={}):
    data_str = JSONEncoder().encode(data)
    event_obj = formated_msg = announcer.format_sse(data=data_str)
    announcer.announce(event_obj)

# Instance Tracker
fstracker = fs_track(outdir="tracks",event_update=lambda msg="" : get_message(msg))
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
            if ret_val['tracking']:
                ret_val['current_track'] = fstracker.current_file()
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


@app.route('/subscribe', methods=['GET'])
def subscribe():

    def stream():
        messages = announcer.listen()  # returns a queue.Queue
        while True:
            msg = messages.get()  # blocks until a new message arrives
            yield msg

    return Response(stream(), mimetype='text/event-stream')

@app.route('/ping')
def ping():
    msg = announcer.format_sse(data='pong')
    announcer.announce(msg=msg)
    return {'message':msg}, 200


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(sys.argv[1]), debug=False)
 

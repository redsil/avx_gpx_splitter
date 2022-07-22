#!/usr/bin/python3
from socket import *
from datetime import *
import re
import argparse
from time import sleep
import math
import time
import threading
import os
import gpx_splitter
import gpxpy
import geopy.distance
import math
import numpy as np



class test_sim:
    def __init__(self,**args):
        if (not 'port' in args):
            args['port'] = 49010

        self.s=socket(AF_INET, SOCK_DGRAM)
        self.s.settimeout(60)
#        self.s.bind(('localhost',args['port']))
        self.s.connect(('localhost',49002))
        self.port = args['port']

        self.gpx_file = args['file']
        


    def get_bearing(self,lat1,lon1,lat2,lon2):
        dLon = lon2 - lon1;
        y = math.sin(dLon) * math.cos(lat2);
        x = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dLon);
        brng = np.rad2deg(math.atan2(y, x));
        if brng < 0: brng+= 360
        return brng


    def run(self):
        fd = open(self.gpx_file,mode="r")
        gpx_string = fd.read()
        gpx_data = gpx_splitter.load_gpx(gpx_string)
        fd.close()

        last_point = None
        speed = 0.0
        bearing = 0.0
        
        for point in gpx_data.walk(only_points=True):
            lon = point.longitude
            lat = point.latitude
            alt = point.elevation        
            time = point.time

            if (last_point):
                dist = geopy.distance.geodesic((last_point.latitude,last_point.longitude),(lat,lon)).mi
                speed = 3600 * dist / 3
                bearing = self.get_bearing(last_point.latitude,last_point.longitude,lat,lon)

            last_point = point

            print(f"XGPSFlight Events,{lon},{lat},{alt},{bearing},{speed}")          
            m=self.s.send(f"XGPSFlight Events,{lon},{lat},{alt},{int(bearing)},{int(speed)}".encode(encoding='UTF-8'))

            sleep(3)
                  

    
if (__name__ == "__main__"):
    ap = argparse.ArgumentParser(description="Simulate Xplane output for position data using a GPX file")
    ap.add_argument('-port','-p',help='Specify the port to listen to, default 49002 (xplane UDP broadcast)',default=49002)
    ap.add_argument('-gpx',help='gpx file to simulate')
    args = ap.parse_args()
    
    sim = test_sim(port=args.port,file=args.gpx)
    sim.run()
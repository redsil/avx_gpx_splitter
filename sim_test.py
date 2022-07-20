#!/usr/bin/python3
from asyncio import wait_for
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
        


    def run(self):
        fd = open(self.gpx_file,mode="r")
        gpx_string = fd.read()
        gpx_data = gpx_splitter.load_gpx(gpx_string)
        fd.close()

        for point in gpx_data.walk(only_points=True):
            lon = point.longitude
            lat = point.latitude
            alt = point.elevation        
            time = point.time

            print(f"XGPSFlight Events,{lon},{lat},{alt}")          
            m=self.s.send(f"XGPSFlight Events,{lon},{lat},{alt}".encode(encoding='UTF-8'))

            sleep(3)
                  

    
if (__name__ == "__main__"):
    ap = argparse.ArgumentParser(description="Simulate Xplane output for position data using a GPX file")
    ap.add_argument('-port','-p',help='Specify the port to listen to, default 49002 (xplane UDP broadcast)',default=49002)
    ap.add_argument('-gpx',help='gpx file to simulate')
    args = ap.parse_args()
    
    sim = test_sim(port=args.port,file=args.gpx)
    sim.run()
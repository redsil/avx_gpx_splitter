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
from itsdangerous import NoneAlgorithm


class sim_track:
    def __init__(self,**args):
        self.s=socket(AF_INET, SOCK_DGRAM)
        self.s.settimeout(60)
        self.s.bind(('',args['port']))
        self.port = args['port']

        self.file_format = args['format']
        self.outdir = args['outdir']
        
        self.running = False

        self.last_pos_time = 0.0
        self.last_lon = 0.0
        self.last_lat = 0.0
        self.enabled = False
        self.sample_rate = 3  # how often to post a position to the gpx file - used to average out rounding errors
        self.completed_gpx = []
        self.close_gpx = False  # used to trigger the thread loop and close out the gpx file
        self.have_connection = False

    def is_connected(self):
        return self.have_connection

    def bind_socket(self):
        # 49002
        return self.s.bind(('',self.port))

    def start(self):
        self.enabled = True    

    def stop(self):
        self.enabled = False

    def close_gpx(self):
        self.close_gpx = True

    def gen_filename(self,format):

        if (format):
            dt = datetime.now()
            filename = format
            filename = re.sub(pattern=r'%D',repl=str(dt.date()),string=filename,count=0)
            filename = re.sub(pattern=r'%T',repl=f'{dt.hour:02}{dt.second:02}',string=filename,count=0)
        else:
            filename = "track.gpx"
        return(filename)

    def is_valid_position(self,lat,lon,alt):
        # position valid if not around sea level at 0,0 (MSFS2020 reset position)
        if (alt < 100 and
            math.fabs(lat) < .5 and
            math.fabs(lat) < .5):
            return(False)

        # position not valid if there was a sudden large change in location
        elif (math.fabs(lon - self.last_lon) > 1 or
                math.fabs(lat - self.last_lat) > 1):
            return(False)
        else:
            return(True)
            
    def parse_position(self,data,ts):
        # "XGPSFlight Events,-83.208471,40.124682,2310.1),58.3,75.1"
        fields = data.split(r',')
        lat,lon,alt = (None,None,None)
        gpx = ""
        # This is position data.  Time is sent with more precision than a GPX can store and this can cause speed fluctuations when
        # rounding errors become high.  We will average this out by taking samples every N seconds
        if (re.search(r'XGPS',fields[0])):
            
            alt = re.sub(r'([\.\d]+).*',r'\1',fields[3])
            alt = float(alt)

            lat = float(fields[2])
            lon = float(fields[1])

            gpx = f'''\t<trkpt lon="{fields[1]}" lat="{fields[2]}">
\t\t<ele>{alt:.1f}</ele>
\t\t<time>{ts.isoformat("T","seconds")}Z</time>
\t</trkpt>'''


        return(lat,lon,alt,gpx)

    def start_thread(self):
        thread = threading.Thread(target=self.run, args=(),daemon=True)
        thread.start()
        print("Thread Started")
        return(thread)

    def finish_segment(self,file):
        print("  </trkseg>",file=file,flush=True)

    def finish_gpx(self,file):
        if (not file.closed):
            print(" </trk>",file=file)
            print("</gpx>",file=file)
            self.completed_gpx.append(gpx_file.name)
            file.close()
        
    def run(self):
        wait_for_position = True
        self.start()
        
        self.last_pos_time = 0.0
        self.last_lon = 0.0
        self.last_lat = 0.0


        gpx_file = None

        while True:
            if self.close_gpx and gpx_file:
                self.finish_gpx(gpx_file)
                self.close_gpx = False

            if self.enabled:
                m = None
                try:
                    m=self.s.recvfrom(1024)
                    ts = datetime.utcnow()
                    self.have_connection = True

                except OSError as msg:
                    if (self.have_connection == True):
                        print("Connection closed, finalizing GPX file")
                        self.finish_gpx(gpx_file)
                        self.have_connection = False
                    continue
                        
                try:
                    data = m[0].decode('utf-8')
                except:
                    print("Failed to decode packet, skipping")
                    continue
                        
                lat,lon,alt,gpx_string = self.parse_position(data,ts)

                if (not (lat and lon and alt)):
                    if (time.time() - self.last_pos_time) <= (self.sample_rate * 3):
                        # Give 3 tries until we give up waiting for position data
                        continue
                    
                    # No longer seeing position updates, close segment and wait for new position
                    elif not wait_for_position:
                        print("Closing segment due to not seeing position updates in last 10 seconds")
                        print("  </trkseg>",file=gpx_file,flush=True)
                        wait_for_position = True

                else:
                    if wait_for_position and self.is_valid_position(lat,lon,alt):
                        # Create new file if needed
                        if not gpx_file or gpx_file.closed:
                            filename = f'{self.outdir}/{self.gen_filename(self.file_format)}'
                            gpx_file = open(filename,'w')            
                            print(f"First position received {lat:.2f},{lon:.2f},{alt:.2f}, starting GPX generation {filename}")
                            print("""<?xml version="1.0" encoding="UTF-8"?>
        <gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="AVX flight tracker" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">
        <trk>
                """,file=gpx_file)

                        # Start segment 
                        print("  <trkseg>",file=gpx_file,flush=True)
                        wait_for_position = False

                    # ongoing segment
                    if not wait_for_position and (time.time() - self.last_pos_time) >= self.sample_rate:
                        if not self.is_valid_position(lat,lon,alt):
                            print("Got invalid position, closing segment and waiting for new position to start a new track segment")
                            print("  </trkseg>",file=gpx_file,flush=True)
                            wait_for_position = True

                        else:
                            print(gpx_string,file=gpx_file,flush=True)
                            self.last_pos_time = time.time()                

                    self.last_lat = lat
                    self.last_lon = lon
            else:  # not enabled
                self.close_gpx(gpx_file)
                self.have_connection = False
                sleep(5)

    
if (__name__ == "__main__"):
    ap = argparse.ArgumentParser(description="Monitor Xplane output for position data and create GPX files")
    ap.add_argument('-outdir','-o',help='Specify where GPX files will be written to',required=True)
    ap.add_argument('-format',help='Specify format of GPX file naming.  use %%D for current date, %%T for current time')
    ap.add_argument('-port','-p',help='Specify the port to listen to, default 49002 (xplane UDP broadcast)',default=49002)
    args = ap.parse_args()
    
    tracker = sim_track(outdir=args.outdir, port=int(args.port), format=args.format)
    t_thread = tracker.start_thread()
    t_thread.join()
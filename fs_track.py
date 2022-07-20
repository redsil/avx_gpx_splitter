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
import os


class fs_track:
    def __init__(self,**args):
        if (not 'port' in args):
            args['port'] = 49002
        if (not 'format' in args ):
            args['format'] = 'track_%D_%T.gpx'
        if ('event_update' in args):
            self.event_update = args['event_update']
        else:
            self.event_update = lambda : False

        self.s=socket(AF_INET, SOCK_DGRAM)
        self.s.settimeout(60)
        self.s.bind(('',args['port']))
        self.port = args['port']

        self.file_format = args['format']
        self.outdir = args['outdir']
        self.gpx_file = None
        
        self.running = False

        self.last_pos_time = 0.0
        self.last_lon = 0.0
        self.last_lat = 0.0
        self.enabled = True
        self.sample_rate = 3  # how often to post a position to the gpx file - used to average out rounding errors
        self.completed_gpx = []
        self.__close_gpx = False  # used to trigger the thread loop and close out the gpx file
        self.have_connection = False
        self.wait_for_position = True # false when actively tracking and creating a segment
        self.__num_segments = 0

    def is_connected(self):
        return self.have_connection

    def enable(self):
        self.enabled = True    

    def disable(self):
        self.enabled = False

    def close_gpx(self):
        self.__close_gpx = True
        while self.__close_gpx:
            sleep(1)

    def list_files(self):
        files = [ f"{self.outdir}/{file}"  for file in os.listdir(self.outdir)  if not self.gpx_file or self.gpx_file.closed or f"{self.outdir}/{file}" != self.gpx_file.name]

        return sorted(files)

    def is_tracking(self):
        return not self.wait_for_position

    def current_file(self):
        if not self.gpx_file or self.gpx_file.closed:
            return ""
        else:
            return self.gpx_file.name

    def is_running(self):
        return self.running and self.enabled

    def delete_gpx(self,filename):
        try:
            os.remove(filename)
            return True
        except OSError as e:
            print(f"Unable to delete {filename}: {e.strerror}")
            return False

    def read_gpx(self,filename):
        try:
            fd = open(filename)
            gpx_data = fd.read()
            fd.close()
            return(gpx_data)
        except Exception as e:
            print(f"Error: unable to read {filename}: {e}")
            return None
        

    def gen_filename(self,format):

        dt = datetime.now()
        date_str = str(dt.date())
        time_str = f'{dt.hour:02}{dt.minute:02}'
        if (format):
            filename = format
            filename = re.sub(pattern=r'%D',repl=date_str,string=filename,count=0)
            filename = re.sub(pattern=r'%T',repl=time_str,string=filename,count=0)
        else:
            filename = f"track_{date_str}_{time_str}.gpx"
        return(filename)

    def __is_valid_position(self,lat,lon,alt):
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
            
    def __parse_position(self,data,ts):
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
        thread = threading.Thread(target=self.__run, args=(),daemon=True)
        thread.start()
        print("Thread Started")
        self.running = True
        self.event_update()
        return(thread)

    def __finish_segment(self):
        if (not self.gpx_file.closed):
            print("  </trkseg>",file=self.gpx_file,flush=True)

    def __start_segment(self):
        if (not self.gpx_file.closed):
            self.__num_segments += 1
            print("  <trkseg>",file=self.gpx_file,flush=True)
                        

    def __finish_gpx(self):
        if (not self.gpx_file.closed):
            self.__finish_segment()
            print(" </trk>",file=self.gpx_file)
            print("</gpx>",file=self.gpx_file,flush=True)
            self.completed_gpx.append(self.gpx_file.name)
            self.gpx_file.close()
            self.wait_for_position = True  # reset waiting state so we can generate a new GPX when a position received
            self.__num_segments = 0
            self.event_update()
        
    def __run(self):
        # create output dir if it doesn't exist
        os.makedirs(self.outdir,exist_ok=True)
        
        self.last_pos_time = 0.0
        self.last_lon = 0.0
        self.last_lat = 0.0

        while True:
            if self.__close_gpx and self.gpx_file:
                self.__finish_gpx()
                self.__close_gpx = False

            if self.enabled:
                m = None
                try:
                    m=self.s.recvfrom(1024)
                    ts = datetime.utcnow()
                    self.have_connection = True

                except OSError as msg:
                    if (self.have_connection == True):
                        print("Connection closed, finalizing GPX file")
                        self.__finish_gpx()
                        self.have_connection = False
                    continue
                        
                try:
                    data = m[0].decode('utf-8')
                except:
                    print("Failed to decode packet, skipping")
                    continue
                        
                lat,lon,alt,gpx_string = self.__parse_position(data,ts)

                if (not (lat and lon and alt)):
                    if (time.time() - self.last_pos_time) <= (self.sample_rate * 3):
                        # Give 3 tries until we give up waiting for position data
                        continue
                    
                    # No longer seeing position updates, close segment and wait for new position
                    elif not self.wait_for_position:
                        print("Closing segment due to not seeing position updates in last 10 seconds")
                        self.__finish_segment()
                        self.wait_for_position = True

                else:
                    if self.wait_for_position and self.__is_valid_position(lat,lon,alt):
                        # Create new file if needed
                        if not self.gpx_file or self.gpx_file.closed:
                            filename = f'{self.outdir}/{self.gen_filename(self.file_format)}'
                            self.gpx_file = open(filename,'w')            
                            print(f"First position received {lat:.2f},{lon:.2f},{alt:.2f}, starting GPX generation {filename}")
                            print("""<?xml version="1.0" encoding="UTF-8"?>
        <gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="AVX flight tracker" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">
        <trk>
                """,file=self.gpx_file,flush=True)
                            self.event_update()

                        # Start segment 
                        self.__num_segments = 0
                        self.__start_segment()
                        self.wait_for_position = False

                    # ongoing segment
                    if not self.wait_for_position and (time.time() - self.last_pos_time) >= self.sample_rate:
                        if not self.__is_valid_position(lat,lon,alt):
                            print("Got invalid position, closing segment and waiting for new position to start a new track segment")
                            self.finish_segment()
                            self.wait_for_position = True
                            self.event_update()

                        else:
                            print(gpx_string,file=self.gpx_file,flush=True)
                            self.last_pos_time = time.time()                

                    self.last_lat = lat
                    self.last_lon = lon
            else:  # not enabled
                self.__finish_gpx()
                self.have_connection = False
                sleep(5)

    
if (__name__ == "__main__"):
    ap = argparse.ArgumentParser(description="Monitor Xplane output for position data and create GPX files")
    ap.add_argument('-outdir','-o',help='Specify where GPX files will be written to',required=True)
    ap.add_argument('-format',help='Specify format of GPX file naming.  use %%D for current date, %%T for current time')
    ap.add_argument('-port','-p',help='Specify the port to listen to, default 49002 (xplane UDP broadcast)',default=49002)
    args = ap.parse_args()
    
    tracker = fs_track(outdir=args.outdir, port=int(args.port), format=args.format)
    t_thread = tracker.start_thread()
    t_thread.join()
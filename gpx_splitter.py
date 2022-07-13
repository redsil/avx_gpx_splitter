#!/usr/bin/python3
import sys
import os
import csv
import gpxpy
import gpxpy.gpx
import geopy.distance
import regex
import copy
from io import  StringIO
import datetime

from simplejson import JSONEncoder

def meters_to_nm(meters):
    return meters/1852 

def meters_to_feet(meters):
    return meters * 3.28084 

def filter_airports(airports,gpx): # lat1,lon1,lat2,lon2):
    # FIMXME - handling for wrap around lon/lat
    filtered_airports = []
    bounds = gpx.get_bounds()
        

    for airport in airports:
        lat = float(airport['latitude_deg'])
        lon = float(airport['longitude_deg'])

        track_airports = []
        if (lat > bounds.min_latitude and lat < bounds.max_latitude and lon > bounds.min_longitude and lon < bounds.max_longitude):
            track_airports.append(airport)

        # append new airports to filtered list
        [filtered_airports.append(airport) for airport in track_airports if (airport['id'] not in [airport['id'] for airport in filtered_airports])]

            
    return filtered_airports
    

def load_airports(filename):
    airports = []
    with open(filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            airport = {}
            id = None
            for col in row: 
                if (col == "id"): id = row[col]
                airport[col] = row[col]
            airports.append(airport)
    return airports


def closest_airport(airports,lat,lon,alt=None):
    closest = None
    closest_dist = 999999
    for airport in airports:
        if (regex.match(r'.*port.*',airport['type'])):
            airport_lat = float(airport['latitude_deg'])
            airport_lon = float(airport['longitude_deg'])
            if (airport['elevation_ft'] != ''):
                airport_alt = float(airport['elevation_ft']);
            else:
                continue
            if (abs(lat - airport_lat ) < 0.1):
                if (abs(lon - airport_lon) < 0.1):
                    if (not alt or (abs(alt - airport_alt)  < 100)):
                        dist = geopy.distance.geodesic((lat,lon),(airport_lat,airport_lon)).mi
                        if (dist < 5 and (not closest or dist < closest_dist)):
                            closest = airport
                            closest_dist = dist
    return closest

def load_gpx(text):
    gpx_stream = StringIO(text)
    gpx_data = gpxpy.parse(gpx_stream)
    return gpx_data


# Given the gpx and list of airports, find where aiports were itermediate destinations and break into segments
def split_into_segments(gpx,airports):
    split_points = []
    for track_no,track in enumerate(gpx.tracks):
        for segment_no,segment in enumerate(track.segments):
            start = segment.points[0]

            last_airport = closest_airport(airports,start.latitude,start.longitude,meters_to_feet(start.elevation))
            if (not last_airport):
                continue

            last_point = None
            for point_no,point in enumerate(segment.points):
                if (last_point):
                    if (point.time_difference(last_point) > 600):
                        cur_airport = closest_airport(airports,last_point.latitude,last_point.longitude,meters_to_feet(last_point.elevation))
                        if (cur_airport['ident'] != last_airport['ident']):
                            split_points.append([track_no,segment_no,point_no-1])
                            last_airport = closest_airport(airports,point.latitude,point.longitude,meters_to_feet(point.elevation))

                last_point = point

    # Split in reverse, otherwise the segment numbers won't map correctly
    for split in reversed(split_points):
        gpx.tracks[split[0]].split(split[1],split[2]) 

# Put each segment into its own track
def split_into_tracks(gpx): 
    segment_list = [segment for track in gpx.tracks for segment in track.segments]

    new_gpx = copy.copy(gpx)
    
    # template track
    template_track = copy.copy(gpx.tracks[0])
    template_track.segments = []
    new_gpx.tracks = []

    for segment in segment_list:
        new_track = copy.copy(template_track)
        new_track.segments = []

        new_track.segments.append(segment)
        new_gpx.tracks.append(new_track)

    return new_gpx
    

def delete_track(gpx,track_no):
    print(f"DEBUG deleting track {track_no} of {len(gpx.tracks)}")
    del gpx.tracks[track_no]                            

def set_track_name(gpx,track_no,name):
    if (track_no >= len(gpx.tracks)):
        return False

    gpx.tracks[track_no].name = name
    return True

def set_track_desc(gpx,track_no,desc):
    if (track_no >= len(gpx.tracks)):
        return False

    gpx.tracks[track_no].description = desc
    return True


def get_airport_info(airports,ident):
    matches = [airport for airport in airports if (airport['ident'] == ident)]
    return matches[0]

def segment_info(segment,airports):
    info = {}
#    for track_no,track in enumerate(gpx_data.tracks):
#        for segment_no,segment in enumerate(track.segments):
    if (len(segment.points)):
        start = segment.points[0]
        end = segment.points[-1]
        start_airport = closest_airport(airports,start.latitude,start.longitude,meters_to_feet(start.elevation))
        end_airport = closest_airport(airports,end.latitude,end.longitude,meters_to_feet(end.elevation))
        elevations = segment.get_elevation_extremes()

        unknown_airport = {'ident':'NONE','name':"",'municipality':"",'iso_region':""}
        if (not start_airport):
            start_airport = unknown_airport
        if (not end_airport):
            end_airport = unknown_airport

        info = {'depart': start_airport['ident'],
                'arrive':end_airport['ident'],
                'time': str(start.time),
                'duration':str(datetime.timedelta(seconds=segment.get_duration())),
                'distance': int(meters_to_nm(segment.length_2d())),
                'max_alt': int(meters_to_feet(elevations.maximum))
        }
        info['description'] = f"""depart:   {info['depart']} {start_airport['name']}, {start_airport['municipality']} {start_airport['iso_region']}
arrive:   {info['arrive']} {end_airport['name']}, {end_airport['municipality']} {end_airport['iso_region']}
date:     {info['time']}
duration: {info['duration']}
distance: {info['distance']}nm 
max alt:  {info['max_alt']}ft
"""

    return info
    
# Attributes is list of dicts (by track) where dict has optional fields name and description 
# An attribute index that is None means to remove that track from the generated gpx
def xml_get_split_gpx(gpx_data,attributes):

    airports = filter_airports(load_airports("airports.csv"),gpx_data)
    split_into_segments(gpx_data,airports)
    new_gpx = split_into_tracks(gpx_data)
    print(f"DEBUG {attributes}")

    # Update names and descriptions
    for i,att in enumerate(attributes):
        if ("name" in att):
            set_track_name(new_gpx,i,att['name'])

            if ("description" in att):
                set_track_desc(new_gpx,i,att['description'])

    for i,att in reversed(list(enumerate(attributes))):
        if (not "name" in att):
            # Remove tracks not specified                
            delete_track(new_gpx,i)
    
    return new_gpx.to_xml()

def json_get_gpx_info(gpx_data):
    airports = filter_airports(load_airports("airports.csv"),gpx_data)
    split_into_segments(gpx_data,airports)
    info_list = [info for track in gpx_data.tracks for info in [segment_info(segment,airports) for segment in track.segments]]
    return JSONEncoder().encode({'xml':gpx_data.to_xml(),'info': info_list})

    


######################################################################################
# Todo - add arg parsing
def run():
    gpx_file = open(sys.argv[1],'r')
    gpx_string = gpx_file.read()
    gpx_data = load_gpx(gpx_string)

    airports = filter_airports(load_airports("airports.csv"),gpx_data)

    # Split any segments if there is a landing
    print("Finding splits...")
    split_into_segments(gpx_data,airports)

    print("Getting segment info")
    info_list = [info for track in gpx_data.tracks for info in [segment_info(segment,airports) for segment in track.segments]]
    for info in info_list:
        print(f"{info['depart']} {info['arrive']} {info['time']}  {info['duration']} {info['distance']}nm {info['max_alt']}ft")

    new_gpx = split_into_tracks(gpx_data)

    print("Set track names")

    for index,info in enumerate(info_list):
        set_track_name(new_gpx,index,f"{info_list[index]['depart']} {info_list[index]['arrive']}")
        set_track_desc(new_gpx,index,info_list[index]['description'])


    #delete_track(new_gpx,2)
    print(new_gpx.to_xml())


if (__name__ == "__main__"):
    run()

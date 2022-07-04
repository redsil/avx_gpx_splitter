#!/usr/bin/python3
import sys
import os
import csv
import gpxpy
import gpxpy.gpx
import geopy.distance
import regex
from io import  StringIO
import datetime

def meters_to_nm(meters):
    return(meters/1852 )

def meters_to_feet(meters):
    return(meters * 3.28084 )

def load_airports(filename):
    airports = {}
    with open(filename, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            airport = {}
            id = None
            for col in row: 
                if (col == "id"): id = row[col]
                airport[col] = row[col]
            airports[id] = airport
    return(airports)

def closest_airport(airports,lat,lon,alt=None):
    closest = None
    closest_dist = 999999
    for id in airports:
        airport = airports[id]
        if (regex.match(r'.*port.*',airport['type'])):
            airport_lat = float(airport['latitude_deg'])
            airport_lon = float(airport['longitude_deg'])
            if (airport['elevation_ft'] != ''):
                airport_alt = float(airport['elevation_ft']);
            else:
                continue
            if (abs(lat - airport_lat ) < 0.1):
                if (abs(lon - airport_lon) < 0.1):
                    if (not alt or (abs(alt - airport_alt)  < 200)):
                        dist = geopy.distance.geodesic((lat,lon),(airport_lat,airport_lon)).mi
                        if (dist < 5 and (not closest or dist < closest_dist)):
                            print(alt)
                            print(airport['elevation_ft'])
                            closest = airport
                            closest_dist = dist
    return(closest)

def load_gpx(text):
    gpx_stream = StringIO(text)
    gpx_data = gpxpy.parse(gpx_stream)
    return(gpx_data)

airports = load_airports("airports.csv")
gpx_file = open(sys.argv[1],'r')
gpx_string = gpx_file.read()
gpx_data = load_gpx(gpx_string)

def find_segments(gpx):
    split_points = []
    for track_no,track in enumerate(gpx.tracks):
    
        for segment_no,segment in enumerate(track.segments):
            start = segment.points[0]

            last_airport = closest_airport(airports,start.latitude,start.longitude,start.elevation)
            if (not last_airport):
                continue
#        end_airport = closest_airport(airports,end.latitude,end.longitude)
#        print(f"{start_airport['ident']} -> {end_airport['ident']}")

            last_point = None
            for point_no,point in enumerate(segment.points):
                if (last_point):
                    if (point.time_difference(last_point) > 600):
                        cur_airport = closest_airport(airports,last_point.latitude,last_point.longitude,last_point.elevation)
                        if (cur_airport['ident'] != last_airport['ident']):
                            split_points.append([track_no,segment_no,point_no-1])
                            last_airport = closest_airport(airports,point.latitude,point.longitude,point.elevation)
#                        airports_visited.append({'airport': last_airport,'time':last_point.time})
#                        airports_visited.append({'airport':next_airport,'time':point.time})

                last_point = point

    # Split in reverse, otherwise the segment numbers won't map correctly
    for split in reversed(split_points):
        gpx.tracks[split[0]].split(split[1],split[2]) 

find_segments(gpx_data)

for track_no,track in enumerate(gpx_data.tracks):
    
    for segment_no,segment in enumerate(track.segments):
        if (len(segment.points)):
            start = segment.points[0]
            end = segment.points[-1]
            start_airport = closest_airport(airports,start.latitude,start.longitude,start.elevation)
            end_airport = closest_airport(airports,end.latitude,end.longitude,end.elevation)
            elevations = segment.get_elevation_extremes()

            if (not start_airport):
                start_airport = {'ident':'NONE'}
            if (not end_airport):
                end_airport = {'ident':'NONE'}

            print(f"{start_airport['ident']} {end_airport['ident']} {start.time}  {datetime.timedelta(seconds=segment.get_duration())} {int(meters_to_nm(segment.length_2d()))}nm {int(meters_to_feet(elevations.maximum))}ft")


#for obj in airports_visited:
#    print(f"{obj['airport']['ident']} {obj['time']}")

#print(f"Looking for airport close to {sys.argv[1]} {sys.argv[2]}")
#airport = closest_airport(airports,float(sys.argv[1]),float(sys.argv[2]))
#if (airport):
#    print(airport)
#!/usr/bin/python3
from pdb import lasti2lineno
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

def filter_airports(airports,gpx): # lat1,lon1,lat2,lon2):
    # FIMXME - handling for wrap around lon/lat
    filtered_airports = []
    track_bounds = []
    
    for track in (gpx.tracks):
        track_bounds.append(track.get_bounds())

    for airport in airports:
        lat = float(airport['latitude_deg'])
        lon = float(airport['longitude_deg'])

        track_airports = []
        for bounds in track_bounds:
            if (lat > bounds.min_latitude and lat < bounds.max_latitude and lon > bounds.min_longitude and lon < bounds.max_longitude):
                track_airports.append(airport)

        # append new airports to filtered list
        [filtered_airports.append(airport) for airport in track_airports if (airport['id'] not in [airport['id'] for airport in filtered_airports])]

            
    return(filtered_airports)
    

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
    return(airports)


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
    return(closest)

def load_gpx(text):
    gpx_stream = StringIO(text)
    gpx_data = gpxpy.parse(gpx_stream)
    return(gpx_data)


# Given the gpx and list of airports, find where aiports were itermediate destinations and break into segments
def split_segments(gpx,airports):
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

######################################################################################

gpx_file = open(sys.argv[1],'r')
gpx_string = gpx_file.read()
gpx_data = load_gpx(gpx_string)

airports = filter_airports(load_airports("airports.csv"),gpx_data)

# Split any segments if there is a landing
print("Finding splits...")
split_segments(gpx_data,airports)

print("Determining aiport data for segements...")
for track_no,track in enumerate(gpx_data.tracks):
    
    for segment_no,segment in enumerate(track.segments):
        if (len(segment.points)):
            start = segment.points[0]
            end = segment.points[-1]
            start_airport = closest_airport(airports,start.latitude,start.longitude,meters_to_feet(start.elevation))
            end_airport = closest_airport(airports,end.latitude,end.longitude,meters_to_feet(end.elevation))
            elevations = segment.get_elevation_extremes()

            if (not start_airport):
                start_airport = {'ident':'NONE'}
            if (not end_airport):
                end_airport = {'ident':'NONE'}

            print(f"{start_airport['ident']} {end_airport['ident']} {start.time}  {datetime.timedelta(seconds=segment.get_duration())} {int(meters_to_nm(segment.length_2d()))}nm {int(meters_to_feet(elevations.maximum))}ft")



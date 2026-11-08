#!/usr/bin/env python3
import sys
import csv
import math

reader = csv.reader(sys.stdin)

for row in reader:
    if len(row) != 15:
        continue

    # Ignorer l'en-tte
    if row[0] == "latitude":
        continue

    # Conserver uniquement les feux de vgtation
    if row[14].strip() != "0":
        continue

    try:
        latitude = float(row[0])
        longitude = float(row[1])

        if not (math.isfinite(latitude) and math.isfinite(longitude)):
            continue

        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue

        # Calcul de la cellule gographique de 0,5 degr
        zone_lat = math.floor(latitude * 2) / 2.0
        zone_lon = math.floor(longitude * 2) / 2.0

        zone = "{:.1f}_{:.1f}".format(zone_lat, zone_lon)

        # mission cl-valeur
        print("{}\t1".format(zone))

    except ValueError:
        continue

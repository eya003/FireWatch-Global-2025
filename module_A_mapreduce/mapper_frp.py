#!/usr/bin/env python3
import sys
import csv
import math

reader = csv.reader(sys.stdin)

for row in reader:
    # Verifier le format CSV NASA
    if len(row) != 15:
        continue

    # Ignorer l'en-tete
    if row[0] == "latitude":
        continue

    # Garder les detections de vegetation presumees
    if row[14].strip() != "0":
        continue

    try:
        latitude = float(row[0])
        longitude = float(row[1])
        frp = float(row[12])

        # Verifier les valeurs numeriques
        if not all(math.isfinite(v) for v in
                   (latitude, longitude, frp)):
            continue

        # Verifier les coordonnees
        if not (-90 <= latitude <= 90 and
                -180 <= longitude <= 180):
            continue

        # Exclure les FRP negatives
        if frp < 0:
            continue

        # Calculer la zone de 0,5 degre
        zone_lat = math.floor(latitude * 2) / 2.0
        zone_lon = math.floor(longitude * 2) / 2.0

        zone = "{:.1f}_{:.1f}".format(
            zone_lat, zone_lon
        )

        # Sortie : zone, FRP, nombre d'observations
        print("{}\t{}\t1".format(zone, frp))

    except ValueError:
        continue

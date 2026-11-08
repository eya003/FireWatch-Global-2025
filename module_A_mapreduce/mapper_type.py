#!/usr/bin/env python3
import sys
import csv

reader = csv.reader(sys.stdin)

for row in reader:
    # Vrifier le nombre de colonnes
    if len(row) != 15:
        continue

    # Ignorer l'en-tte CSV
    if row[14].strip() == "type":
        continue

    # Rcuprer la catgorie de dtection
    fire_type = row[14].strip()

    if fire_type not in ("0", "1", "2", "3"):
        continue

    # mettre une paire cl-valeur
    print("{}\t1".format(fire_type))

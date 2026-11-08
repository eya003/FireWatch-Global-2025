#!/usr/bin/env python3
import sys

current_zone = None
total_frp = 0.0
count = 0

for line in sys.stdin:
    parts = line.strip().split("\t")

    if len(parts) != 3:
        continue

    zone = parts[0]

    try:
        frp_sum = float(parts[1])
        n = int(parts[2])
    except ValueError:
        continue

    if zone != current_zone:
        if current_zone is not None:
            print("{}\t{}\t{}".format(
                current_zone, total_frp, count
            ))

        current_zone = zone
        total_frp = 0.0
        count = 0

    total_frp += frp_sum
    count += n

if current_zone is not None:
    print("{}\t{}\t{}".format(
        current_zone, total_frp, count
    ))

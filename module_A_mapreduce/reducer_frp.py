#!/usr/bin/env python3
import sys

current_zone = None
total_frp = 0.0
total_count = 0

for line in sys.stdin:
    parts = line.strip().split("\t")

    if len(parts) != 3:
        continue

    zone = parts[0]

    try:
        frp_sum = float(parts[1])
        count = int(parts[2])
    except ValueError:
        continue

    if zone != current_zone:
        if current_zone is not None and total_count > 0:
            avg = total_frp / total_count
            print("{}\t{:.4f}".format(current_zone, avg))

        current_zone = zone
        total_frp = 0.0
        total_count = 0

    total_frp += frp_sum
    total_count += count

if current_zone is not None and total_count > 0:
    avg = total_frp / total_count
    print("{}\t{:.4f}".format(current_zone, avg))

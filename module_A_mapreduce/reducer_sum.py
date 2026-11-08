#!/usr/bin/env python3
import sys

current_month = None
total = 0

for line in sys.stdin:
    parts = line.strip().split("\t")

    if len(parts) != 2:
        continue

    month = parts[0]
    count = int(parts[1])

    if month == current_month:
        total += count
    else:
        if current_month is not None:
            print("{}\t{}".format(current_month, total))

        current_month = month
        total = count

if current_month is not None:
    print("{}\t{}".format(current_month, total))

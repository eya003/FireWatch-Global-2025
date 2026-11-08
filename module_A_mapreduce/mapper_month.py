#!/usr/bin/env python3
import sys
import csv

reader = csv.reader(sys.stdin)

for row in reader:
    if len(row) != 15:
        continue

    if row[5] == "acq_date":
        continue

    if row[14].strip() != "0":
        continue

    date = row[5].strip()

    if len(date) != 10 or date[:4] != "2025":
        continue

    year_month = date[:7]
    print("{}\t1".format(year_month))

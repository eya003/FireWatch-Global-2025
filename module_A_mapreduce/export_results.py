#!/usr/bin/env python3

import csv
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(BASE_DIR, "exports")

HDFS_BASE = "/fires/results/mapreduce"
HDFS_EXPORT = HDFS_BASE + "/csv"

JOBS = [
    {
        "source": "month_world_combiner",
        "file": "fires_by_month.csv",
        "columns": ["month", "count"],
        "expected_rows": 12
    },
    {
        "source": "type_world",
        "file": "fires_by_type.csv",
        "columns": ["type", "count"],
        "expected_rows": 4
    },
    {
        "source": "zone_world",
        "file": "fires_by_zone.csv",
        "columns": ["zone", "count"],
        "expected_rows": 37790
    },
    {
        "source": "frp_world",
        "file": "frp_by_zone.csv",
        "columns": ["zone", "avg_frp_mw"],
        "expected_rows": 37790
    }
]


def hdfs_exists(path):
    return subprocess.call(
        ["hdfs", "dfs", "-test", "-e", path]
    ) == 0


def export_job(job):
    source = HDFS_BASE + "/" + job["source"]

    if not hdfs_exists(source + "/_SUCCESS"):
        raise RuntimeError(
            "Job non termine : " + source
        )

    print("Export : " + job["file"])

    output = subprocess.check_output([
        "hdfs", "dfs", "-cat", source + "/part-*"
    ]).decode("utf-8")

    rows = []

    for line in output.splitlines():
        if not line.strip():
            continue

        parts = line.split("\t")

        if len(parts) != 2:
            raise ValueError(
                "Ligne invalide : " + line
            )

        rows.append(parts)

    if len(rows) != job["expected_rows"]:
        raise ValueError(
            "{} : {} lignes au lieu de {}".format(
                job["file"],
                len(rows),
                job["expected_rows"]
            )
        )

    # Valider les valeurs numeriques
    for key, value in rows:
        if job["file"] == "frp_by_zone.csv":
            number = float(value)
            if not (0 <= number < float("inf")):
                raise ValueError("FRP invalide")
        else:
            number = int(value)
            if number < 0:
                raise ValueError("Comptage negatif")

    path = os.path.join(EXPORT_DIR, job["file"])
    temp_path = path + ".tmp"

    with open(temp_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(job["columns"])
        writer.writerows(rows)

    os.replace(temp_path, path)

    print("OK : {} lignes de donnees".format(len(rows)))

    return rows


def main():
    if not os.path.isdir(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)

    print("=== FireWatch : export MapReduce ===")

    results = {}

    for job in JOBS:
        results[job["file"]] = export_job(job)

    # Verification des totaux
    total_month = sum(
        int(row[1])
        for row in results["fires_by_month.csv"]
    )

    total_zone = sum(
        int(row[1])
        for row in results["fires_by_zone.csv"]
    )

    total_type = sum(
        int(row[1])
        for row in results["fires_by_type.csv"]
    )

    if total_month != 17017025:
        raise ValueError("Total mensuel incorrect")

    if total_zone != 17017025:
        raise ValueError("Total geographique incorrect")

    if total_type != 18415101:
        raise ValueError("Total par type incorrect")

    # Verifier la correspondance des zones
    zones_count = {
        row[0] for row in results["fires_by_zone.csv"]
    }

    zones_frp = {
        row[0] for row in results["frp_by_zone.csv"]
    }

    if zones_count != zones_frp:
        raise ValueError(
            "Zones incompatibles entre count et FRP"
        )

    print("Verification des resultats : OK")

    # Publier les CSV dans HDFS
    subprocess.run([
        "hdfs", "dfs", "-mkdir", "-p", HDFS_EXPORT
    ], check=True)

    for job in JOBS:
        local_path = os.path.join(
            EXPORT_DIR, job["file"]
        )

        subprocess.run([
            "hdfs", "dfs", "-put", "-f",
            local_path, HDFS_EXPORT + "/"
        ], check=True)

    print("Exports HDFS termines.")

    subprocess.run([
        "hdfs", "dfs", "-ls", "-h", HDFS_EXPORT
    ], check=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError,
            subprocess.CalledProcessError) as error:
        print("ERREUR : {}".format(error), file=sys.stderr)
        sys.exit(1)
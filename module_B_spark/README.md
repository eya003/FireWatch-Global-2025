# Module B - Apache Spark Batch Processing

## 1. Overview

This module is responsible for batch processing and analysis of NASA FIRMS VIIRS S-NPP active fire data using Apache Spark.

The objective is to analyze fire distribution over time and geographical areas, identify the most affected zones, and produce statistical results for Tunisia and the Maghreb region.

## 2. Technologies

- Apache Spark 2.2.0
- Scala 2.11.8
- Hadoop HDFS
- Spark SQL
- Docker
- NASA FIRMS VIIRS S-NPP 2025 dataset

## 3. Project Structure

```text
module_B_spark/
├── scripts/
│   ├── load.scala
│   ├── cleaning.scala
│   ├── temporal.scala
│   ├── zones.scala
│   ├── world_analysis.scala
│   ├── country_analysis.scala
│   └── final_analysis.scala
├── data/
│   └── countries.geojson
├── results/
│   └── final/
│       ├── monthly_spark.csv
│       ├── top10_days.csv
│       ├── zone_month_stats.csv
│       ├── world_top_zones.csv
│       ├── country_summary.csv
│       └── country_monthly.csv
└── README.md
```

## 4. Processing Pipeline

### 4.1 Data Loading

- Define an explicit schema for the 15 VIIRS S-NPP columns.
- Load CSV data from HDFS using Spark DataFrames.
- Preserve acquisition time as a string to retain leading zeros.

### 4.2 Data Cleaning and Transformation

- Keep only vegetation fire detections (type = 0).
- Exclude other fire types.
- Extract year, month and year-month features.
- Calculate geographical zones using a 0.5-degree grid.

### 4.3 Temporal Analysis

- Calculate monthly fire counts.
- Analyze seasonal fire distribution.
- Identify the 10 days with the highest number of fire detections.

### 4.4 Spatial Analysis

- Calculate fire counts, average FRP and maximum FRP by geographical zone and month.
- Use Spark SQL for additional queries.
- Identify the 20 geographical zones with the highest number of fire detections worldwide.

### 4.5 Maghreb Country Analysis

- Use Natural Earth country boundaries in GeoJSON format.
- Apply point-in-polygon geographical filtering.
- Identify detections inside Tunisia, Algeria, Libya and Morocco.
- Calculate total and monthly fire statistics for each country.

## 5. Scala Scripts

| Script | Description |
|---|---|
| load.scala | Loads the sample dataset with an explicit schema. |
| cleaning.scala | Cleans data and creates analytical features. |
| temporal.scala | Performs temporal analysis. |
| zones.scala | Performs spatial analysis and Spark SQL queries. |
| world_analysis.scala | Calculates the 20 most affected zones worldwide. |
| country_analysis.scala | Extracts and analyzes fires in the four Maghreb countries. |
| final_analysis.scala | Executes final analyses and exports the results. |

## 6. Dataset and HDFS Requirements

The complete global NASA FIRMS dataset is not included in this repository because of its size.

The main analysis expects the global dataset in HDFS at:

`/fires/raw/world/2025/`

The sample dataset used for development is expected at:

`/fires/sample/sample_fires.csv`

The country boundary file is included in `data/countries.geojson`.

The scripts use the project environment paths under `/root/fires_project/`. Before execution, place the scripts in `/root/fires_project/scripts/` and the GeoJSON file in `/root/fires_project/data/`.

## 7. Execution Environment

The project was developed and tested using:

- Docker container: hadoop-master
- Spark 2.2.0
- Scala 2.11.8
- Java 1.8
- Hadoop HDFS

Example command for executing the final analysis inside Docker:

```bash
spark-shell --master local[4] --driver-memory 8g --conf spark.sql.shuffle.partitions=8 -i /root/fires_project/scripts/final_analysis.scala
```

The global dataset must already be available in HDFS, and the GeoJSON file must be present at the expected local path.

## 8. Final Results

| Output | Description |
|---|---|
| monthly_spark.csv | Monthly fire counts in Tunisia. |
| top10_days.csv | Ten days with the highest fire counts in Tunisia. |
| zone_month_stats.csv | Fire statistics by geographical zone and month in Tunisia. |
| world_top_zones.csv | Twenty geographical zones with the highest fire counts worldwide. |
| country_summary.csv | Total fire detections in Tunisia, Algeria, Libya and Morocco. |
| country_monthly.csv | Monthly fire counts for the four Maghreb countries. |

The final results are stored in `results/final/`.

## 9. Main Findings

The analysis of the 2025 global dataset identified 16,372,388 vegetation fire detections (type = 0).

The Maghreb country analysis identified 21,519 detections:

- Algeria: 10,874
- Libya: 7,766
- Tunisia: 1,495
- Morocco: 1,384

For Tunisia, September recorded the highest monthly number of detections, with 430 fires, followed by August with 273 and July with 204.

## 10. Module Responsibility

This module represents Member B's contribution to the FireWatch Global 2025 project. It focuses on distributed batch processing, temporal and spatial analysis, Spark SQL queries and CSV result generation.
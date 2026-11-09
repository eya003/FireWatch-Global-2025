# FireWatch — Global Fire Intelligence Dashboard

The dashboard contains **Overview**, **Fire Explorer**, **Trends & Insights**, and a preparatory **Live Monitoring** page. Historical pages read existing MapReduce and Spark CSV exports. Live Monitoring remains disconnected until Module C provides a real alert reader; the dashboard does not run Hadoop, Spark, Kafka, or Docker.

## Requirements

- Python 3.10 or newer
- The four CSV exports in `module_A_mapreduce/exports/`
- Spark exports `country_summary.csv`, `country_monthly.csv`, `monthly_spark.csv`, and `top10_days.csv` in `module_B_spark/results/final/`
- Spark `world_top_countries.csv` (`rank,country,fire_count`) for the Overview Top 10 countries chart.

## Create an environment and install dependencies

From the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r dashboard\requirements.txt
```

On macOS or Linux, activate the environment with `source .venv/bin/activate`.

## Run the dashboard

From the repository root:

```powershell
python -m streamlit run dashboard/app.py
```

The application resolves the Module A export directory relative to the project files. It validates required columns, numeric values, month coverage, category totals, zone totals, unique geographic keys, and the zone-to-FRP join. The map derives representative centers from the lower-left coordinates encoded in each 0.5° cell identifier; centers do not represent exact detections. Its default view limits rendering to the top 500 cells, with an option to display all cells.

## Run the lightweight data tests

Install the test dependency if it is not already present:

```powershell
python -m pip install -r dashboard\requirements-dev.txt
```

Then run:

```powershell
python -m pytest dashboard\tests -q
```

Tests verify the checked-in geographic and Spark trend exports, monthly reconciliation, country ranking and filters, daily date ranking, coordinate conversion (including negative coordinates), source-data immutability, invalid input handling, and Streamlit rendering and navigation for all four pages. They do not require Docker or cluster services.

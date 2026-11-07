import org.apache.spark.sql.functions._

// Load the cleaned dataset
val firesDF = spark.read.option("header", "true").option("inferSchema", "true").csv("hdfs:///fires/processed/")

println("========== DATASET INFORMATION ==========")
println("Total vegetation fires: " + firesDF.count())

// 1. Spatial analysis using DataFrames
println("========== SPATIAL ANALYSIS ==========")

val zoneMonthStats = firesDF.groupBy("zone", "year_month").agg(count("*").alias("count"), avg("frp").alias("avg_frp"), max("frp").alias("max_frp")).orderBy(desc("count"))

zoneMonthStats.show(20, false)

// 2. Create a temporary SQL view
firesDF.createOrReplaceTempView("fires")

println("========== SQL QUERY 1: TOP 10 FIRE ZONES ==========")

val topZones = spark.sql("SELECT zone, COUNT(*) AS count FROM fires GROUP BY zone ORDER BY count DESC LIMIT 10")
topZones.show(false)

println("========== SQL QUERY 2: MONTHLY FIRE STATISTICS BY ZONE ==========")

val monthlyZones = spark.sql("SELECT zone, year_month, COUNT(*) AS count, ROUND(AVG(frp), 2) AS avg_frp, MAX(frp) AS max_frp FROM fires GROUP BY zone, year_month ORDER BY count DESC")
monthlyZones.show(20, false)

// 3. Save spatial analysis results
println("========== SAVING SPATIAL RESULTS ==========")

zoneMonthStats.coalesce(1).write.mode("overwrite").option("header", "true").csv("hdfs:///fires/results/spark/zone_month_stats")

println("Spatial analysis completed successfully.")

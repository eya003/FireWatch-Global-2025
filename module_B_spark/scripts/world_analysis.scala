import org.apache.spark.sql.types._
import org.apache.spark.sql.functions._
import org.apache.spark.storage.StorageLevel

val fireSchema = StructType(Seq(
  StructField("latitude", DoubleType, true),
  StructField("longitude", DoubleType, true),
  StructField("bright_ti4", DoubleType, true),
  StructField("scan", DoubleType, true),
  StructField("track", DoubleType, true),
  StructField("acq_date", StringType, true),
  StructField("acq_time", StringType, true),
  StructField("satellite", StringType, true),
  StructField("instrument", StringType, true),
  StructField("confidence", StringType, true),
  StructField("version", StringType, true),
  StructField("bright_ti5", DoubleType, true),
  StructField("frp", DoubleType, true),
  StructField("daynight", StringType, true),
  StructField("type", IntegerType, true)
))

println("========== LOADING VEGETATION FIRES ==========")

val worldDF = spark.read.option("header", "true").schema(fireSchema).csv("hdfs:///fires/raw/world/2025/*.csv")

val vegetationDF = worldDF.filter(col("type") === 0).select("latitude", "longitude", "frp").persist(StorageLevel.MEMORY_AND_DISK)

println("Total vegetation fires: " + vegetationDF.count())

println("========== CREATING GEOGRAPHICAL ZONES ==========")

val zonedDF = vegetationDF.withColumn("zone", concat(format_string("%.1f", floor(col("latitude") * 2) / 2), lit("_"), format_string("%.1f", floor(col("longitude") * 2) / 2)))

println("========== TOP 20 WORLDWIDE ZONES ==========")

val top20Zones = zonedDF.groupBy("zone").count().orderBy(desc("count")).limit(20)

val startTime = System.nanoTime()

top20Zones.show(20, false)

val endTime = System.nanoTime()
val executionTime = (endTime - startTime) / 1000000000.0

println("Top 20 analysis execution time: " + executionTime + " seconds")

println("========== SAVING WORLD RESULTS ==========")

top20Zones.coalesce(1).write.mode("overwrite").option("header", "true").csv("hdfs:///fires/results/spark/world_top_zones")

vegetationDF.unpersist()

println("World geographical analysis completed successfully.")

import org.apache.spark.sql.types._
import org.apache.spark.sql.functions._

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

val firesDF = spark.read.option("header", "true").schema(fireSchema).csv("hdfs:///fires/sample/sample_fires.csv")

// Keep only vegetation fires
val cleanedDF = firesDF.filter(col("type") === 0)

// Extract temporal information and create geographical zones
val enrichedDF = cleanedDF.withColumn("year", substring(col("acq_date"), 1, 4).cast("int")).withColumn("month", substring(col("acq_date"), 6, 2).cast("int")).withColumn("year_month", substring(col("acq_date"), 1, 7)).withColumn("zone", concat((floor(col("latitude") * 2) / 2).cast("string"), lit("_"), (floor(col("longitude") * 2) / 2).cast("string")))

println("========== CLEANED DATASET ==========")
enrichedDF.printSchema()

println("========== FIRST 10 RECORDS ==========")
enrichedDF.show(10, false)

println("========== CLEANING STATISTICS ==========")
println("Original records: " + firesDF.count())
println("Vegetation fire records: " + enrichedDF.count())

println("========== MONTHLY DISTRIBUTION ==========")
enrichedDF.groupBy("year_month").count().orderBy("year_month").show()

println("========== TOP GEOGRAPHICAL ZONES ==========")
enrichedDF.groupBy("zone").count().orderBy(desc("count")).show(10, false)

// Save the enriched dataset in HDFS
enrichedDF.write.mode("overwrite").option("header", "true").csv("hdfs:///fires/processed/")

println("Cleaned dataset successfully saved in HDFS.")

import org.apache.spark.sql.types._

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

val firesDF = spark.read.option("header", "true").option("mode", "PERMISSIVE").schema(fireSchema).csv("hdfs:///fires/sample/sample_fires.csv")

println("========== DATASET SCHEMA ==========")
firesDF.printSchema()

println("========== FIRST 10 RECORDS ==========")
firesDF.show(10, false)

println("========== DATASET STATISTICS ==========")
println("Total records: " + firesDF.count())

println("========== FIRE TYPES ==========")
firesDF.groupBy("type").count().show()

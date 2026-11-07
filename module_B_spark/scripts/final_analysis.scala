import org.apache.spark.sql.types._
import org.apache.spark.sql.functions._
import org.apache.spark.storage.StorageLevel
import scala.util.parsing.json.JSON
import java.nio.file.{Files, Paths}
import java.nio.charset.StandardCharsets

object FinalGeoUtils extends Serializable {
  def toPoint(v: Any): (Double, Double) = {
    val c = v.asInstanceOf[List[Any]]
    (c(0).asInstanceOf[Double], c(1).asInstanceOf[Double])
  }

  def toRing(v: Any): Seq[(Double, Double)] =
    v.asInstanceOf[List[Any]].map(toPoint)

  def toPolygon(v: Any): Seq[Seq[(Double, Double)]] =
    v.asInstanceOf[List[Any]].map(toRing)

  def toPolygons(g: Map[String, Any]): Seq[Seq[Seq[(Double, Double)]]] = {
    g("type").toString match {
      case "Polygon" => Seq(toPolygon(g("coordinates")))
      case "MultiPolygon" =>
        g("coordinates").asInstanceOf[List[Any]].map(toPolygon)
      case other =>
        throw new IllegalArgumentException("Unsupported geometry: " + other)
    }
  }

  def pointInRing(lon: Double, lat: Double, ring: Seq[(Double, Double)]): Boolean = {
    var inside = false
    var j = ring.length - 1
    var i = 0

    while (i < ring.length) {
      val xi = ring(i)._1
      val yi = ring(i)._2
      val xj = ring(j)._1
      val yj = ring(j)._2

      if ((yi > lat) != (yj > lat) &&
          lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) {
        inside = !inside
      }

      j = i
      i += 1
    }
    inside
  }

  def pointInPolygon(lon: Double, lat: Double, polygon: Seq[Seq[(Double, Double)]]): Boolean = {
    pointInRing(lon, lat, polygon.head) &&
      !polygon.drop(1).exists(h => pointInRing(lon, lat, h))
  }

  def pointInCountry(lon: Double, lat: Double, polygons: Seq[Seq[Seq[(Double, Double)]]]): Boolean =
    polygons.exists(p => pointInPolygon(lon, lat, p))

  def findCountry(
    lon: Double,
    lat: Double,
    countries: Map[String, Seq[Seq[Seq[(Double, Double)]]]]
  ): String = {
    countries.find {
      case (_, polygons) => pointInCountry(lon, lat, polygons)
    }.map(_._1).getOrElse(null)
  }
}

println("========== LOADING COUNTRY BOUNDARIES ==========")

val geoJsonBytes = Files.readAllBytes(Paths.get("/root/fires_project/data/countries.geojson"))
val geoJsonText = new String(geoJsonBytes, StandardCharsets.UTF_8)
val root = JSON.parseFull(geoJsonText).get.asInstanceOf[Map[String, Any]]
val features = root("features").asInstanceOf[List[Any]]
val targetCountries = Set("Tunisia", "Algeria", "Libya", "Morocco")

val countryPolygons = features.flatMap { feature =>
  val f = feature.asInstanceOf[Map[String, Any]]
  val properties = f("properties").asInstanceOf[Map[String, Any]]
  val name = properties("name").toString

  if (targetCountries.contains(name)) {
    Some(name -> FinalGeoUtils.toPolygons(f("geometry").asInstanceOf[Map[String, Any]]))
  } else {
    None
  }
}.toMap

println("Countries loaded: " + countryPolygons.keys.mkString(", "))
val countryBroadcast = sc.broadcast(countryPolygons)

println("========== LOADING GLOBAL DATASET ==========")

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

val worldDF = spark.read .option("header", "true") .option("mode", "PERMISSIVE") .schema(fireSchema) .csv("hdfs:///fires/raw/world/2025/*.csv")

println("Global records loaded: " + worldDF.count())

println("========== GLOBAL TOP 20 ZONES ==========")

val globalVegetation = worldDF.filter(col("type") === 0)

val globalZones = globalVegetation .withColumn(
    "zone",
    concat(
      format_string("%.1f", floor(col("latitude") * 2) / 2),
      lit("_"),
      format_string("%.1f", floor(col("longitude") * 2) / 2)
    )
  ) .groupBy("zone") .count() .orderBy(desc("count")) .limit(20)

globalZones.show(20, false)

println("========== IDENTIFYING MAGHREB COUNTRIES ==========")

val maghrebDF = globalVegetation .filter(
    col("latitude").between(14.0, 38.0) &&
    col("longitude").between(-18.0, 26.0)
  ) .select("latitude", "longitude", "acq_date", "frp")

val findCountryUDF = udf(
  (longitude: Double, latitude: Double) =>
    FinalGeoUtils.findCountry(longitude, latitude, countryBroadcast.value)
)

val countryFires = maghrebDF .withColumn("country", findCountryUDF(col("longitude"), col("latitude"))) .filter(col("country").isNotNull) .withColumn("year_month", substring(col("acq_date"), 1, 7)) .persist(StorageLevel.MEMORY_AND_DISK)

println("Total fires inside the four country boundaries: " + countryFires.count())

println("========== COUNTRY SUMMARY ==========")

val countrySummary = countryFires .groupBy("country") .count() .orderBy(desc("count"))

countrySummary.show(false)

println("========== COUNTRY MONTHLY STATISTICS ==========")

val countryMonthly = countryFires .groupBy("country", "year_month") .count() .orderBy("country", "year_month")

countryMonthly.show(60, false)

println("========== TUNISIA MONTHLY STATISTICS ==========")

val tunisiaFires = countryFires.filter(col("country") === "Tunisia")

val tunisiaMonthly = tunisiaFires .groupBy("year_month") .count() .orderBy("year_month")

tunisiaMonthly.show(20, false)

println("========== TUNISIA TOP 10 DAYS ==========")

val top10Days = tunisiaFires .groupBy(col("acq_date").alias("date")) .agg(
    count("*").alias("count"),
    max("frp").alias("max_frp")
  ) .orderBy(desc("count"), desc("max_frp")) .limit(10)

top10Days.show(10, false)

println("========== TUNISIA ZONE MONTH STATISTICS ==========")

val tunisiaZoneMonthStats = tunisiaFires .withColumn(
    "zone",
    concat(
      format_string("%.1f", floor(col("latitude") * 2) / 2),
      lit("_"),
      format_string("%.1f", floor(col("longitude") * 2) / 2)
    )
  ) .groupBy("zone", "year_month") .agg(
    count("*").alias("count"),
    round(avg("frp"), 2).alias("avg_frp"),
    max("frp").alias("max_frp")
  ) .orderBy(desc("count"))

tunisiaZoneMonthStats.show(20, false)

println("========== SAVING FINAL RESULTS ==========")

globalZones.coalesce(1) .write.mode("overwrite").option("header", "true") .csv("hdfs:///fires/results/spark/final/world_top_zones")

countrySummary.coalesce(1) .write.mode("overwrite").option("header", "true") .csv("hdfs:///fires/results/spark/final/country_summary")

countryMonthly.coalesce(1) .write.mode("overwrite").option("header", "true") .csv("hdfs:///fires/results/spark/final/country_monthly")

tunisiaMonthly.coalesce(1) .write.mode("overwrite").option("header", "true") .csv("hdfs:///fires/results/spark/final/monthly_spark")

top10Days.coalesce(1) .write.mode("overwrite").option("header", "true") .csv("hdfs:///fires/results/spark/final/top10_days")

tunisiaZoneMonthStats.coalesce(1) .write.mode("overwrite").option("header", "true") .csv("hdfs:///fires/results/spark/final/zone_month_stats")

println("All final analyses saved successfully.")

countryFires.unpersist()

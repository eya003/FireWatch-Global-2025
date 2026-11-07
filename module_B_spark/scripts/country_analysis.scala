import org.apache.spark.sql.types._
import org.apache.spark.sql.functions._
import scala.util.parsing.json.JSON
import java.nio.file.{Files, Paths}
import java.nio.charset.StandardCharsets

object GeoUtils extends Serializable {
  def toPoint(v: Any): (Double, Double) = {
    val c = v.asInstanceOf[List[Any]]
    (c(0).asInstanceOf[Double], c(1).asInstanceOf[Double])
  }

  def toRing(v: Any): Seq[(Double, Double)] = v.asInstanceOf[List[Any]].map(toPoint)

  def toPolygon(v: Any): Seq[Seq[(Double, Double)]] = v.asInstanceOf[List[Any]].map(toRing)

  def toPolygons(g: Map[String, Any]): Seq[Seq[Seq[(Double, Double)]]] = {
    g("type").toString match {
      case "Polygon" => Seq(toPolygon(g("coordinates")))
      case "MultiPolygon" => g("coordinates").asInstanceOf[List[Any]].map(toPolygon)
      case other => throw new IllegalArgumentException("Unsupported geometry: " + other)
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
      if ((yi > lat) != (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) inside = !inside
      j = i
      i += 1
    }
    inside
  }

  def pointInPolygon(lon: Double, lat: Double, polygon: Seq[Seq[(Double, Double)]]): Boolean = {
    pointInRing(lon, lat, polygon.head) && !polygon.drop(1).exists(h => pointInRing(lon, lat, h))
  }

  def pointInCountry(lon: Double, lat: Double, polygons: Seq[Seq[Seq[(Double, Double)]]]): Boolean = {
    polygons.exists(p => pointInPolygon(lon, lat, p))
  }

  def findCountry(lon: Double, lat: Double, countries: Map[String, Seq[Seq[Seq[(Double, Double)]]]]): String = {
    countries.find { case (_, polygons) => pointInCountry(lon, lat, polygons) }.map(_._1).getOrElse(null)
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
  val p = f("properties").asInstanceOf[Map[String, Any]]
  val name = p("name").toString
  if (targetCountries.contains(name)) Some(name -> GeoUtils.toPolygons(f("geometry").asInstanceOf[Map[String, Any]])) else None
}.toMap

println("Countries loaded: " + countryPolygons.keys.mkString(", "))
val countryBroadcast = sc.broadcast(countryPolygons)

println("========== LOADING WORLD DATASET ==========")

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

val worldDF = spark.read.option("header", "true").option("mode", "PERMISSIVE").schema(fireSchema).csv("hdfs:///fires/raw/world/2025/*.csv")

println("World dataset loaded.")

println("========== FILTERING MAGHREB AREA ==========")

val maghrebDF = worldDF.filter(col("type") === 0).filter(col("latitude").between(14.0, 38.0) && col("longitude").between(-18.0, 26.0)).select("latitude", "longitude", "acq_date", "frp")

println("Records in broad geographic area: " + maghrebDF.count())

println("========== IDENTIFYING COUNTRIES ==========")

val findCountryUDF = udf((longitude: Double, latitude: Double) => GeoUtils.findCountry(longitude, latitude, countryBroadcast.value))

val countryFires = maghrebDF.withColumn("country", findCountryUDF(col("longitude"), col("latitude"))).filter(col("country").isNotNull).withColumn("year_month", substring(col("acq_date"), 1, 7)).cache()

val totalCountryFires = countryFires.count()
println("Total fires inside the four country boundaries: " + totalCountryFires)

println("========== FIRE COUNT BY COUNTRY ==========")

val countrySummary = countryFires.groupBy("country").count().orderBy(desc("count"))
countrySummary.show(false)

println("========== MONTHLY FIRE STATISTICS ==========")

val countryMonthly = countryFires.groupBy("country", "year_month").count().orderBy("country", "year_month")
countryMonthly.show(60, false)

println("========== SAVING COUNTRY RESULTS ==========")

countrySummary.coalesce(1).write.mode("overwrite").option("header", "true").csv("hdfs:///fires/results/spark/country_summary")
countryMonthly.coalesce(1).write.mode("overwrite").option("header", "true").csv("hdfs:///fires/results/spark/country_monthly")

println("Country analysis completed successfully.")

countryFires.unpersist()

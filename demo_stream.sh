#!/bin/bash
# demo_stream.sh - Membre C
# Lance toute la chaine temps reel :
#   producteur -> Kafka -> Spark Streaming -> HDFS -> HBase -> requetes de demo
# Usage : ./demo_stream.sh [fichier_csv] [lignes_par_seconde]

cd "$(dirname "$0")"
DATA=${1:-../data/viirs-snpp_2025_Tunisia.csv}
RATE=${2:-20}
TOPIC=fires-tunisia
PKG=org.apache.spark:spark-streaming-kafka-0-10_2.11:2.2.0
mkdir -p logs

etape() { echo; echo "========== $1 =========="; }

etape "1. Verification de Kafka et HBase"
if ! jps | grep -q " Kafka$"; then
  echo "Demarrage de ZooKeeper + Kafka..."
  nohup ~/start-kafka-zookeeper.sh > logs/kafka.log 2>&1 &
  sleep 15
fi
if ! jps | grep -q "HMaster"; then
  echo "Demarrage de HBase..."
  start-hbase.sh > logs/hbase.log 2>&1
  sleep 30
fi
jps | grep -E "Kafka|QuorumPeerMain|HMaster|HRegionServer"

etape "2. Topic Kafka"
kafka-topics.sh --create --if-not-exists --zookeeper localhost:2181 \
  --replication-factor 1 --partitions 1 --topic $TOPIC 2>/dev/null
kafka-topics.sh --list --zookeeper localhost:2181 2>/dev/null | grep $TOPIC

etape "3. Nettoyage des anciennes alertes dans HDFS"
hdfs dfs -rm -r -f /fires/stream/alerts > /dev/null 2>&1
echo "ok"

etape "4. Lancement de Spark Streaming (arriere-plan)"
nohup spark-shell --master local[2] --packages $PKG -i streaming.scala \
  < /dev/null > logs/streaming.log 2>&1 &
echo "Attente du demarrage de Spark (60 s)... journal : logs/streaming.log"
sleep 60

etape "5. Envoi des detections dans Kafka ($RATE lignes/s)"
python3 producer.py --replay "$DATA" --rate $RATE \
  | kafka-console-producer.sh --broker-list localhost:9092 --topic $TOPIC 2>/dev/null
echo "Attente des derniers micro-batchs (30 s)..."
sleep 30
grep "==>" logs/streaming.log | tail -5

etape "6. Arret de Spark Streaming"
kill $(jps | grep SparkSubmit | cut -d' ' -f1) 2>/dev/null
echo "ok"

etape "7. Alertes produites"
hdfs dfs -cat /fires/stream/alerts/*/part-* > alerts.csv 2>/dev/null
echo "$(wc -l < alerts.csv) alertes ecrites dans HDFS"

etape "8. Chargement dans HBase (table fire_alerts)"
python3 csv_to_puts.py --csv alerts.csv \
  --names zone,acq_date,acq_time,latitude,longitude,frp,confidence \
  --table fire_alerts --key zone --family last \
  --columns acq_date,acq_time,latitude,longitude,frp,confidence \
  --ts acq_date,acq_time > puts_alerts.hbase
hbase shell puts_alerts.hbase > logs/hbase_puts.log 2>&1
echo "ok (detail : logs/hbase_puts.log)"

etape "9. Consultation HBase"
hbase shell queries_demo.hbase 2>/dev/null

etape "FIN"
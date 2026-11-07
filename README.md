# Module C : temps réel (Kafka, Spark Streaming) et HBase

> Projet Big Data (II3) : **surveillance des feux de forêt à partir des données satellites NASA FIRMS**
> Responsable du module : **Hassine Kooli** (membre C)

Ce module constitue la **couche temps réel** et la **couche de stockage NoSQL** de l'architecture Lambda du projet :

- il **collecte** les nouvelles détections de feux (API NASA FIRMS ou rejeu d'un fichier) et les envoie dans **Kafka** ;
- il les **analyse en continu** avec **Spark Streaming** pour lever des **alertes** (feu intense, fiable, dans le Nord de la Tunisie) ;
- il **stocke** dans **HBase** les alertes ainsi que les résultats batch des modules A (MapReduce) et B (Spark), pour une consultation rapide par clé.

---

## Sommaire

1. [Place du module dans l'architecture](#1-place-du-module-dans-larchitecture)
2. [Contenu du dossier](#2-contenu-du-dossier)
3. [Prérequis](#3-prérequis)
4. [Contrat commun utilisé](#4-contrat-commun-utilisé)
5. [Installation](#5-installation)
6. [Utilisation pas à pas](#6-utilisation-pas-à-pas)
7. [Lancement automatique : `demo_stream.sh`](#7-lancement-automatique--demo_streamsh)
8. [Résultats attendus (tests de validation)](#8-résultats-attendus-tests-de-validation)
9. [Intégration avec les modules A et B](#9-intégration-avec-les-modules-a-et-b)
10. [Choix techniques](#10-choix-techniques)
11. [Dépannage](#11-dépannage)
12. [Limites et améliorations possibles](#12-limites-et-améliorations-possibles)

---

## 1. Place du module dans l'architecture

```
                       COUCHE BATCH (modules A et B)
  NASA FIRMS (CSV) ──> HDFS ──> MapReduce (A) ──┐
                              └─> Spark (B) ────┤  CSV de résultats
                                                ▼
                                         csv_to_puts.py ──> HBase
                                                ▲          (fire_monthly,
                       COUCHE TEMPS RÉEL (module C)         fire_zone,
  API FIRMS / rejeu ──> producer.py ──> Kafka ──> Spark ──> HDFS  fire_alerts)
                                      (topic    Streaming  /fires/stream/alerts
                                  fires-tunisia)
```

---

## 2. Contenu du dossier

| Fichier | Rôle |
|---|---|
| `producer.py` | Producteur : envoie les détections ligne par ligne sur la sortie standard (redirigée vers Kafka). Deux modes : `--replay` (rejeu d'un CSV) et `--api` (API NASA FIRMS, avec filtre des doublons). |
| `streaming.scala` | Spark Streaming : lit le topic `fires-tunisia` par micro-batchs de 10 s, applique la règle d'alerte, calcule la zone et écrit les alertes dans HDFS. |
| `create_tables.hbase` | Crée les 3 tables HBase du contrat. |
| `csv_to_puts.py` | Convertit n'importe quel CSV du contrat en fichier de commandes `put` exécutable par `hbase shell`. |
| `queries_demo.hbase` | 10 requêtes de démonstration : `get`, versions, `scan`, préfixe de clé, filtres, `TIMERANGE`. |
| `demo_stream.sh` | Lance toute la chaîne temps réel en une seule commande, de la vérification des services jusqu'aux requêtes HBase. |
| `logs/` | *(généré)* Journaux de Kafka, Spark Streaming et HBase. |

---

## 3. Prérequis

Le module s'exécute dans le **conteneur `hadoop-master`** du cluster Docker du TP1 (image `liliasfaxi/spark-hadoop:hv-2.7.2`).

| Composant | Version | Remarque |
|---|---|---|
| Hadoop / HDFS | 2.7.2 | `./start-hadoop.sh` |
| Kafka | 1.0.2 (Scala 2.11) | `~/start-kafka-zookeeper.sh` |
| Spark | 2.2.0 (Scala 2.11) | `spark-shell` |
| HBase | 1.4.9 | `start-hbase.sh` |
| Python | **3.5.2** | ⚠️ pas de f-strings : utiliser `"...".format()` |
| Connecteur Spark ↔ Kafka | `spark-streaming-kafka-0-10_2.11:2.2.0` | téléchargé automatiquement au **premier** lancement (Internet nécessaire une seule fois, puis conservé dans `~/.ivy2`) |
| Clé API NASA FIRMS | — | facultative (mode `--api` uniquement), à demander sur https://firms.modaps.eosdis.nasa.gov/api/map_key/ |

---

## 4. Contrat commun utilisé

| Élément | Valeur |
|---|---|
| Topic Kafka | `fires-tunisia` (1 partition, réplication 1) |
| Message Kafka | 1 ligne CSV brute VIIRS, sans en-tête : 15 colonnes en rejeu d'archive, 14 depuis l'API (pas de colonne `type`) |
| Règle d'alerte | `latitude >= 35.5` **et** `frp >= 20` **et** `confidence != 'l'` |
| Zone | grille de 0,5° : `floor(lat*2)/2 + "_" + floor(lon*2)/2`, par exemple `36.5_9.0` |
| Sortie du streaming (HDFS) | `/fires/stream/alerts/batch-<timestamp>/part-*` |
| Format d'une alerte | `zone,acq_date,acq_time,latitude,longitude,frp,confidence` |

**Tables HBase**

| Table | Row key | Familles | Contenu |
|---|---|---|---|
| `fire_monthly` | `AAAA-MM` | `mr`, `spark` (colonne `count`) | comptages mensuels de MapReduce (A) et Spark (B) côte à côte |
| `fire_zone` | `zone#AAAA-MM` | `stats` (`count`, `avg_frp`, `max_frp`) | statistiques par zone et par mois (B) |
| `fire_alerts` | `zone` | `last`, **10 versions** | les 10 dernières alertes de chaque zone (C) |

---

## 5. Installation

Les fichiers sont écrits sur Windows (VS Code) puis copiés dans le conteneur.

1. Dans VS Code, régler les fins de ligne sur **LF** (indispensable pour les scripts `.sh`).
2. Copier le projet dans le conteneur, depuis **PowerShell** :
   ```powershell
   docker cp "C:\chemin\vers\projet" hadoop-master:/root/
   ```
3. Dans le conteneur :
   ```bash
   cd ~/projet/module_C_streaming_hbase
   chmod +x demo_stream.sh
   ```

---

## 6. Utilisation pas à pas

Toutes les commandes s'exécutent dans le conteneur (`docker exec -it hadoop-master bash`).

### 6.1 Démarrer les services

```bash
./start-hadoop.sh
hdfs dfsadmin -safemode get          # attendre "Safe mode is OFF"
~/start-kafka-zookeeper.sh
start-hbase.sh
jps                                  # NameNode, Kafka, QuorumPeerMain, HMaster, HRegionServer
```

> Kafka et HBase partagent **le même ZooKeeper** (port 2181) : il est normal que `HQuorumPeer` n'apparaisse pas dans `jps`.

### 6.2 Créer le topic Kafka (une seule fois)

```bash
kafka-topics.sh --create --if-not-exists --zookeeper localhost:2181 \
  --replication-factor 1 --partitions 1 --topic fires-tunisia
kafka-topics.sh --list --zookeeper localhost:2181
```

### 6.3 Créer les tables HBase (une seule fois)

```bash
hbase shell create_tables.hbase
```

### 6.4 Lancer Spark Streaming (terminal 1)

```bash
spark-shell --master local[2] \
  --packages org.apache.spark:spark-streaming-kafka-0-10_2.11:2.2.0 \
  -i streaming.scala
```

Attendre la fin du démarrage avant de lancer le producteur (`auto.offset.reset = latest` : seuls les nouveaux messages sont lus).

### 6.5 Lancer le producteur (terminal 2)

**Mode rejeu** (tests et démonstration, sans Internet) :
```bash
python3 producer.py --replay ../data/viirs-snpp_2025_Tunisia.csv --rate 20 \
  | kafka-console-producer.sh --broker-list localhost:9092 --topic fires-tunisia
```

**Mode API** (données NASA en quasi temps réel) :
```bash
export FIRMS_KEY=VOTRE_MAP_KEY       # ne jamais écrire la clé dans le code ni la publier
python3 producer.py --api $FIRMS_KEY --interval 600 --days 1 \
  | kafka-console-producer.sh --broker-list localhost:9092 --topic fires-tunisia
```

| Option | Signification |
|---|---|
| `--replay FICHIER` | rejoue un CSV FIRMS ligne par ligne |
| `--rate N` | lignes envoyées par seconde (rejeu) |
| `--api MAP_KEY` | interroge l'API FIRMS (rectangle autour de la Tunisie) |
| `--interval S` | secondes entre deux appels à l'API |
| `--days N` | jours demandés à l'API (**1 à 5 maximum**) |

### 6.6 Charger les alertes dans HBase

```bash
hdfs dfs -cat /fires/stream/alerts/*/part-* > alerts.csv

python3 csv_to_puts.py --csv alerts.csv \
  --names zone,acq_date,acq_time,latitude,longitude,frp,confidence \
  --table fire_alerts --key zone --family last \
  --columns acq_date,acq_time,latitude,longitude,frp,confidence \
  --ts acq_date,acq_time > puts_alerts.hbase

hbase shell puts_alerts.hbase
```

### 6.7 Consulter HBase

```bash
hbase shell queries_demo.hbase
```

---

## 7. Lancement automatique : `demo_stream.sh`

Le script enchaîne toutes les étapes de la section 6 : vérification ou démarrage de Kafka et HBase, topic, nettoyage HDFS, Spark Streaming en arrière-plan, rejeu, chargement HBase et requêtes de démonstration.

```bash
./demo_stream.sh                                            # fichier 2025, 20 lignes/s
./demo_stream.sh ../data/sample_fires.csv 10                # autre fichier, autre débit
```

Durée : environ 4 minutes. Les journaux sont écrits dans `logs/`.
Pour voir les alertes apparaître en direct, dans un autre terminal :
```bash
tail -f logs/streaming.log | grep --line-buffered -A 3 "==>"
```

---

## 8. Résultats attendus (tests de validation)

Avec le fichier `viirs-snpp_2025_Tunisia.csv` (2 457 détections) :

| Test | Commande | Résultat attendu |
|---|---|---|
| Rejeu complet | sortie de `producer.py` | `Rejeu termine : 2457 lignes envoyees` |
| Alertes produites | `hdfs dfs -cat /fires/stream/alerts/*/part-* \| wc -l` | **70** |
| Zones en alerte | `count 'fire_alerts'` | **10** |
| Zone la plus touchée | `get 'fire_alerts', '36.5_9.0', {COLUMN=>'last:acq_date', VERSIONS=>10}` | **8 versions**, du 2025-10-16 au 2025-08-11 |
| Alertes de septembre 2025 | requête 9 (`TIMERANGE`) | **5 zones, 8 alertes** |
| Feu le plus intense | requête 5 | zone `36.0_9.5`, frp = **432.32** MW (2025-10-11) |

Les 70 alertes sont toutes de `type = 0` (feux de végétation), bien que la règle n'utilise pas cette colonne : elle exclut naturellement les torchères et les sites industriels.

---

## 9. Intégration avec les modules A et B

Les CSV livrés par A et B doivent respecter le contrat : **en-tête, séparateur virgule**, `year_month` sur deux chiffres (`2025-09`), zone au format `36.5_9.0`.

```bash
# Module A (MapReduce) -> fire_monthly, famille mr
python3 csv_to_puts.py --csv fires_by_month.csv --table fire_monthly \
  --key year_month --family mr --columns count > puts_monthly_mr.hbase

# Module B (Spark) -> fire_monthly, famille spark
python3 csv_to_puts.py --csv monthly_spark.csv --table fire_monthly \
  --key year_month --family spark --columns count > puts_monthly_spark.hbase

# Module B (Spark) -> fire_zone
python3 csv_to_puts.py --csv zone_month_stats.csv --table fire_zone \
  --key zone,year_month --family stats > puts_zone.hbase

hbase shell puts_monthly_mr.hbase
hbase shell puts_monthly_spark.hbase
hbase shell puts_zone.hbase
```

Activer ensuite les requêtes 11 et 12 de `queries_demo.hbase`. Vérification de cohérence :
```
get 'fire_monthly', '2025-09'      # mr:count = spark:count = 430
```

---

## 10. Choix techniques

| Choix | Justification |
|---|---|
| **Kafka** entre la collecte et le traitement | découple le producteur et Spark, stocke les messages (aucune perte si Spark est arrêté ou en retard), absorbe les pics, permet plusieurs consommateurs |
| Micro-batchs de **10 s**, `--master local[2]` | le temps de traitement d'un micro-batch doit rester inférieur à l'intervalle. Sur YARN, les délais de planification créaient un retard cumulé (plus de 2 min observées) |
| `cache()` + un seul `count()` par micro-batch | évite de relire Kafka pour chaque action |
| Règle d'alerte **dans Spark**, pas dans HBase | HBase compare les valeurs en **texte** (`"432.32" < "50"`, voir la requête 10). Les comparaisons numériques se font dans Spark (`toDouble`) |
| Row key `zone#AAAA-MM` | permet un **scan par préfixe** (tous les mois d'une zone sans parcourir la table) |
| `fire_alerts` avec 10 versions | l'historique des alertes est stocké dans la cellule elle-même |
| Option `--ts` (timestamp = heure de détection) | versions triées chronologiquement, filtrage par période avec `TIMERANGE`, rechargement **sans doublon** (idempotent). Les pixels d'un même passage satellite forment une seule version (18 alertes donnent 8 événements pour `36.5_9.0`) |
| Producteur sur **stdout** + `kafka-console-producer.sh` | aucune bibliothèque Python à installer (Python 3.5). Les messages d'information partent sur stderr pour ne pas polluer le topic |

---

## 11. Dépannage

| Symptôme | Cause | Solution |
|---|---|---|
| `Name node is in safe mode` | HDFS vient de démarrer | attendre, ou `hdfs dfsadmin -safemode leave` |
| `Can't get master address from ZooKeeper` | HMaster pas prêt ou arrêté | `stop-hbase.sh`, puis `start-hbase.sh`, attendre 1 min |
| Journaux `INFO ... ZooKeeperServer` dans le terminal | ZooKeeper / Kafka lancés au premier plan dans ce terminal | travailler dans un autre terminal, ou lancer via `demo_stream.sh` (journaux dans `logs/`) |
| `Erreur API 400` | `--days` supérieur à 5, ou `$FIRMS_KEY` vide | `--days 1` à `5`, vérifier `echo $FIRMS_KEY` |
| Aucune alerte écrite, Spark en retard | micro-batchs plus longs que 10 s | lancer avec `--master local[2]`, attendre la fin du traitement avant Ctrl+C |
| Terminal Spark bloqué après Ctrl+C | annulation des jobs en cours | 2ᵉ Ctrl+C, sinon `jps` puis `kill -9 <PID de SparkSubmit>` |
| `LoadError: No such file to load` | `hbase shell` lancé depuis un autre dossier | `cd ~/projet/module_C_streaming_hbase` ou chemin complet |
| `Table already exists` | tables déjà créées | normal. Pour repartir de zéro : `disable 'table'` puis `drop 'table'` |
| `/bin/bash^M: bad interpreter` | fichier en fins de ligne Windows (CRLF) | `sed -i 's/\r$//' demo_stream.sh` et régler VS Code sur LF |
| `BrokenPipeError` avec `\| head` | `head` ferme la sortie | sans conséquence |
| Plus de 70 alertes | anciens messages ou anciennes alertes | `hdfs dfs -rm -r /fires/stream/alerts` puis relancer |

---

## 12. Limites et améliorations possibles

- **Quasi temps réel** : le satellite S-NPP ne survole la Tunisie que quelques fois par jour, et la NASA publie avec environ 3 h de délai. L'architecture accepterait sans modification des sources plus rapides (capteurs au sol, caméras).
- Le seuil d'alerte (`frp >= 20`) est fixé empiriquement. Il pourrait être ajusté par zone ou par saison.
- Les alertes passent par HDFS avant HBase. Une écriture directe de Spark Streaming vers HBase supprimerait cette étape.
- Visualisation possible : carte des alertes (Python + `folium`) ou tableau de bord à partir des tables HBase.

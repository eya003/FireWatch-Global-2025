# 🔥 FireWatch Global 2025 — Module A

## Hadoop HDFS & MapReduce

**Projet :** FireWatch Global 2025  
**Module :** A — Stockage distribué et traitement Batch  
**Technologies :** Apache Hadoop, HDFS, YARN, Hadoop Streaming, Python, Docker  
**Dataset :** NASA FIRMS — VIIRS S-NPP — 2025

---

## 1. Présentation du module

FireWatch Global 2025 est un projet Big Data consacré à l'analyse des détections thermiques satellitaires enregistrées dans le monde durant l'année 2025.

Le module A repose sur **Hadoop HDFS et MapReduce** pour assurer le stockage distribué, le traitement et l'agrégation des données NASA FIRMS.

### Objectifs

- Stocker les données mondiales dans HDFS.
- Vérifier l'intégrité des fichiers distribués.
- Analyser les détections par mois et par catégorie.
- Identifier les zones géographiques présentant le plus de détections.
- Calculer la puissance radiative moyenne (FRP) par zone.
- Optimiser les traitements avec un Combiner.
- Comparer les performances avec et sans Combiner.
- Générer des fichiers CSV exploitables par les autres modules du projet.

Les traitements sont implémentés en Python et exécutés de manière distribuée avec **Hadoop Streaming**.

## 2. Dataset NASA FIRMS

### 2.1. Source des données

Les données proviennent du service **Fire Information for Resource Management System (FIRMS)** de la NASA.

- **Satellite :** Suomi NPP
- **Capteur :** VIIRS
- **Produit :** Standard Processing
- **Période :** 1er janvier au 31 décembre 2025
- **Couverture :** mondiale
- **Format :** CSV

Source officielle : https://firms.modaps.eosdis.nasa.gov/

### 2.2. Caractéristiques du dataset

| Caractéristique | Valeur |
|---|---:|
| Fichiers CSV | 219 |
| Pays et territoires représentés | 219 |
| Observations totales | 18 415 101 |
| Colonnes | 15 |
| Taille décompressée | 1 450 617 875 octets |
| Année | 2025 |

Archive utilisée :

`viirs-snpp_2025_all_countries.zip`

### 2.3. Schéma des données

Les fichiers partagent les 15 colonnes suivantes :

```text
latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight,type
```

Principales variables exploitées :

| Colonne | Description |
|---|---|
| `latitude` | Latitude de la détection |
| `longitude` | Longitude de la détection |
| `acq_date` | Date de l'observation |
| `acq_time` | Heure de l'observation |
| `frp` | Puissance radiative estimée, en MW |
| `type` | Catégorie de la source thermique |
| `confidence` | Catégorie de confiance de la détection |
| `daynight` | Détection de jour ou de nuit |

Le nom du pays provient des fichiers sources. Il ne constitue pas une colonne du schéma CSV d'origine.

### 2.4. Répartition des types

| Type | Catégorie | Observations |
|---|---|---:|
| 0 | Feu de végétation présumé | 17 017 025 |
| 1 | Volcan actif | 35 575 |
| 2 | Autre source thermique terrestre statique | 1 280 380 |
| 3 | Source thermique offshore | 82 121 |
| **Total** | | **18 415 101** |

Les analyses temporelles, géographiques et FRP utilisent les observations de **type 0**.

Le traitement de répartition par catégorie conserve les quatre types.

### 2.5. Qualité des données

Un audit de l'archive source a permis de vérifier :

| Contrôle | Résultat |
|---|---:|
| Intégrité CRC de l'archive | Valide |
| Schémas distincts | 1 |
| Fichiers incorrects signalés | 0 |
| Valeurs vides signalées | 0 |
| Valeurs numériques invalides | 0 |
| Dates invalides | 0 |
| Coordonnées invalides | 0 |
| Doublons exacts signalés | 0 |
| FRP égales à zéro | 3 881 |
| FRP supérieures à 1 000 MW | 131 |

Les statistiques de qualité portent sur l'ensemble des 18 415 101 observations, toutes catégories confondues.

## 3. Environnement technique

Les traitements ont été réalisés dans un cluster Hadoop exécuté avec Docker.

### Infrastructure

| Composant | Configuration |
|---|---|
| Système hôte | Windows |
| Conteneurisation | Docker Desktop |
| Image Hadoop | `liliasfaxi/spark-hadoop:hv-2.7.2` |
| Hadoop | 2.7.2 |
| Python dans les conteneurs | 3.5.2 |
| Nœud principal | `hadoop-master` |
| Nœuds secondaires | `hadoop-slave1`, `hadoop-slave2` |
| Système de fichiers | HDFS |
| Gestionnaire de ressources | YARN |
| Moteur de traitement | Hadoop MapReduce / Streaming |

Le fichier JAR utilisé est :

```text
/usr/local/hadoop/share/hadoop/tools/lib/hadoop-streaming-2.7.2.jar
```

## 4. Architecture du traitement

Le pipeline du module suit les étapes suivantes :

```text
       NASA FIRMS — 219 CSV
                |
                v
       load_hdfs.py
                |
                v
       HDFS /fires/raw/world/
                |
                v
       run_mapreduce.py
                |
                v
       Hadoop MapReduce
        /      |       \
    Mapper  Combiner  Reducer
                |
                v
       Résultats dans HDFS
                |
                v
       export_results.py
                |
                v
         Fichiers CSV
                |
                v
       Analyses et visualisations
```

Le script Python `run_mapreduce.py` pilote les commandes Hadoop.

Les calculs distribués sont réalisés par Hadoop à travers les Mappers, Combiners et Reducers Python.

## 5. Structure des fichiers

```text
module_A_mapreduce/
│
├── README.md
│
├── load_hdfs.py
├── run_mapreduce.py
├── export_results.py
│
├── mapper_month.py
├── mapper_type.py
├── mapper_zone.py
├── mapper_frp.py
│
├── reducer_sum.py
├── reducer_frp.py
├── combiner_frp.py
│
└── exports/
    ├── fires_by_month.csv
    ├── fires_by_type.csv
    ├── fires_by_zone.csv
    └── frp_by_zone.csv
```

### Description des scripts

| Fichier | Fonction |
|---|---|
| `load_hdfs.py` | Chargement sécurisé et contrôle d'intégrité HDFS |
| `run_mapreduce.py` | Orchestration des jobs Hadoop Streaming |
| `export_results.py` | Vérification et export des résultats CSV |
| `mapper_month.py` | Extraction du mois pour chaque détection de type 0 |
| `mapper_type.py` | Extraction de la catégorie de chaque observation |
| `mapper_zone.py` | Calcul de la cellule géographique |
| `mapper_frp.py` | Extraction de la FRP et de la cellule géographique |
| `reducer_sum.py` | Agrégation des comptages |
| `combiner_frp.py` | Agrégation locale des sommes FRP et des effectifs |
| `reducer_frp.py` | Calcul final des FRP moyennes |

## 6. Stockage distribué avec HDFS

### 6.1. Organisation HDFS

```text
/fires/
├── raw/
│   └── world/
│       └── 219 fichiers CSV
│
├── sample/
│   └── sample_fires.csv
│
└── results/
    └── mapreduce/
        ├── month_world_combiner/
        ├── month_world_no_combiner_a6/
        ├── type_world/
        ├── zone_world/
        ├── frp_world/
        └── csv/
```

### 6.2. Chargement avec Python

Le fichier `load_hdfs.py` automatise le stockage des fichiers NASA dans HDFS.

Il réalise notamment :

1. La vérification du nombre et de la taille des fichiers.
2. La vérification des en-têtes CSV.
3. Le chargement dans un dossier HDFS temporaire pour un nouveau dataset.
4. La vérification de l'intégrité HDFS.
5. La publication des données validées dans `/fires/raw/world/`.

Le script protège les données déjà présentes contre un écrasement accidentel.

### 6.3. Vérification HDFS

Résultats du contrôle effectué sur le dataset mondial :

| Indicateur | Résultat |
|---|---:|
| Fichiers | 219 |
| Taille logique | 1 450 617 875 octets |
| Blocs | 220 |
| DataNodes | 2 |
| Facteur de réplication | 2 |
| Blocs corrompus | 0 |
| Réplicas manquants | 0 |
| État du système de fichiers | **HEALTHY** |

## 7. Traitements Hadoop MapReduce

### 7.1. A4 — Comptage des détections par mois

**Objectif :** déterminer le nombre mensuel de détections de végétation présumées durant l'année 2025.

Le Mapper :

- Lit chaque observation CSV.
- Conserve les observations de `type = 0`.
- Extrait le mois depuis `acq_date`.
- Émet une paire `(mois, 1)`.

Exemple :

```text
2025-08    1
2025-08    1
```

Le Reducer additionne les valeurs associées à chaque mois.

**Sortie :** `fires_by_month.csv`

### 7.2. A5.1 — Comptage par type

**Objectif :** calculer le nombre d'observations dans chaque catégorie NASA.

Le Mapper produit :

```text
0    1
2    1
0    1
```

Le Reducer additionne les valeurs par type.

**Sortie :** `fires_by_type.csv`

### 7.3. A5.2 — Comptage par zone géographique

**Objectif :** regrouper les observations de type 0 dans des cellules géographiques de 0,5° × 0,5°.

Calcul de la cellule :

```python
zone_lat = math.floor(latitude * 2) / 2.0
zone_lon = math.floor(longitude * 2) / 2.0

zone = "{:.1f}_{:.1f}".format(zone_lat, zone_lon)
```

Exemple :

```text
Latitude  : 36.78
Longitude : 10.24

Zone : 36.5_10.0
```

Chaque observation contribue au compteur de sa cellule.

**Sortie :** `fires_by_zone.csv`

### 7.4. A7 — FRP moyenne par zone

**Objectif :** calculer la puissance radiative moyenne des détections de végétation pour chaque cellule géographique.

Le Mapper produit :

```text
zone    frp    1
```

Le Combiner calcule localement :

```text
zone    somme_frp    nombre
```

Le Reducer fusionne les résultats partiels, puis calcule :

\[
FRP_{moyenne}=\frac{\sum FRP}{N}
\]

Cette méthode permet d'obtenir une moyenne globale correcte sans calculer une moyenne de moyennes.

Les FRP égales à zéro sont conservées dans le calcul. Les valeurs négatives ou non finies sont exclues.

**Sortie :** `frp_by_zone.csv`

## 8. Automatisation et exécution

### 8.1. Accéder au conteneur Hadoop

Depuis PowerShell :

```powershell
docker exec -it hadoop-master bash
```

Accéder au dossier :

```bash
cd /root/module_A_mapreduce
```

Les commandes suivantes s'exécutent à l'intérieur du conteneur.

### 8.2. Vérifier les données HDFS

```bash
python3 load_hdfs.py --check-only
```

Cette commande contrôle le nombre de fichiers, la taille et l'intégrité des blocs HDFS, sans effectuer de nouveau chargement.

### 8.3. Charger les données

Pour un premier chargement, les CSV sources doivent être présents dans le conteneur.

Par défaut, le script utilise :

```text
/tmp/fires_world_2025/
```

Exécution :

```bash
python3 load_hdfs.py
```

Pour spécifier un autre dossier :

```bash
python3 load_hdfs.py --source /chemin/vers/les_csv
```

### 8.4. Exécuter les traitements MapReduce

```bash
python3 run_mapreduce.py
```

Le script orchestre les quatre jobs :

- Comptage mensuel.
- Comptage par type.
- Comptage par zone.
- FRP moyenne par zone.

Il vérifie les résultats existants et empêche leur écrasement automatique.

Les nouveaux jobs disposent d'un manifeste contenant une signature de leurs scripts et de leur configuration.

Pour réutiliser explicitement les sorties historiques validées avant l'introduction des manifestes :

```bash
python3 run_mapreduce.py --allow-legacy
```

Pour inclure l'expérience de comptage mensuel sans Combiner :

```bash
python3 run_mapreduce.py --allow-legacy --compare-combiner
```

Pour générer une nouvelle version des résultats dans des dossiers distincts :

```bash
python3 run_mapreduce.py --suffix v2
```

Cette dernière option conserve les anciens résultats.

### 8.5. Exporter les résultats CSV

```bash
python3 export_results.py
```

Ce programme :

- Lit les résultats Hadoop depuis HDFS.
- Convertit les paires clé-valeur en CSV.
- Contrôle les valeurs numériques et les effectifs attendus.
- Vérifie la cohérence des totaux.
- Compare les ensembles de cellules géographiques.
- Enregistre les CSV localement et dans HDFS.

Dossier des exports locaux :

```text
module_A_mapreduce/exports/
```

Dossier des exports HDFS :

```text
/fires/results/mapreduce/csv/
```

Les exports standard sont construits à partir des sorties HDFS canoniques du module.

## 9. Résultats obtenus

### 9.1. Détections mensuelles — Type 0

| Mois | Détections |
|---|---:|
| Janvier | 1 629 374 |
| Février | 1 304 268 |
| Mars | 1 414 644 |
| Avril | 941 585 |
| Mai | 989 061 |
| Juin | 1 093 639 |
| Juillet | 1 636 873 |
| Août | 2 522 565 |
| Septembre | 1 934 941 |
| Octobre | 1 577 832 |
| Novembre | 988 538 |
| Décembre | 983 705 |
| **Total** | **17 017 025** |

Le mois d'août présente le plus grand nombre de détections dans le jeu de données mondial.

### 9.2. Agrégation géographique

| Indicateur | Résultat |
|---|---:|
| Observations de type 0 | 17 017 025 |
| Cellules géographiques distinctes | 37 790 |
| Cellules disposant d'une FRP moyenne | 37 790 |

Les deux traitements géographiques produisent les mêmes identifiants de cellules.

### 9.3. Exports finaux

| Fichier | Colonnes | Lignes de données |
|---|---|---:|
| `fires_by_month.csv` | `month,count` | 12 |
| `fires_by_type.csv` | `type,count` | 4 |
| `fires_by_zone.csv` | `zone,count` | 37 790 |
| `frp_by_zone.csv` | `zone,avg_frp_mw` | 37 790 |

Les deux fichiers géographiques peuvent être associés par la colonne `zone`.

## 10. Expérience d'optimisation avec Combiner

### 10.1. Objectif

Étudier l'effet du Combiner sur le volume des données intermédiaires et le temps d'exécution d'un job Hadoop MapReduce.

L'expérience compare le comptage mensuel mondial :

- Sans Combiner.
- Avec Combiner utilisant `reducer_sum.py`.

### 10.2. Résultats expérimentaux

| Indicateur | Sans Combiner | Avec Combiner |
|---|---:|---:|
| Mappers | 220 | 220 |
| Reducers | 1 | 1 |
| Map output records | 17 017 025 | 17 017 025 |
| Reduce input records | 17 017 025 | 2 216 |
| Reduce shuffle bytes | 204 205 620 | 31 909 |
| Temps YARN | 388,039 s | 475,942 s |
| Résultats finaux | 12 mois | 12 mois |

### 10.3. Analyse

Le Combiner a réduit les données transférées pendant le Shuffle d'environ **99,984 %**, soit plus de 6 000 fois moins d'octets.

Les résultats mensuels sont restés strictement identiques avec et sans Combiner.

Cependant, dans cette expérience, le traitement avec Combiner a pris davantage de temps :

- Sans Combiner : environ 6 min 28 s.
- Avec Combiner : environ 7 min 56 s.

Le gain sur le Shuffle est donc démontré, mais une accélération globale n'a pas été observée lors de ces exécutions.

Ce résultat illustre la différence entre **réduction des données intermédiaires** et **amélioration du temps total**, qui dépend aussi des coûts de calcul et des ressources du cluster.

## 11. Validation du module

Les traitements ont été vérifiés à plusieurs niveaux.

### Tests sur l'échantillon tunisien

Un échantillon de 200 observations a été utilisé pour les premiers tests.

Il contient :

- 120 observations de type 0.
- 80 observations de type 2.

Les comptages et les calculs géographiques ont été comparés aux résultats attendus.

Le traitement par zone sur cet échantillon a identifié 33 cellules géographiques.

### Validation mondiale

Les quatre traitements Hadoop ont été exécutés sur les 219 fichiers mondiaux.

Les vérifications ont confirmé :

- Le total de 18 415 101 observations pour le comptage par type.
- Le total de 17 017 025 observations de type 0.
- La concordance des résultats mensuels avec et sans Combiner.
- La cohérence des 37 790 cellules entre les comptages et les FRP moyennes.
- La génération des quatre CSV.
- L'intégrité du stockage HDFS.

Les scripts d'automatisation Python permettent de reproduire les opérations de chargement, de traitement et d'export.

## 12. Interprétation des résultats

Les statistiques du module doivent être interprétées selon la nature des observations satellites.

Une détection FIRMS ne correspond pas nécessairement à un incendie distinct. Un même événement peut être observé plusieurs fois.

Le type 0 représente un feu de végétation présumé, et non un incendie confirmé au sol.

Les cellules de 0,5° × 0,5° ne possèdent pas une superficie identique en kilomètres carrés à toutes les latitudes.

La FRP moyenne exprime une puissance radiative moyenne par observation. Elle ne constitue pas une mesure directe de la surface brûlée ou des dommages.

Les résultats de ce module décrivent les observations de l'année 2025, sans prédiction d'incendies futurs.

## 13. Intégration au projet FireWatch

Le module A fournit quatre jeux de résultats agrégés :

```text
fires_by_month.csv
fires_by_type.csv
fires_by_zone.csv
frp_by_zone.csv
```

Ces fichiers peuvent être utilisés pour :

- La comparaison avec les analyses Apache Spark.
- Les graphiques de répartition temporelle.
- Les cartes géographiques des détections.
- La visualisation des puissances radiatives moyennes.
- Les analyses historiques dans les autres modules du projet.

Les autres composants du système FireWatch sont documentés séparément dans leurs modules respectifs.

---

**FireWatch Global 2025 — Module A**  
*Apache Hadoop · HDFS · YARN · MapReduce · Hadoop Streaming · Python*

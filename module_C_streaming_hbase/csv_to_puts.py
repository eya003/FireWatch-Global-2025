#!/usr/bin/env python3
# csv_to_puts.py - Membre C
# Transforme un fichier CSV du contrat en fichier de commandes HBase "put".
# Le fichier produit s'execute avec : hbase shell fichier.hbase
#
# Exemples :
#   python3 csv_to_puts.py --csv fires_by_month.csv --table fire_monthly --key year_month \
#           --family mr --columns count > puts_monthly_mr.hbase
#   python3 csv_to_puts.py --csv alerts.csv --names zone,acq_date,acq_time,latitude,longitude,frp,confidence \
#           --table fire_alerts --key zone --family last \
#           --columns acq_date,acq_time,latitude,longitude,frp,confidence --ts acq_date,acq_time > puts_alerts.hbase

import sys
import csv
import argparse
import calendar
import time


def quote(texte):
    # protege les apostrophes pour le shell HBase
    return "'" + texte.replace("\\", "\\\\").replace("'", "\\'") + "'"


def timestamp_ms(date, heure):
    # "2025-09-13" + "1206" -> millisecondes depuis 1970 (UTC)
    t = time.strptime(date + heure.zfill(4), "%Y-%m-%d%H%M")
    return calendar.timegm(t) * 1000


def main():
    p = argparse.ArgumentParser(description="CSV -> commandes put HBase")
    p.add_argument("--csv", required=True, help="fichier CSV d'entree")
    p.add_argument("--names", help="noms des colonnes si le CSV n'a PAS d'en-tete (separes par des virgules)")
    p.add_argument("--table", required=True, help="table HBase")
    p.add_argument("--key", required=True, help="colonne(s) formant la row key, ex: zone,year_month")
    p.add_argument("--sep", default="#", help="separateur entre les parties de la cle (defaut #)")
    p.add_argument("--family", required=True, help="famille de colonnes HBase")
    p.add_argument("--columns", help="colonnes a inserer (defaut : toutes sauf la cle)")
    p.add_argument("--ts", help="colonnes date,heure servant de timestamp de la cellule (ex: acq_date,acq_time)")
    a = p.parse_args()

    cles = a.key.split(",")
    with open(a.csv) as f:
        if a.names:
            lecteur = csv.DictReader(f, fieldnames=a.names.split(","))
        else:
            lecteur = csv.DictReader(f)          # la 1re ligne = en-tete
        colonnes = a.columns.split(",") if a.columns else [c for c in lecteur.fieldnames if c not in cles]

        n_lignes = 0
        n_puts = 0
        for ligne in lecteur:
            if ligne[cles[0]] is None or ligne[cles[0]] == "":
                continue                           # ligne vide ou incomplete
            row_key = a.sep.join(ligne[c].strip() for c in cles)
            ts = ""
            if a.ts:
                d, h = a.ts.split(",")
                ts = ", " + str(timestamp_ms(ligne[d].strip(), ligne[h].strip()))
            for c in colonnes:
                valeur = ligne[c].strip()
                print("put {}, {}, {}, {}{}".format(
                    quote(a.table), quote(row_key), quote(a.family + ":" + c), quote(valeur), ts))
                n_puts += 1
            n_lignes += 1

    print("exit")
    sys.stderr.write("{} lignes -> {} commandes put pour la table {}\n".format(n_lignes, n_puts, a.table))


if __name__ == "__main__":
    main()

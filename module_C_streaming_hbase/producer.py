# producer.py - Membre C
# Envoie des detections FIRMS ligne par ligne sur la sortie standard.
# La sortie est redirigee vers Kafka avec kafka-console-producer.sh.
#
# Mode rejeu : python3 producer.py --replay fichier.csv --rate 5
# Mode API   : python3 producer.py --api MAP_KEY --interval 600 --days 1

import sys
import time
import argparse
import urllib.request

BBOX = "7.5,30.2,11.6,37.6"   # ouest,sud,est,nord : rectangle autour de la Tunisie
API_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{bbox}/{days}"


def send(line):
    # stdout = ce qui part dans Kafka
    print(line)
    sys.stdout.flush()   # envoie la ligne tout de suite (sinon Python attend)


def log(msg):
    # stderr = messages pour l'utilisateur, qui ne vont PAS dans Kafka
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def is_header(line):
    return line.startswith("latitude")


def replay(path, rate):
    pause = 1.0 / rate
    n = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if len(line) == 0 or is_header(line):
                continue
            send(line)
            n += 1
            time.sleep(pause)
    log("Rejeu termine : {} lignes envoyees".format(n))


def fetch_api(key, days):
    url = API_URL.format(key=key, bbox=BBOX, days=days)
    reponse = urllib.request.urlopen(url, timeout=60)
    texte = reponse.read().decode("utf-8")
    lignes = []
    for l in texte.splitlines():
        l = l.strip()
        if len(l) > 0 and not is_header(l):
            lignes.append(l)
    return lignes


def api_loop(key, interval, days):
    deja_envoyees = set()   # pour ne pas renvoyer une detection deja envoyee
    while True:
        try:
            lignes = fetch_api(key, days)
            nouvelles = 0
            for line in lignes:
                c = line.split(",")
                ident = (c[0], c[1], c[5], c[6])   # latitude, longitude, date, heure
                if ident not in deja_envoyees:
                    deja_envoyees.add(ident)
                    send(line)
                    nouvelles += 1
            log("{} : {} detections recues, {} nouvelles".format(
                time.strftime("%H:%M:%S"), len(lignes), nouvelles))
        except Exception as e:
            log("Erreur API : {}".format(e))
        time.sleep(interval)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Producteur FIRMS pour Kafka")
    p.add_argument("--replay", help="fichier CSV a rejouer")
    p.add_argument("--rate", type=float, default=5, help="lignes par seconde (rejeu)")
    p.add_argument("--api", metavar="MAP_KEY", help="cle API NASA FIRMS")
    p.add_argument("--interval", type=int, default=600, help="secondes entre 2 appels API")
    p.add_argument("--days", type=int, default=1, help="jours demandes a l'API (1 a 10)")
    a = p.parse_args()

    if a.replay:
        replay(a.replay, a.rate)
    elif a.api:
        api_loop(a.api, a.interval, a.days)
    else:
        p.print_help()

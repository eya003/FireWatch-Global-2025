
#!/usr/bin/env python3
# FireWatch Global 2025 - Module A
# Chargement securise des CSV NASA dans HDFS
# Compatible Python 3.5

import argparse
import csv
import os
import re
import subprocess
import sys
import time

SOURCE_DEFAULT = "/tmp/fires_world_2025"

HDFS_DIR = "/fires/raw/world"
HDFS_PARENT = "/fires/raw"

EXPECTED_FILES = 219
EXPECTED_BYTES = 1450617875

EXPECTED_COLUMNS = [
    "latitude", "longitude", "bright_ti4",
    "scan", "track", "acq_date", "acq_time",
    "satellite", "instrument", "confidence",
    "version", "bright_ti5", "frp",
    "daynight", "type"
]


def run(command):
    subprocess.run(command, check=True)


def output(command):
    return subprocess.check_output(
        command
    ).decode("utf-8", "replace")


def hdfs_exists(path):
    return subprocess.call(
        ["hdfs", "dfs", "-test", "-e", path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ) == 0


def check_local(source):
    if not os.path.isdir(source):
        raise RuntimeError(
            "Dossier local introuvable : " + source
        )

    files = sorted([
        os.path.join(source, name)
        for name in os.listdir(source)
        if name.lower().endswith(".csv")
        and os.path.isfile(
            os.path.join(source, name)
        )
    ])

    if len(files) != EXPECTED_FILES:
        raise RuntimeError(
            "{} fichiers CSV au lieu de {}"
            .format(len(files), EXPECTED_FILES)
        )

    total_bytes = sum(
        os.path.getsize(path)
        for path in files
    )

    if total_bytes != EXPECTED_BYTES:
        raise RuntimeError(
            "Taille locale incorrecte : {}"
            .format(total_bytes)
        )

    # Verifier les en-tetes des 219 fichiers
    for path in files:
        with open(
            path,
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as f:
            reader = csv.reader(f)
            header = next(reader, None)

        if header != EXPECTED_COLUMNS:
            raise RuntimeError(
                "Schema CSV incorrect : " + path
            )

    print("Sources locales validees")
    print("CSV : {}".format(len(files)))
    print("Octets : {}".format(total_bytes))

    return files


def hdfs_file_names(path):
    listing = output([
        "hdfs", "dfs", "-ls", path
    ])

    names = []

    for line in listing.splitlines():
        parts = line.split()

        if len(parts) >= 8 and parts[0].startswith("-"):
            names.append(
                os.path.basename(parts[-1])
            )

    return names


def check_hdfs(path, expected_names=None):
    if not hdfs_exists(path):
        raise RuntimeError(
            "Dossier HDFS introuvable : " + path
        )

    result = output([
        "hdfs", "dfs", "-count", path
    ])

    parts = result.split()

    if len(parts) < 3:
        raise RuntimeError(
            "Reponse HDFS inattendue"
        )

    file_count = int(parts[1])
    total_bytes = int(parts[2])

    print("Fichiers HDFS : {}".format(file_count))
    print("Taille HDFS : {}".format(total_bytes))

    if file_count != EXPECTED_FILES:
        raise RuntimeError(
            "Nombre de fichiers HDFS incorrect"
        )

    if total_bytes != EXPECTED_BYTES:
        raise RuntimeError(
            "Taille HDFS incorrecte"
        )

    names = hdfs_file_names(path)

    if len(names) != EXPECTED_FILES:
        raise RuntimeError(
            "Liste des fichiers HDFS incorrecte"
        )

    if any(
        not name.lower().endswith(".csv")
        for name in names
    ):
        raise RuntimeError(
            "Fichier non CSV trouve dans HDFS"
        )

    if expected_names is not None:
        if set(names) != set(expected_names):
            raise RuntimeError(
                "Fichiers locaux et HDFS differents"
            )

    print("Verification des blocs HDFS...")

    fsck = output([
        "hdfs", "fsck",
        path, "-files", "-blocks"
    ])

    print("\n".join(fsck.splitlines()[-15:]))

    if not re.search(
        r"(Status:\s*HEALTHY| is HEALTHY)",
        fsck
    ):
        raise RuntimeError(
            "HDFS n'est pas HEALTHY"
        )

    for pattern in (
        r"Corrupt blocks:\s*0\b",
        r"Missing replicas:\s*0\b",
        r"Under-replicated blocks:\s*0\b"
    ):
        if not re.search(pattern, fsck):
            raise RuntimeError(
                "Verification des blocs non conforme"
            )

    print("Integrite HDFS validee.")


def main():
    parser = argparse.ArgumentParser(
        description="Chargement NASA FIRMS dans HDFS"
    )

    parser.add_argument(
        "--source",
        default=SOURCE_DEFAULT,
        help="Dossier local des 219 CSV dans le conteneur"
    )

    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verifier HDFS sans charger de donnees"
    )

    args = parser.parse_args()

    print("=== FireWatch : chargement HDFS ===")

    # Cas 1 : les donnees existent deja
    if hdfs_exists(HDFS_DIR):
        print("Dataset deja present.")

        check_hdfs(HDFS_DIR)

        print("Aucun chargement necessaire.")
        return

    if args.check_only:
        raise RuntimeError(
            "Dataset HDFS absent : rien a verifier"
        )

    # Cas 2 : premier chargement
    files = check_local(args.source)

    expected_names = [
        os.path.basename(path)
        for path in files
    ]

    run([
        "hdfs", "dfs", "-mkdir", "-p",
        HDFS_PARENT
    ])

    # Utiliser un dossier temporaire unique
    staging = (
        HDFS_PARENT + "/.world_staging_"
        + str(int(time.time()))
        + "_" + str(os.getpid())
    )

    if hdfs_exists(staging):
        raise RuntimeError(
            "Dossier temporaire deja existant"
        )

    print("Chargement temporaire : " + staging)

    run([
        "hdfs", "dfs", "-mkdir", staging
    ])

    try:
        # Copier les 219 fichiers dans HDFS
        run(
            ["hdfs", "dfs", "-put"]
            + files
            + [staging]
        )

        # Verifier avant de publier
        check_hdfs(staging, expected_names)

        # Ne jamais ecraser le dossier final
        if hdfs_exists(HDFS_DIR):
            raise RuntimeError(
                "Le dossier final est apparu "
                "pendant le chargement"
            )

        # Publication par renommage HDFS
        run([
            "hdfs", "dfs", "-mv",
            staging, HDFS_DIR
        ])

        # Dernier controle
        check_hdfs(HDFS_DIR, expected_names)

        print("=== Chargement HDFS valide ===")

    except Exception:
        print(
            "ERREUR : verification ou chargement "
            "interrompu.",
            file=sys.stderr
        )
        print(
            "Verifier le dossier temporaire : "
            + staging,
            file=sys.stderr
        )
        print(
            "Aucune suppression automatique effectuee.",
            file=sys.stderr
        )
        raise


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        RuntimeError,
        ValueError,
        subprocess.CalledProcessError
    ) as error:
        print(
            "ERREUR : {}".format(error),
            file=sys.stderr
        )
        sys.exit(1)

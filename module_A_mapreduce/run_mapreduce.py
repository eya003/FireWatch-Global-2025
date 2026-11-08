import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT = "/fires/raw/world"
OUTPUT_BASE = "/fires/results/mapreduce"

STREAMING_JAR = (
    "/usr/local/hadoop/share/hadoop/tools/lib/"
    "hadoop-streaming-2.7.2.jar"
)

EXPECTED_FILES = 219
EXPECTED_BYTES = 1450617875


def hdfs_exists(path):
    return subprocess.call(
        ["hdfs", "dfs", "-test", "-e", path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    ) == 0


def hdfs_output(arguments):
    return subprocess.check_output(
        ["hdfs", "dfs"] + arguments
    ).decode("utf-8")


def sha256_file(path):
    digest = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


def check_input():
    if not hdfs_exists(INPUT):
        raise RuntimeError(
            "Dataset HDFS introuvable : " + INPUT
        )

    # Verification rapide de la couverture HDFS
    result = hdfs_output(["-count", INPUT])
    parts = result.split()

    if len(parts) < 3:
        raise RuntimeError("Reponse HDFS inattendue")

    file_count = int(parts[1])
    total_bytes = int(parts[2])

    if file_count != EXPECTED_FILES:
        raise RuntimeError(
            "Nombre de fichiers incorrect : {}"
            .format(file_count)
        )

    if total_bytes != EXPECTED_BYTES:
        raise RuntimeError(
            "Taille du dataset incorrecte : {}"
            .format(total_bytes)
        )

    print("Dataset HDFS : {} fichiers, {} octets"
          .format(file_count, total_bytes))

    # Empreinte des noms, tailles et dates HDFS
    listing = hdfs_output(["-ls", INPUT])

    return hashlib.sha256(
        listing.encode("utf-8")
    ).hexdigest()


def get_signature(job, input_signature):
    scripts = [job["mapper"], job["reducer"]]

    if job["combiner"]:
        scripts.append(job["combiner"])

    script_hashes = {}

    for script in set(scripts):
        path = os.path.join(BASE_DIR, script)

        if not os.path.isfile(path):
            raise RuntimeError(
                "Script introuvable : " + path
            )

        script_hashes[script] = sha256_file(path)

    if not os.path.isfile(STREAMING_JAR):
        raise RuntimeError(
            "Hadoop Streaming introuvable"
        )

    configuration = {
        "job": job["name"],
        "input": INPUT,
        "input_signature": input_signature,
        "mapper": job["mapper"],
        "reducer": job["reducer"],
        "combiner": job["combiner"],
        "reducers": 1,
        "scripts_sha256": script_hashes,
        "streaming_jar_sha256": sha256_file(
            STREAMING_JAR
        )
    }

    serialized = json.dumps(
        configuration,
        sort_keys=True
    ).encode("utf-8")

    return hashlib.sha256(serialized).hexdigest()


def read_manifest(output_path):
    path = output_path + "/_firewatch_manifest.json"

    if not hdfs_exists(path):
        return None

    content = hdfs_output(["-cat", path])

    return json.loads(content)


def write_manifest(output_path, signature, job):
    metadata = {
        "job": job["name"],
        "output": output_path,
        "signature": signature,
        "validation": "SUCCESS"
    }

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False
        ) as f:
            json.dump(metadata, f, indent=2)
            temp_path = f.name

        subprocess.run([
            "hdfs", "dfs", "-put", "-f",
            temp_path,
            output_path + "/_firewatch_manifest.json"
        ], check=True)

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def run_job(job, input_signature, args):
    name = job["name"]
    output_name = job["output"]

    if args.suffix:
        output_name += "_" + args.suffix

    output_path = OUTPUT_BASE + "/" + output_name

    print("\n=== {} ===".format(name))

    signature = get_signature(job, input_signature)

    if hdfs_exists(output_path):

        if not hdfs_exists(output_path + "/_SUCCESS"):
            raise RuntimeError(
                "Sortie HDFS incomplete : " + output_path
            )

        manifest = read_manifest(output_path)

        if manifest is None:
            if args.allow_legacy:
                print(
                    "Sortie historique sans manifeste : "
                    "reutilisee sur confirmation."
                )
                return

            raise RuntimeError(
                "Sortie historique sans manifeste : {}. "
                "Utiliser --allow-legacy pour la "
                "conserver, ou --suffix pour creer "
                "une nouvelle sortie."
                .format(output_path)
            )

        if manifest.get("signature") != signature:
            raise RuntimeError(
                "Le code, la configuration ou les "
                "metadonnees d'entree ont change. "
                "Utiliser --suffix pour produire "
                "une nouvelle version sans supprimer "
                "les anciens resultats."
            )

        print("Resultat deja valide : job ignore.")
        return

    scripts = [job["mapper"], job["reducer"]]

    if job["combiner"]:
        scripts.append(job["combiner"])

    command = [
        "hadoop", "jar", STREAMING_JAR,
        "-D", "mapreduce.job.name=" + name,
        "-D", "mapreduce.job.reduces=1",
        "-files", ",".join(sorted(set(scripts))),
        "-input", INPUT,
        "-output", output_path,
        "-mapper", "python3 " + job["mapper"],
        "-reducer", "python3 " + job["reducer"]
    ]

    if job["combiner"]:
        command.extend([
            "-combiner",
            "python3 " + job["combiner"]
        ])

    print("Lancement du job Hadoop...")

    subprocess.run(
        command,
        cwd=BASE_DIR,
        check=True
    )

    if not hdfs_exists(output_path + "/_SUCCESS"):
        raise RuntimeError(
            "Job termine sans _SUCCESS : " + name
        )

    write_manifest(output_path, signature, job)

    print("Job Hadoop valide : " + name)


def build_jobs():
    return [
        {
            "name": "firewatch-month-world",
            "output": "month_world_combiner",
            "mapper": "mapper_month.py",
            "reducer": "reducer_sum.py",
            "combiner": "reducer_sum.py"
        },
        {
            "name": "firewatch-type-world",
            "output": "type_world",
            "mapper": "mapper_type.py",
            "reducer": "reducer_sum.py",
            "combiner": None
        },
        {
            "name": "firewatch-zone-world",
            "output": "zone_world",
            "mapper": "mapper_zone.py",
            "reducer": "reducer_sum.py",
            "combiner": None
        },
        {
            "name": "firewatch-frp-world",
            "output": "frp_world",
            "mapper": "mapper_frp.py",
            "reducer": "reducer_frp.py",
            "combiner": "combiner_frp.py"
        }
    ]


def main():
    parser = argparse.ArgumentParser(
        description="FireWatch Hadoop MapReduce"
    )

    parser.add_argument(
        "--allow-legacy",
        action="store_true",
        help="Conserver les sorties historiques sans manifeste"
    )

    parser.add_argument(
        "--compare-combiner",
        action="store_true",
        help="Inclure le job mensuel sans Combiner (A6)"
    )

    parser.add_argument(
        "--suffix",
        default="",
        help="Suffixe des nouvelles sorties HDFS"
    )

    args = parser.parse_args()

    if args.suffix and not re.match(
        r"^[A-Za-z0-9_-]+$", args.suffix
    ):
        parser.error("Suffixe invalide")

    input_signature = check_input()
    jobs = build_jobs()

    if args.compare_combiner:
        jobs.append({
            "name": "firewatch-month-no-combiner-a6",
            "output": "month_world_no_combiner_a6",
            "mapper": "mapper_month.py",
            "reducer": "reducer_sum.py",
            "combiner": None
        })

    for job in jobs:
        run_job(job, input_signature, args)

    print("\n=== Tous les jobs sont valides ===")


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        RuntimeError,
        ValueError,
        subprocess.CalledProcessError
    ) as error:
        print("ERREUR : {}".format(error), file=sys.stderr)
        sys.exit(1)

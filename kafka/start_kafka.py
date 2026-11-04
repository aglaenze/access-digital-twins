"""Starts a local Kafka broker for the digital twins (single node, KRaft mode: no ZooKeeper), as the data streaming of
ESS: the detector of the twin publishes its neutrons on it, just-bin-it histograms them, NICOS shows the histograms.

    python kafka/start_kafka.py                # foreground; Ctrl+C stops it
    python kafka/start_kafka.py --check        # only checks that a broker answers on localhost:9092
    python kafka/start_kafka.py --topics odin  # creates the topics of an instrument (broker running)

Needs Apache Kafka (3.9, Scala 2.13) and Java (≥ 17):
  * KAFKA_HOME: Kafka folder (default ~/McStas_runs/kafka_2.13-3.9.1), from
    https://archive.apache.org/dist/kafka/3.9.1/kafka_2.13-3.9.1.tgz;
  * JAVA_HOME: Java folder; default: the conda environment "kafka" (conda create -n kafka -c conda-forge openjdk=21),
    or the java found on the PATH.
The broker listens on 127.0.0.1 only (this computer). Its data go to <TWIN_RUN_ROOT>/kafka/ and are kept 2 hours:
the detector stream of a twin is large (~0.5 million neutrons per second for ODIN), and only the live display reads
it; the files are written by the twin itself.
"""
import argparse
import base64
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid

HOME = os.path.expanduser("~")
KAFKA_HOME = os.environ.get("KAFKA_HOME", os.path.join(HOME, "McStas_runs", "kafka_2.13-3.9.1"))
TWIN_RUN_ROOT = os.environ.get("TWIN_RUN_ROOT", os.path.join(HOME, "McStas_runs", "twin"))
DATA = os.path.join(TWIN_RUN_ROOT, "kafka")
PORT, CONTROLLER_PORT = 9092, 9093

PROPERTIES = f"""# written by start_kafka.py: local single-node broker of the digital twins
process.roles=broker,controller
node.id=1
controller.quorum.voters=1@127.0.0.1:{CONTROLLER_PORT}
listeners=PLAINTEXT://127.0.0.1:{PORT},CONTROLLER://127.0.0.1:{CONTROLLER_PORT}
advertised.listeners=PLAINTEXT://127.0.0.1:{PORT}
controller.listener.names=CONTROLLER
inter.broker.listener.name=PLAINTEXT
listener.security.protocol.map=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
log.dirs={os.path.join(DATA, "logs").replace(os.sep, "/")}
num.partitions=1
offsets.topic.replication.factor=1
transaction.state.log.replication.factor=1
transaction.state.log.min.isr=1
auto.create.topics.enable=true
# detector streams: keep 2 hours, small segments so that old data are deleted soon
log.retention.ms=7200000
log.segment.bytes=67108864
log.retention.check.interval.ms=60000
# messages up to 16 MB (one source pulse of events, one histogram)
message.max.bytes=16777216
replica.fetch.max.bytes=16777216
"""


def answers(port=PORT, host="127.0.0.1"):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0


def cluster_id():
    """Random cluster id in the Kafka format: 16 bytes, base64 (URL alphabet) without padding."""
    return base64.urlsafe_b64encode(uuid.uuid4().bytes).decode().rstrip("=")


def topics(instrument):
    """Kafka topics of an instrument twin: detector stream, just-bin-it commands, heartbeat, responses, histograms."""
    return [f"{instrument}_{t}" for t in ("detector", "jbi_commands", "jbi_heartbeat", "jbi_responses",
                                          "visualisation")]


def create_topics(names, brokers=f"127.0.0.1:{PORT}"):
    """Creates the topics that do not exist yet, one partition each (just-bin-it waits for its command topic to
    exist and needs single-partition topics). Returns the names created."""
    from confluent_kafka.admin import AdminClient, NewTopic
    admin = AdminClient({"bootstrap.servers": brokers})
    existing = set(admin.list_topics(timeout=20).topics)
    new = [NewTopic(n, num_partitions=1, replication_factor=1) for n in names if n not in existing]
    for name, f in (admin.create_topics(new) if new else {}).items():
        f.result(timeout=30)
    return [t.topic for t in new]


def java_home():
    if os.environ.get("JAVA_HOME"):
        return os.environ["JAVA_HOME"]
    conda = os.path.join(HOME, "AppData", "Local", "miniforge3", "envs", "kafka", "Library") if os.name == "nt" \
        else os.path.join(os.environ.get("CONDA_ROOT", "/opt/conda"), "envs", "kafka")
    if os.path.isfile(os.path.join(conda, "bin", "java.exe" if os.name == "nt" else "java")):
        return conda
    java = shutil.which("java")
    if java:
        return os.path.dirname(os.path.dirname(os.path.realpath(java)))
    sys.exit("Java not found: set JAVA_HOME, or: conda create -n kafka -c conda-forge openjdk=21")


def java(main_class, *args, heap="-Xmx1G -Xms256M"):
    """Command line running a Kafka class with Java directly (the .bat scripts of Kafka build a command line too long
    for Windows when the classpath lists every jar; a wildcard classpath avoids it)."""
    exe = os.path.join(java_home(), "bin", "java.exe" if os.name == "nt" else "java")
    logs = os.path.join(DATA, "server-logs")
    os.makedirs(logs, exist_ok=True)
    return [exe, *heap.split(), "-Dkafka.logs.dir=" + logs,
            "-Dlog4j.configuration=file:" + os.path.join(KAFKA_HOME, "config", "log4j.properties").replace(os.sep, "/"),
            "-cp", os.path.join(KAFKA_HOME, "libs", "*"), main_class, *args]


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--check", action="store_true", help="only check that a broker answers")
    a.add_argument("--topics", metavar="INSTRUMENT", help="create the topics of an instrument (broker running)")
    args = a.parse_args()
    if args.topics:
        print("topics created:", create_topics(topics(args.topics)) or "none (all exist)")
        return
    if args.check or answers():
        ok = answers()
        print(f"Kafka broker on 127.0.0.1:{PORT}: {'running' if ok else 'not running'}")
        sys.exit(0 if ok else 1)
    if not os.path.isdir(KAFKA_HOME):
        sys.exit(f"Kafka not found in {KAFKA_HOME} (variable KAFKA_HOME); see the docstring of this file")
    os.makedirs(DATA, exist_ok=True)
    props = os.path.join(DATA, "server.properties")
    with open(props, "w", encoding="utf-8") as f:
        f.write(PROPERTIES)
    if not os.path.isfile(os.path.join(DATA, "logs", "meta.properties")):        # first start: format the storage
        subprocess.run(java("kafka.tools.StorageTool", "format", "-t", cluster_id(), "-c", props, heap="-Xmx256M"),
                       check=True)
    p = subprocess.Popen(java("kafka.Kafka", props))
    t0 = time.time()
    while not answers() and p.poll() is None and time.time() - t0 < 120:
        time.sleep(1)
    print(f"Kafka broker ready on 127.0.0.1:{PORT} (data: {DATA})" if answers() else "Kafka did not start", flush=True)
    try:
        p.wait()
    except KeyboardInterrupt:
        p.terminate()
        p.wait(30)


if __name__ == "__main__":
    main()

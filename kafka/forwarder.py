"""The values of the devices of a twin, published to Kafka as the EPICS forwarder of ESS does: one f144 message (ESS
flatbuffer schema "log data") per device and per change, with the time of the change. The ESS file-writer
(kafka-to-nexus) reads them to fill the NXlog groups of the file (filewriter/README.md, step 2).

    from forwarder import Forwarder
    f = Forwarder("127.0.0.1:9092", topic="odin_devices", prefix="odin")
    f.publish(odin.status(), odin.devices)        # all the devices now; then after each move

Source names: "<prefix>:<device>" (at ESS: the EPICS PV names). Numbers are sent as float64; a device with a list of
choices (e.g. the shutter "open"/"closed", the chopper mode) as the index of its value in the list (int32), as an EPICS
enum; values that are neither (text) are not sent (f144 has no strings).
Used by twin_server.py when TWIN_FORWARD=1 (broker: TWIN_KAFKA).
"""
import time

import numpy as np

try:
    from confluent_kafka import Producer
    from streaming_data_types import serialise_f144
except ImportError:                                  # Kafka is optional: the twin works without it
    Producer = serialise_f144 = None


def available():
    return Producer is not None


def encode(value, choices=None):
    """The value as f144 sends it (numpy scalar), or None if it cannot be sent."""
    if isinstance(value, (bool, np.bool_)):
        return np.int32(int(value))
    if isinstance(value, (int, float, np.integer, np.floating)):
        return np.float64(value)
    if choices:
        lst = [c if not isinstance(c, (list, tuple)) else c[0] for c in choices]
        if value in lst:
            return np.int32(lst.index(value))
    return None


class Forwarder:
    def __init__(self, brokers="127.0.0.1:9092", topic="devices", prefix="twin"):
        if Producer is None:
            raise RuntimeError("the forwarder needs confluent-kafka and ess-streaming-data-types")
        self.topic, self.prefix = topic, prefix
        self.producer = Producer({"bootstrap.servers": brokers, "linger.ms": 5})
        self.last = {}

    def publish(self, values, devices=None, only_changes=False, t_ns=None):
        """Publishes {device: value}; devices: {name: object with .choices} (or None). Returns the number sent."""
        t_ns = time.time_ns() if t_ns is None else t_ns
        sent = 0
        for name, value in values.items():
            choices = getattr((devices or {}).get(name), "choices", None)
            v = encode(value, choices)
            if v is None or (only_changes and self.last.get(name) == v):
                continue
            self.producer.produce(self.topic, serialise_f144(f"{self.prefix}:{name}", v, t_ns), timestamp=t_ns // 1_000_000)
            self.last[name] = v
            sent += 1
        self.producer.flush(10)
        return sent

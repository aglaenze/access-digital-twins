"""Streams the neutrons of a twin measurement to Kafka, pulse by pulse and in real time, as the detector of an ESS
instrument does: one ev44 message (ESS flatbuffer schema "event data") per source pulse, with the time of the pulse,
and for each neutron its arrival time after the pulse and its pixel.

Used by the twin server (twin_server.py, count with "stream": true): after the twin has computed a measurement, its
events are replayed at 14 pulses per second, so that just-bin-it histograms them and NICOS shows the image and the
spectrum filling up during the count, as on the real instrument.

    from streamer import Streamer
    s = Streamer("127.0.0.1:9092", topic="odin_detector", source="odin_timepix3")
    s.stream(pulses, start_ns)      # pulses: list of (offset of the pulse [ns], times of flight [ns], pixel ids)
"""
import time

import numpy as np

try:
    from confluent_kafka import Producer
    from streaming_data_types import serialise_ev44
except ImportError:                                  # Kafka is optional: the twin works without it
    Producer = serialise_ev44 = None


def available():
    return Producer is not None


class Streamer:
    def __init__(self, brokers="127.0.0.1:9092", topic="detector", source="detector"):
        if Producer is None:
            raise RuntimeError("Kafka streaming needs confluent-kafka and ess-streaming-data-types")
        self.topic, self.source = topic, source
        self.producer = Producer({"bootstrap.servers": brokers, "message.max.bytes": 16_000_000,
                                  "queue.buffering.max.kbytes": 1_048_576, "linger.ms": 5})
        self.message_id = 0

    def stream(self, pulses, start_ns=None, speed=1.0, stop=None, tail_s=1.5):
        """Publishes the pulses at their times: pulse k at start_ns + offset_k / speed (wall clock). Returns the number
        of events sent. stop: optional threading.Event to interrupt. tail_s: then empty pulses for this time, as a
        detector streams all the time (a histogrammer sees that its time window is over)."""
        start_ns = time.time_ns() if start_ns is None else start_ns
        sent = 0
        for offset, tof, pix in pulses:
            t_pulse = start_ns + int(offset / speed)
            wait = (t_pulse - time.time_ns()) / 1e9
            if wait > 0:
                time.sleep(wait)
            if stop is not None and stop.is_set():
                break
            self.message_id += 1
            msg = serialise_ev44(self.source, self.message_id, np.array([t_pulse], dtype=np.int64),
                                 np.array([0], dtype=np.int32), np.asarray(tof, dtype=np.int32),
                                 np.asarray(pix, dtype=np.int32))
            self.producer.produce(self.topic, msg, timestamp=t_pulse // 1_000_000)
            self.producer.poll(0)
            sent += len(pix)
        if pulses and tail_s > 0 and not (stop is not None and stop.is_set()):
            last = start_ns + int(pulses[-1][0] / speed)
            empty = np.zeros(0, dtype=np.int32)
            for k in range(1, int(tail_s * 14) + 1):
                t_pulse = last + int(k * 1e9 / 14)
                time.sleep(max(0.0, (t_pulse - time.time_ns()) / 1e9))
                self.message_id += 1
                self.producer.produce(self.topic, serialise_ev44(self.source, self.message_id,
                                      np.array([t_pulse], dtype=np.int64), np.array([0], dtype=np.int32), empty, empty),
                                      timestamp=t_pulse // 1_000_000)
                self.producer.poll(0)
        self.producer.flush(30)
        return sent

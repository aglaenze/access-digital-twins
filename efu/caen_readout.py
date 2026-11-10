"""Raw readout of LoKI's detector (CAEN electronics), as the ESS Event Formation Unit (EFU, program loki) reads it.

LoKI's detector is made of tubes, each of 7 thin straws of helium-3, in 4 layers. A neutron absorbed in a straw makes
a charge, read at both ends of the tube through a resistive network. The CAEN digitizers send four amplitudes A, B, C,
D per neutron, and the EFU finds by **charge division**:

* the straw: (B + D) / (A + B + C + D), cut into 7 intervals of the calibration file;
* the position along the straw: (A + B) / (A + B + C + D), corrected by the calibration polynomial of that straw and
  cut into 512 positions.

Each neutron is one 24-byte readout (fiber, front-end board FEN, group, time on the ESS clock of 88.0525 MHz, the
four amplitudes), in UDP packets that start with the ESS readout header (time of the pulse and of the previous one).
The EFU publishes one neutron per readout to Kafka (ev44, source "caen"): there is no clustering, unlike ODIN's camera.
Its pixel numbers are those of the real LoKI file (configs/loki.json). At ESS, each bank has its own EFU and topic
(loki_detector_bank0 ... bank8), as in the real file.

The twin does the reverse: each neutron of its file becomes the readout of its pixel, with amplitudes whose charge
division gives the right straw and position, and its time on the ESS clock. The formats are those of the EFU's sources
(src/common/readout/ess/Parser.h, src/modules/caen/readout/DataParser.h, src/modules/caen/geometry/CDCalibration.cpp,
src/modules/loki/geometry/LokiGeometry.cpp and LokiConfig.h, src/common/time/ESSTime.h;
ess-dmsc/event-formation-unit).

    Readout().pulse(t0, eto, ids)    UDP payloads of one pulse, bank by bank
    expected(t0, eto)                (pulse time, times of flight) the EFU must publish (same pixel ids)
    match(...)                       compares what the EFU published with what was sent
    null_calibration(path)           the calibration file of an ideal charge division
                                     (python efu/caen_readout.py --calibration PATH)
    decode(payloads)                 the EFU's computation in Python (to check this module without the EFU)
"""
import json
import os
import struct

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "configs", "loki.json")
LOKI = 0x30                       # detector type of LoKI in the ESS readout header (common/types/DetectorType.h)
HEADER = struct.Struct("<BBIHBBIIIIIH")    # ESS readout header, version 1 (32 bytes)
READOUT = struct.Struct("<BBHIIBBHhhhh")   # CAEN readout (24 bytes)
READOUT_DTYPE = np.dtype([("fiber", "u1"), ("fen", "u1"), ("length", "<u2"), ("high", "<u4"), ("low", "<u4"),
                          ("flags", "u1"), ("group", "u1"), ("unused", "<u2"),
                          ("a", "<i2"), ("b", "<i2"), ("c", "<i2"), ("d", "<i2")])
UDP_MAX = 8972                    # the EFU's largest UDP payload (MaxUdpDataSize)
PER_PACKET = (UDP_MAX - HEADER.size) // READOUT.size   # 372 readouts per packet
CLOCK_HZ = 88_052_500             # ESS clock: time = high (s) + low ticks of 1/88052500 s
TICK = 1e9 / CLOCK_HZ             # as ESSTime::ESSClockTick (double)
PERIOD_NS = 71_428_571            # 14 Hz
STRAWS = 7
# straw intervals of (B + D) / sum, as the null calibration of the EFU's sources (lokinullcalib.json)
INTERVALS = [[0.0, 0.143], [0.144, 0.286], [0.287, 0.429], [0.43, 0.571], [0.572, 0.714], [0.715, 0.857],
             [0.858, 1.0]]
AMP_SUM = 511 * 40                # A + B + C + D: (A + B) / sum = position / 511 exactly


def _config():
    with open(CONFIG) as f:
        c = json.load(f)
    banks = sorted(c["Banks"], key=lambda b: b["Bank"])
    return c["Resolution"], np.array([b["YOffset"] for b in banks]), np.array([b["GroupsN"] for b in banks]), \
        c["Config"]


RESOLUTION, Y_OFFSET, TUBES, RINGS = _config()
N_BANKS = len(Y_OFFSET)
N_PIXELS = RESOLUTION * int(Y_OFFSET[-1] + 4 * STRAWS * TUBES[-1])    # 3211264, as the real file
GROUPS = int(4 * TUBES.sum())     # tubes of the detector (896): one calibration group each


def bank_of(ids):
    """Bank (0..8) of each pixel id (1-based, numbering of the real LoKI file)."""
    y = (np.asarray(ids, np.int64) - 1) // RESOLUTION
    return np.searchsorted(Y_OFFSET, y, side="right") - 1


def readouts(ids):
    """Readout fields of the pixels: bank, fiber, FEN, group, amplitudes A, B, C, D (LokiConfig::getY,
    getGlobalGroup and LokiGeometry::calcUnitAndPos read backward)."""
    i = np.asarray(ids, np.int64) - 1
    pos, y = i % RESOLUTION, i // RESOLUTION
    bank = np.searchsorted(Y_OFFSET, y, side="right") - 1
    r = y - Y_OFFSET[bank]
    per_layer = TUBES[bank] * STRAWS
    layer, tube, straw = r // per_layer, (r % per_layer) // STRAWS, r % STRAWS
    fen_global, group = tube // 2, layer + 4 * (tube % 2)
    ring = np.full(len(i), -1)
    fen = np.zeros(len(i), np.int64)
    for c in RINGS:
        sel = (bank == c["Bank"]) & (fen_global >= c["FENOffset"]) & (fen_global < c["FENOffset"] + c["FENs"])
        ring[sel], fen[sel] = c["Ring"], fen_global[sel] - c["FENOffset"]
    assert np.all(ring >= 0), "pixel outside the rings of configs/loki.json"
    p = pos * (AMP_SUM // (RESOLUTION - 1))                                  # A + B
    centers = np.array([(lo + hi) / 2 for lo, hi in INTERVALS])
    q = np.round(centers[straw] * AMP_SUM).astype(np.int64)                  # B + D
    b = np.minimum(p, q)
    a, d = p - b, q - b
    c = AMP_SUM - a - b - d
    return bank, 2 * ring, fen, group, a, b, c, d


def ess_time(t_ns):
    """Epoch ns -> (seconds, ticks of the ESS clock), the nearest tick."""
    t = np.asarray(t_ns, np.int64)
    high, low = t // 10**9, np.round((t % 10**9) / TICK).astype(np.int64)
    carry = low >= CLOCK_HZ
    return high + carry, np.where(carry, 0, low)


def to_ns(high, low):
    """The EFU's conversion (ESSTime::toNS): high x 1e9 + (uint64)(low x tick)."""
    return np.asarray(high, np.int64) * 10**9 + (np.asarray(low, np.int64) * TICK).astype(np.int64)


def expected(t0, eto):
    """(pulse time, time of flight) the EFU publishes for neutrons of pulse t0 (epoch ns) arriving eto ns after it:
    both times rounded to a tick of the ESS clock (11.4 ns), then converted as the EFU does. The pixel id is the same."""
    t0, eto = np.asarray(t0, np.int64), np.asarray(eto, np.int64)
    p = to_ns(*ess_time(t0))
    return p, to_ns(*ess_time(t0 + eto)) - p


def header(length, seq, t0, prev):
    hp, lp = (int(v) for v in ess_time(t0))
    hq, lq = (int(v) for v in ess_time(prev))
    return HEADER.pack(0, 1, 0x535345 | (LOKI << 24), length, 0, 0, hp, lp, hq, lq, seq & 0xFFFFFFFF, 0)


class Readout:
    """LoKI's readout system, pulse after pulse: one sequence number per bank (its EFU counts the packets)."""

    def __init__(self):
        self.seq = [0] * N_BANKS

    def pulse(self, t0, eto, ids):
        """UDP payloads of one pulse (time t0, epoch ns): {bank: [payloads]}, the neutrons (eto ns after the pulse,
        pixel ids) of each bank by time, PER_PACKET readouts per packet."""
        t0 = int(t0)
        e, d = np.asarray(eto, np.int64), np.asarray(ids, np.int64)
        o = np.argsort(e, kind="stable")
        e, d = e[o], d[o]
        bank, fiber, fen, group, a, b, c, dd = readouts(d)
        high, low = ess_time(t0 + e)
        out = {}
        for k in np.unique(bank):
            sel = np.nonzero(bank == k)[0]
            r = np.zeros(len(sel), READOUT_DTYPE)
            r["fiber"], r["fen"], r["length"], r["high"], r["low"] = fiber[sel], fen[sel], READOUT.size, \
                high[sel], low[sel]
            r["group"], r["a"], r["b"], r["c"], r["d"] = group[sel], a[sel], b[sel], c[sel], dd[sel]
            out[int(k)] = []
            for j in range(0, len(r), PER_PACKET):
                body = r[j:j + PER_PACKET].tobytes()
                out[int(k)].append(header(HEADER.size + len(body), self.seq[k], t0, t0 - PERIOD_NS) + body)
                self.seq[k] += 1
        return out


def packets(etz, eto, ids, counts, readout=None):
    """UDP payloads of a measurement, {bank: [payloads]}: for each pulse k (time etz[k], epoch ns; counts[k]
    neutrons, in eto and ids in the order of the pulses), Readout.pulse."""
    readout = readout or Readout()
    out, start = {}, 0
    for t0, n in zip(np.asarray(etz, np.int64), counts):
        for k, p in readout.pulse(t0, eto[start:start + n], ids[start:start + n]).items():
            out.setdefault(k, []).extend(p)
        start += n
    return out


def null_calibration(path):
    """Writes the calibration file of an ideal charge division (no correction): one group per tube, the straw
    intervals of INTERVALS, polynomials 0 (as nullcalib.py of the EFU's sources)."""
    groups = [{"groupindex": g, "intervals": INTERVALS, "polynomials": [[0.0] * 4] * STRAWS} for g in range(GROUPS)]
    with open(path, "w") as f:
        json.dump({"Calibration": {"version": 0, "date": "2026-11-10", "info": "ideal charge division (twin)",
                                   "instrument": "loki", "groups": GROUPS, "groupsize": STRAWS,
                                   "Parameters": groups}}, f)
    return path


def decode(payloads):
    """What the EFU makes of the payloads of one bank (its computation, in Python): [(pulse time ns, pixel ids,
    tofs)] per packet."""
    out = []
    for p in payloads:
        h = HEADER.unpack_from(p)
        assert h[0] == 0 and h[1] == 1 and h[2] == 0x535345 | (LOKI << 24) and h[3] == len(p)
        pulse = int(to_ns(h[6], h[7]))
        r = np.frombuffer(p, READOUT_DTYPE, offset=HEADER.size)
        assert np.all(r["length"] == READOUT.size)
        a, b, c, d = (r[k].astype(np.int64) for k in "abcd")
        s = a + b + c + d
        uncorr, straw_pos = 1.0 * (a + b) / s, 1.0 * (b + d) / s
        unit = np.full(len(r), -1)
        for k, (lo, hi) in enumerate(INTERVALS):
            unit[(unit < 0) & (straw_pos >= lo) & (straw_pos <= hi)] = k
        assert np.all(unit >= 0)
        ring, fen, group = r["fiber"].astype(np.int64) // 2, r["fen"].astype(np.int64), r["group"].astype(np.int64)
        y = np.zeros(len(r), np.int64)
        for cfg in RINGS:
            sel = ring == cfg["Ring"]
            bank = cfg["Bank"]
            y[sel] = (Y_OFFSET[bank] + (group[sel] % 4) * TUBES[bank] * STRAWS + (cfg["FENOffset"] + fen[sel]) * 14
                      + 7 * (group[sel] // 4) + unit[sel])
        pos = np.floor(uncorr * (RESOLUTION - 1) + 0.5).astype(np.int64)     # C++ round (half away from zero)
        out.append((pulse, 1 + pos + RESOLUTION * y, to_ns(r["high"], r["low"]) - pulse))
    return out


def match(t0, eto, ids, t0_efu, tof_efu, ids_efu, tolerance_ns=10_000):
    """Compares neutrons sent (pulse time t0, eto, ids; one entry per neutron) with the neutrons the EFU published
    (pulse time, time of flight, pixel id). Each neutron sent must come back once (no clustering), with the same pixel
    and the time of flight of expected(); the EFU's pulse times are matched to the nearest pulse sent, within
    tolerance_ns. Returns (found exactly, sent, published, pulses of the EFU matching no pulse sent)."""
    t0, t0_efu = np.asarray(t0, np.int64), np.asarray(t0_efu, np.int64)
    pulses = np.unique(t0)
    j = np.clip(np.searchsorted(pulses, t0_efu), 1, max(len(pulses) - 1, 1)) if len(pulses) > 1 else \
        np.zeros(len(t0_efu), np.int64)
    if len(pulses) > 1:
        j = np.where(np.abs(pulses[j - 1] - t0_efu) <= np.abs(pulses[j] - t0_efu), j - 1, j)
    near = np.abs(pulses[j] - t0_efu) <= tolerance_ns if len(pulses) else np.zeros(len(t0_efu), bool)
    key_sent = (np.asarray(ids, np.int64) << 31) | expected(t0, eto)[1]      # pixel id (22 bits), tof (< 2^31 ns)
    key_got = (np.asarray(ids_efu, np.int64) << 31) | np.asarray(tof_efu, np.int64)
    o_s, o_g = np.argsort(t0, kind="stable"), np.argsort(np.where(near, j, -1), kind="stable")
    k_s, k_g = t0[o_s], np.where(near, j, -1)[o_g]
    found = 0
    for k, p in enumerate(pulses):
        a, b = np.searchsorted(k_s, p), np.searchsorted(k_s, p, side="right")
        c, d = np.searchsorted(k_g, k), np.searchsorted(k_g, k, side="right")
        us, cs = np.unique(key_sent[o_s[a:b]], return_counts=True)
        ug, cg = np.unique(key_got[o_g[c:d]], return_counts=True)
        _, i_s, i_g = np.intersect1d(us, ug, assume_unique=True, return_indices=True)
        found += int(np.minimum(cs[i_s], cg[i_g]).sum())
    return found, len(t0), len(t0_efu), int(len(np.unique(t0_efu[~near])))


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--calibration":       # python caen_readout.py --calibration PATH
        print("calibration written:", null_calibration(sys.argv[2]))
        sys.exit(0)
    # self-check without the EFU: every pixel of the 9 banks, then random neutrons -> packets -> the EFU's computation
    every = np.arange(1, N_PIXELS + 1)
    pk = Readout().pulse(1_800_000_000_000_000_000, np.zeros(N_PIXELS, np.int64), every)
    back = np.concatenate([np.concatenate([g[1] for g in decode(pk[k])]) for k in sorted(pk)])
    print(f"{N_PIXELS} pixels in {sum(len(v) for v in pk.values())} packets: "
          f"{np.sum(np.sort(back) != every)} come back with another pixel id")
    assert np.array_equal(np.sort(back), every)
    rng = np.random.default_rng(1)
    n = 300_000
    counts = rng.multinomial(n, np.ones(40) / 40)
    etz = 1_800_000_000_000_000_000 + np.round(np.arange(40) * 1e9 / 14).astype(np.int64)
    eto = rng.integers(0, 2 * PERIOD_NS, n)          # LoKI's slow neutrons can arrive after the next pulse
    ids = rng.integers(1, N_PIXELS + 1, n)
    eto[:4] = [0, 1, PERIOD_NS, 999_999_999]
    pk = packets(etz, eto, ids, counts)
    t0_got, id_got, tof_got = [], [], []
    for k in pk:
        for t, g, f in decode(pk[k]):
            t0_got.append(np.full(len(g), t)), id_got.append(g), tof_got.append(f)
    t0_got, id_got, tof_got = (np.concatenate(v) for v in (t0_got, id_got, tof_got))
    t0 = np.repeat(etz, counts)
    res = match(t0, eto, ids, t0_got, tof_got, id_got)
    xt, xtof = expected(t0, eto)
    print(f"match: {res[0]} of {res[1]} found, {res[2]} published, {res[3]} pulses unmatched; "
          f"tof - eto in [{(xtof - eto).min()}, {(xtof - eto).max()}] ns, pulse times moved by up to "
          f"{np.abs(xt - t0).max()} ns")
    assert res[0] == res[1] == res[2] == n and res[3] == 0

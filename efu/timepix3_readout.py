"""Raw readout of ODIN's Timepix3 camera, as the ESS Event Formation Unit (EFU, module timepix3) reads it.

At ESS the camera does not send neutrons: it sends the pixels that saw light (64-bit "pixel" words: position on the
256 x 256 chip, time of arrival, time over threshold ToT), a 64-bit "TDC" word when it receives the trigger of a
proton pulse, and the timing system (EVR) sends the time of each pulse (24-byte packet). The EFU pairs each TDC
with its EVR packet, groups the pixels into clusters (close in time and space: one neutron makes a flash of light seen
by several pixels), and publishes one neutron per cluster to Kafka (ev44): its time is that of the first pixel, its
position the ToT-weighted center of the cluster, scaled up 16 times (4096 x 4096 pixels).

The twin does the reverse: each neutron of its file becomes a cluster of 2 x 2 chip pixels at the neutron's time,
whose ToT weights put the center in the right sub-pixel. The formats are those of the EFU's sources
(src/modules/timepix3: readout/DataParser.h, dto/TimepixDataTypes.h, handlers/PixelEventHandler.cpp,
geometry/Timepix3Geometry.h; ess-dmsc/event-formation-unit).

    packets(etz, eto, ids, counts)   UDP payloads of a measurement, pulse by pulse
    expected(eto, ids)               (pixel ids, times of flight) the EFU must publish for these neutrons
    send(payloads, host, port)       sends them
    decode(payloads)                 the EFU's computation in Python (to check this module without the EFU)
"""
import socket
import struct
import time

import numpy as np

CHIP = 256                      # pixels per side of the Timepix3 chip
SCALE = 16                      # ScaleUpFactor of the EFU configuration (configs/odin_timepix3.json)
NPIX = CHIP * SCALE             # 4096: pixels per side of the real ODIN file
PIXEL_MAX_NS = 26843545600      # the pixel clock (409600 ns x 2^16) wraps after 26.8 s
PULSE_HZ = 14.0
UDP_MAX = 8952                  # bytes per UDP packet (as the EFU's generator)
EVENTS_PER_PACKET = UDP_MAX // 32   # whole clusters: 4 words of 8 bytes per neutron (never 24 bytes: an EVR packet)

PIXEL, TDC, TDC1_RISING, EVR = 0xB, 0x6, 0xF, 1


def _axis(v):
    """Chip pixels (lo, lo+1) and their weights for the scaled-up coordinate v (0..4095): the weighted center
    lo + w_hi/(w_lo+w_hi) falls in the middle of the sub-pixel v / 16 (EFU: pixel = floor(16 x center)). The last chip
    pixel (255) has no neighbor above: its sub-pixels all become 4080 (as for the real camera)."""
    p, m = v // SCALE, v % SCALE
    edge = p >= CHIP - 1
    lo = np.where(edge, CHIP - 2, p)
    w_lo = np.where(edge, 0, 31 - 2 * m)
    w_hi = np.where(edge, 31, 2 * m + 1)
    return lo, w_lo, w_hi


def expected(eto, ids):
    """(pixel ids, times of flight in ns) the EFU publishes for neutrons (eto in ns, ids 1-based, 1 + x + 4096 y):
    positions in the last 15 sub-pixels of each axis move to 4080; times are coded to 1.5625 ns and read back
    rounded down, i.e. eto or eto + 1 (computed exactly as the EFU does, by the same coding as packets())."""
    i = np.asarray(ids, np.int64) - 1
    x, y = np.minimum(i % NPIX, NPIX - 16), np.minimum(i // NPIX, NPIX - 16)
    c, f = _time_code(np.asarray(eto, np.int64))
    tof = np.floor(c * 25 - f * 1.5625).astype(np.int64)
    return 1 + x + NPIX * y, tof


def match(t0, eto, ids, t0_efu, tof_efu, ids_efu, tolerance_ns=10_000):
    """Compares neutrons sent (pulse time t0, eto, ids; one entry per neutron) with the neutrons the EFU published
    (pulse time, time of flight, pixel id). The EFU's pulse time is computed in floating point (about 256 ns lost): it
    is matched to the nearest pulse sent, within tolerance_ns. The neutrons sent become what the EFU must publish
    (expected()), identical ones counted once (one flash). Returns (found exactly, expected, published, pulses of the
    EFU matching no pulse sent)."""
    t0, t0_efu = np.asarray(t0, np.int64), np.asarray(t0_efu, np.int64)
    pulses = np.unique(t0)
    j = np.clip(np.searchsorted(pulses, t0_efu), 1, max(len(pulses) - 1, 1)) if len(pulses) > 1 else \
        np.zeros(len(t0_efu), np.int64)
    if len(pulses) > 1:
        j = np.where(np.abs(pulses[j - 1] - t0_efu) <= np.abs(pulses[j] - t0_efu), j - 1, j)
    near = np.abs(pulses[j] - t0_efu) <= tolerance_ns if len(pulses) else np.zeros(len(t0_efu), bool)
    xid, xtof = expected(eto, ids)
    key_sent = (xid << 27) | xtof                       # pixel id (25 bits) and time of flight (< 2^27 ns)
    key_got = (np.asarray(ids_efu, np.int64) << 27) | np.asarray(tof_efu, np.int64)
    o_s, o_g = np.argsort(t0, kind="stable"), np.argsort(np.where(near, j, -1), kind="stable")
    k_s, k_g = t0[o_s], np.where(near, j, -1)[o_g]
    found = n_sent = 0
    for k, p in enumerate(pulses):
        a, b = np.searchsorted(k_s, p), np.searchsorted(k_s, p, side="right")
        c, d = np.searchsorted(k_g, k), np.searchsorted(k_g, k, side="right")
        s = np.unique(key_sent[o_s[a:b]])
        n_sent += len(s)
        found += int(np.isin(s, key_got[o_g[c:d]]).sum())
    return found, n_sent, len(t0_efu), int(len(np.unique(t0_efu[~near])))


def _time_code(t_ns):
    """Pixel clock time t (integer ns) -> (coarse 25 ns ticks c, fine 1.5625 ns ticks f): time = 25 c - 1.5625 f,
    the smallest such time >= t (the EFU then rounds it down: t or t + 1)."""
    c = -(-t_ns // 25)
    f = ((c * 25 - t_ns) * 16) // 25
    return c, f


def pixel_words(x, y, t_ns, tot):
    """64-bit pixel words: chip pixel (x, y), pixel clock time t_ns (< PIXEL_MAX_NS), ToT (0..1023)."""
    x, y, tot = (np.asarray(a, np.uint64) for a in (x, y, tot))
    c, f = _time_code(np.asarray(t_ns, np.int64))
    c = (c % (PIXEL_MAX_NS // 25)).astype(np.uint64)
    spidr, toa = c >> np.uint64(14), c & np.uint64(0x3FFF)
    dcol, spix = x & ~np.uint64(1), y & ~np.uint64(3)
    pix = ((x & np.uint64(1)) << np.uint64(2)) | (y & np.uint64(3))
    u = np.uint64
    return ((u(PIXEL) << u(60)) | (dcol << u(52)) | (spix << u(45)) | (pix << u(44)) | (toa << u(30))
            | (tot << u(20)) | (f.astype(np.uint64) << u(16)) | spidr)


def tdc_word(counter, t_ns):
    """64-bit TDC word (TDC1 rising edge): trigger counter (12 bits), time t_ns (a multiple of 25 ns: 3.125 ns ticks)."""
    return np.uint64((TDC << 60) | (TDC1_RISING << 56) | ((counter % 4096) << 44) | ((t_ns * 8 // 25) << 9))


def evr_packet(counter, pulse_ns, prev_ns):
    """24-byte EVR packet: type 1, counter, time of the pulse and of the previous one (s, ns)."""
    return struct.pack("<BBHIIIII", EVR, 0, 0, counter, pulse_ns // 10**9, pulse_ns % 10**9,
                       prev_ns // 10**9, prev_ns % 10**9)


def cluster_words(eto, ids, t_tdc):
    """Pixel words of the neutrons of one pulse (eto ns after the pulse, whose TDC came at pixel clock time t_tdc):
    4 words per neutron, in the order of the neutrons."""
    i = np.asarray(ids, np.int64) - 1
    xl, wx0, wx1 = _axis(i % NPIX)
    yl, wy0, wy1 = _axis(i // NPIX)
    t = (t_tdc + np.asarray(eto, np.int64)) % PIXEL_MAX_NS
    hits = [(xl + a, yl + b, (wx1 if a else wx0) * (wy1 if b else wy0)) for a in (0, 1) for b in (0, 1)]
    w = np.stack([pixel_words(hx, hy, t, tot) for hx, hy, tot in hits], axis=1)
    return w.reshape(-1)


class Camera:
    """The camera and the timing system of the instrument, pulse after pulse: the pulse counter (EVR, TDC) and the
    pixel clock go on from one measurement to the next, as on the instrument (the EFU drops a pulse whose counter
    repeats the last one). The TDC of the k-th pulse comes at pixel clock time 25 ns x round(k / 14 Hz / 25 ns),
    modulo the wrap of the clock."""

    def __init__(self):
        self.k, self.last = 0, None

    def pulse(self, t0, eto, ids):
        """UDP payloads of one pulse (time t0, epoch ns): its EVR packet, its TDC word, then its neutrons (eto ns after
        the pulse, pixel ids) in packets of whole clusters, by time."""
        t0 = int(t0)
        prev = self.last if self.last is not None else t0 - int(round(1e9 / PULSE_HZ))
        self.k += 1
        t_tdc = (25 * int(round((self.k - 1) * 1e9 / PULSE_HZ / 25))) % PIXEL_MAX_NS
        out = [evr_packet(self.k % 2**32, t0, prev), np.array([tdc_word(self.k, t_tdc)], np.uint64).tobytes()]
        self.last = t0
        e, d = np.asarray(eto, np.int64), np.asarray(ids, np.int64)
        o = np.argsort(e, kind="stable")
        e, d = e[o], d[o]
        for j in range(0, len(e), EVENTS_PER_PACKET):
            out.append(cluster_words(e[j:j + EVENTS_PER_PACKET], d[j:j + EVENTS_PER_PACKET], t_tdc).tobytes())
        return out


def packets(etz, eto, ids, counts, camera=None):
    """UDP payloads of a measurement: for each pulse k (time etz[k], epoch ns; counts[k] neutrons, in eto and ids in
    the order of the pulses), Camera.pulse."""
    camera = camera or Camera()
    out, start = [], 0
    for t0, n in zip(np.asarray(etz, np.int64), counts):
        out += camera.pulse(t0, eto[start:start + n], ids[start:start + n])
        start += n
    return out


def send(payloads, host="127.0.0.1", port=9000, pause_s=100e-6):
    """Sends the payloads over UDP, with a short pause between packets (the EFU reads them one by one)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 << 20)
    try:
        for p in payloads:
            s.sendto(p, (host, port))
            if pause_s:
                time.sleep(pause_s)
    finally:
        s.close()


def decode(payloads, min_hits=4, max_gap=1):
    """What the EFU makes of the payloads (its computation, in Python, for neutrons sent by this module, taken as one
    cluster per 4 hits: same time, pixels at most max_gap apart): [(pulse time ns, pixel ids, tofs)] per pulse."""
    out, pulse, tdc = [], None, None
    for p in payloads:
        if len(p) == 24 and p[0] == EVR:
            _, _, _, _, s, ns, _, _ = struct.unpack("<BBHIIIII", p)
            pulse = s * 10**9 + ns
            out.append((pulse, [], []))
            continue
        w = np.frombuffer(p, np.uint64)
        typ = w >> np.uint64(60)
        for t in w[typ == TDC]:
            stamp = int((t >> np.uint64(9)) & np.uint64((1 << 35) - 1))
            tdc = int(3.125 * stamp) % PIXEL_MAX_NS
        px = w[typ == PIXEL]
        if not len(px):
            continue
        g = lambda mask, off: ((px & np.uint64(mask)) >> np.uint64(off)).astype(np.int64)   # noqa: E731
        dcol, spix, pix = g(0x0FE0000000000000, 52), g(0x001F800000000000, 45), g(0x0000700000000000, 44)
        toa, tot, ftoa, spidr = g(0x00000FFFC0000000, 30), g(0x000000003FF00000, 20), g(0xF0000, 16), g(0xFFFF, 0)
        x, y = dcol + pix // 4, spix + (pix & 3)
        clock = np.floor(409600 * spidr + 25 * toa - 1.5625 * ftoa).astype(np.int64)
        tof = np.where(clock >= tdc, clock - tdc, PIXEL_MAX_NS - tdc + clock)
        for k in range(0, len(px), 4):          # one cluster per 4 hits (as sent; the EFU finds them itself)
            sl = slice(k, k + 4)
            assert np.all(np.abs(np.diff(x[sl])) <= max_gap) and len(set(tof[sl])) == 1 and 4 >= min_hits
            wsum = tot[sl].sum()
            cx, cy = (x[sl] * tot[sl]).sum() / wsum, (y[sl] * tot[sl]).sum() / wsum
            out[-1][1].append(1 + int(cx * SCALE) + NPIX * int(cy * SCALE))
            out[-1][2].append(int(tof[sl].min()))
    return out


if __name__ == "__main__":
    # self-check without the EFU: random neutrons -> packets -> the EFU's computation == expected()
    rng = np.random.default_rng(1)
    n = 200_000
    counts = rng.multinomial(n, np.ones(40) / 40)
    etz = 1_800_000_000_000_000_000 + np.round(np.arange(40) * 1e9 / PULSE_HZ).astype(np.int64)
    eto = rng.integers(0, int(1e9 / PULSE_HZ), n)
    ids = rng.integers(1, NPIX * NPIX + 1, n)
    ids[:8] = [1, NPIX, NPIX * NPIX, NPIX * (NPIX - 1) + 1, 4081, 4080, 17, 16]
    eto[:8] = [0, 1, 24, 25, 26, 71428570, 12, 13]
    pk = packets(etz, eto, ids, counts)
    got = decode(pk)
    start, bad = 0, 0
    for k, (t0, gid, gtof) in enumerate(got):
        sl = slice(start, start + counts[k])
        o = np.argsort(eto[sl], kind="stable")
        eid, etof = expected(eto[sl][o], ids[sl][o])
        bad += int(t0 != etz[k]) + int(np.any(np.array(gid) != eid)) + int(np.any(np.array(gtof) != etof))
        start += counts[k]
    d = expected(eto, ids)[1] - eto
    print(f"{len(pk)} packets, {n} neutrons, {len(got)} pulses; mismatches: {bad}; "
          f"tof - eto in [{d.min()}, {d.max()}]; ids moved by the edge: {np.sum(expected(eto, ids)[0] != ids)}")
    assert bad == 0 and d.min() >= 0 and d.max() <= 1
    # match(): the EFU's pulse times in floating point (seconds x 1e9 + ns, as dto/TimepixDataTypes.h)
    t_efu = np.concatenate([[int(float(t // 10**9) * 1e9 + t % 10**9)] * len(g) for t, g, _ in got])
    res = match(np.repeat(etz, counts), eto, ids, t_efu, np.concatenate([g[2] for g in got]),
                np.concatenate([g[1] for g in got]))
    print(f"match: {res[0]} of {res[1]} found, {res[2]} published, {res[3]} pulses unmatched; "
          f"pulse times moved by up to {np.max(np.abs(t_efu - np.repeat(etz, counts)))} ns")
    assert res[0] == res[1] == n and res[3] == 0

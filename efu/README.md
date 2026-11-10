# Event Formation Unit (EFU) of ESS with the twin

At ESS a detector does not send neutrons. It sends its **raw readout** over UDP, and the **Event Formation Unit**
(EFU, https://github.com/ess-dmsc/event-formation-unit) turns that readout into neutron events. The EFU publishes them
to Kafka as ev44 messages, where the file-writer and the live data reduction read them. Without the EFU, the twin
publishes its neutrons to Kafka itself.

## ODIN: Timepix3 camera

| At ESS | In the twin |
|---|---|
| The Timepix3 camera sees the flash of light that a neutron makes in the scintillator. It sends 64-bit **pixel words**: position on the 256 × 256 chip, time of arrival, time over threshold (ToT). For each proton pulse it also sends a **TDC word** when the pulse trigger arrives. | `timepix3_readout.py` turns each neutron of the twin's file into a cluster of 2 × 2 chip pixels, all hit at the neutron's time. The ToT weights put the ToT-weighted center in the right sub-pixel. It also sends one TDC word per pulse. |
| The timing system (EVR) sends the time of each pulse in a 24-byte packet. | The same packet, with the time of the twin's pulse. |
| The EFU (`timepix3` program):<br>• pairs each TDC word with its EVR packet;<br>• groups the hits into clusters;<br>• publishes one neutron per cluster: time of the first hit, position at the center scaled up 16 times (4096 × 4096 pixels, the pixels of the real ODIN file);<br>• uses the source `timepix3` and the topic `odin_detector`. | The same program, built from its sources (`Containerfile`). The configuration is `configs/odin_timepix3.json`, because the one used at ESS is not public. It sets 256 × 256 pixels scaled up 16 times and 14 Hz pulses. Its cluster gaps match the twin's clusters: 1 ns, and a coordinate gap of 2, which joins only touching pixels (the EFU joins two hits when their distance squared is strictly below the gap squared). |

The bit layout follows the EFU's sources: `src/modules/timepix3`, files `readout/DataParser.h`,
`dto/TimepixDataTypes.h`, `handlers/PixelEventHandler.cpp` and `geometry/Timepix3Geometry.h`. What the EFU makes of
the readout is known exactly, and `timepix3_readout.expected()` predicts it:

* **Pixel.** It is the same pixel, except in the last 15 sub-pixels of each axis. There the center of a cluster cannot
  go beyond the last chip pixel, so these neutrons land on sub-pixel 4080, as with the real camera.
* **Time of flight.** The camera codes times in steps of 1.5625 ns, and the EFU rounds them down. The time of flight
  comes back as `eto` or `eto + 1` ns.
* **Merged neutrons.** Two neutrons in the same pixel at the same nanosecond are one flash for the camera, so the EFU
  publishes one neutron. Two neutrons within 1 ns whose pixels touch also make one cluster (pile-up).

## LoKI: CAEN readout of the tubes

| At ESS | In the twin |
|---|---|
| A neutron absorbed in a straw of a tube makes a charge, read at both ends of the tube. The CAEN digitizers send one 24-byte **readout** per neutron: fiber, front-end board (FEN), group, time on the ESS clock (88.0525 MHz), and four amplitudes A, B, C, D. Each UDP packet starts with the ESS readout header (time of the pulse and of the previous one). | `caen_readout.py` turns each neutron of the twin's file into the readout of its pixel. Its amplitudes give the right straw and position by charge division, and its time is the nearest tick of the ESS clock. |
| The EFU (`loki` program) finds the straw from (B + D) / (A + B + C + D) and the position along it from (A + B) / (A + B + C + D), corrected by the calibration of that straw. It publishes one neutron per readout (no clustering), with source `caen`. Each bank has its own EFU and topic (`loki_detector_bank0` ... `bank8`), as in the real file. | The same program, one per bank (`service.py`). The configuration is `configs/loki.json`, the 9 banks and 10 rings of `LokiFull.json` of the EFU's sources: its pixel numbers are exactly those of the real LoKI file (3,211,264 pixels). The calibration is null (no correction), written by `caen_readout.null_calibration()`: the twin's charge division is ideal. ESS's real calibration is not public. |

The bit layout follows the EFU's sources: `src/common/readout/ess/Parser.h`, `src/modules/caen/readout/DataParser.h`,
`src/modules/caen/geometry/CDCalibration.cpp`, `src/modules/loki/geometry/LokiGeometry.cpp` and `LokiConfig.h`,
`src/common/time/ESSTime.h`. What the EFU makes of the readout is known exactly (`caen_readout.expected()`):

* **Pixel.** The same pixel.
* **Time of flight.** The readout time and the pulse time are each rounded to a tick of the ESS clock (11.4 ns), so the
  time of flight comes back within 10 ns of `eto`.
* **Every neutron.** No clustering: each neutron of the twin comes back once, identical neutrons included.

## Correction made to the EFU

The test found a defect in the EFU's timepix3 module. At each new pulse, `handlers/PixelEventHandler.cpp` changes
the reference time of the ev44 message with `serializer.setReferenceTime()`. That call does not first publish the
neutrons already in the message, so the last neutrons of a pulse leave with the time of the next pulse.

* In the test, these were 4007 neutrons of pulse 0 and 2462 of pulse 1, with their times of flight still counted from
  their own pulse.
* At ESS it should happen too: pulses come every 71 ms, and the EFU otherwise publishes only every second.
* `EV44Serializer::checkAndSetReferenceTime()` publishes them first. The counter `produce.cause.pulse_change` of the
  module counts that, so it was the intent.

The image is built with this one-line change (`EFU_PATCH=1` in the `Containerfile`, written in `/opt/efu/EFU_VERSION`).
The build stops if the line changes upstream. Reported to ECDC (2026-11-10): https://github.com/ess-dmsc/event-formation-unit/issues/852

## Steps

1. **Build.** `.github/workflows/efu.yml` builds the EFU as ECDC does: Ubuntu 22.04, Conan 1, profile
   `linux_x86_64_gcc11`, CMake, programs `timepix3` and `loki`. It records the commit in `/opt/efu/EFU_VERSION` and
   publishes `ghcr.io/aglaenze/access-digital-twins-efu`. The mirror's tags stop in 2020, so the image is built from
   `master`.
2. **ODIN end to end.** This step runs only on GitHub, never on a student's computer. A Kafka broker and the EFU run
   on the runner. `e2e_test.py` reads the neutrons of the real ODIN file (1 M neutrons in 3 pulses) and sends their
   readout over UDP. It reads back the EFU's ev44 messages and compares them pulse by pulse. It requires 99.5 % of
   the distinct neutrons found with the same pixel and the same time of flight.

   Result (run of commit 5f68e52):
   * 939,572 of the 939,580 distinct neutrons come back with the same pixel and time of flight (99.999 %).
   * The 8 others were piled up, as predicted from the file: 9 pairs within 1 ns whose pixels touch.
   * 195 neutrons come back twice. They are probably identical neutrons split between two UDP packets: the EFU
     clusters each packet on its own. This explanation is not yet checked.

   **LoKI end to end** (`e2e_loki.py`, nine EFUs, one per bank). The neutrons of the real LoKI file
   (`ess.loki.data.loki_coda_file()`), then 2 million random neutrons on all the pixels, are sent as CAEN readout.
   Every neutron must come back once, with the same pixel and the time of flight of `caen_readout.expected()`.
   Result (run of commit b509968): 103,431 of 103,431 neutrons of the real file and 2,000,000 of 2,000,000 random ones,
   in all 9 banks.

   `python efu/timepix3_readout.py` checks the coding without the EFU. It runs the EFU's computation, rewritten in
   Python, on 200 000 random neutrons. `python efu/caen_readout.py` does the same for LoKI, on every pixel and on
   300 000 random neutrons.

## In the app

The app's image holds the EFU (Linux x86-64 only, as the file-writer). It is copied from the image above, fixed by
its digest.

```
python nicos/start_nicos.py --instrument odin --efu --filewriter     # or TWIN_EFU=1
python nicos/start_nicos.py --instrument loki --efu --filewriter
```

With `--efu`:

* **The EFUs.** `service.py` starts them before the twin server, one per detector topic of the real file. ODIN: one
  EFU, UDP port 9000, topic `odin_detector`. LoKI: nine EFUs, UDP ports 9100 to 9108, topics `loki_detector_bank0`
  to `bank8`.
* **The twin.** At each pulse of a count, the twin server sends the readout of its detectors instead of publishing
  the neutrons (`filewriter/twin_filewriter.py`: `count_messages(efu=service.targets())`, `EFU_SOURCES`). The pulse
  and packet counters go on from count to count, as on the instrument. The packets of a pulse are spread over at
  most 60 ms.
* **The comparison.** At the end of a job, the file-writer's file is compared with the twin's file. For the neutrons,
  the comparison is the `match()` of the readout module instead of identity, pulse times within 10 µs. ODIN: 99.5 %
  of the distinct neutrons. LoKI: every neutron. NICOS prints the lines "through the EFU: … found exactly".

The container test (`../container/smoke_test.py`, last step, GitHub only) runs one job of each instrument this way.

* ODIN (run of commit 65e5663): 1,784,932 of the 1,785,395 distinct neutrons come back with the same pixel and time
  of flight (99.974 %), and the rest of the file is the same as the twin's. The cause of the 463 others is not yet
  checked: pile-up, or clusters cut (the EFU counted 180 clusters too small). In the container the kernel gave the
  EFU a receive buffer of 2 MB instead of the 32 MB asked.
* LoKI (run of commit b509968): a count of 30 s on D2O, 4,818,037 neutrons in the 9 banks. Every one comes back
  once, with the same pixel and the predicted time of flight (100 %), and the rest of the file is the same as the
  twin's.

## Still to do

* esslivedata with the EFU: not yet tested together.

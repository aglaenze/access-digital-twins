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
| The EFU (`timepix3` program):<br>• pairs each TDC word with its EVR packet;<br>• groups the hits into clusters;<br>• publishes one neutron per cluster: time of the first hit, position at the center scaled up 16 times (4096 × 4096 pixels, the pixels of the real ODIN file);<br>• uses the source `timepix3` and the topic `odin_detector`. | The same program, built from its sources (`Containerfile`). The configuration is `configs/odin_timepix3.json`, because the one used at ESS is not public. It sets 256 × 256 pixels scaled up 16 times and 14 Hz pulses. Its cluster gaps (1 ns, 1 chip pixel) match the twin's clusters. |

The bit layout follows the EFU's sources: `src/modules/timepix3`, files `readout/DataParser.h`,
`dto/TimepixDataTypes.h`, `handlers/PixelEventHandler.cpp` and `geometry/Timepix3Geometry.h`. What the EFU makes of
the readout is known exactly, and `timepix3_readout.expected()` predicts it:

* **Pixel.** It is the same pixel, except in the last 15 sub-pixels of each axis. There the center of a cluster cannot
  go beyond the last chip pixel, so these neutrons land on sub-pixel 4080, as with the real camera.
* **Time of flight.** The camera codes times in steps of 1.5625 ns, and the EFU rounds them down. The time of flight
  comes back as `eto` or `eto + 1` ns.
* **Merged neutrons.** Two neutrons in the same pixel at the same nanosecond are one flash for the camera, so the EFU
  publishes one neutron. Two neutrons within 1 ns and 1 chip pixel of each other also make one cluster (pile-up).

## Steps

1. **Build.** `.github/workflows/efu.yml` builds the EFU as ECDC does: Ubuntu 22.04, Conan 1, profile
   `linux_x86_64_gcc11`, CMake, programs `timepix3` and `loki`. It records the commit in `/opt/efu/EFU_VERSION` and
   publishes `ghcr.io/aglaenze/access-digital-twins-efu`. The mirror's tags stop in 2020, so the image is built from
   `master`.
2. **ODIN end to end.** This step runs only on GitHub, never on a student's computer. A Kafka broker and the EFU run
   on the runner. `e2e_test.py` reads the neutrons of the real ODIN file (1 M neutrons in 3 pulses) and sends their
   readout over UDP. It reads back the EFU's ev44 messages and compares them pulse by pulse. It requires 99.5 % of
   the distinct neutrons found with the same pixel and the same time of flight.

   `python efu/timepix3_readout.py` checks the coding without the EFU. It runs the EFU's computation, rewritten in
   Python, on 200 000 random neutrons.

## Still to do

* Put the EFU into the app's image, with `start_nicos.py --efu` or `TWIN_EFU=1`. The twin would then send the readout
  instead of the neutrons. The file-writer and esslivedata would read the EFU's neutrons.
* LoKI: CAEN readout, which uses the ESS readout header and a calibration file (`loki` program).

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
The build stops if the line changes upstream. It is worth reporting to ECDC.

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

   `python efu/timepix3_readout.py` checks the coding without the EFU. It runs the EFU's computation, rewritten in
   Python, on 200 000 random neutrons.

## Still to do

* Put the EFU into the app's image, with `start_nicos.py --efu` or `TWIN_EFU=1`. The twin would then send the readout
  instead of the neutrons. The file-writer and esslivedata would read the EFU's neutrons.
* LoKI: CAEN readout, which uses the ESS readout header and a calibration file (`loki` program).

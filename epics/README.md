# EPICS layer of the twin: soft IOC and ESS forwarder

At ESS every device (motor, chopper, shutter, sensor) is an **EPICS PV**: a named value served on the network by an
**IOC**, the program in front of the hardware. The **forwarder** of ESS (https://github.com/ess-dmsc/forwarder)
subscribes to the PVs and relays their values to Kafka (f144 messages), where the file-writer and the live data
reduction read them. With `--epics`, the twin does the same:

| Piece | At ESS | In the twin |
|---|---|---|
| PVs | one IOC per piece of hardware | `ioc.py`: one soft IOC (p4p, pvAccess, on 127.0.0.1) serving every device written in the real ESS file of the instrument, with its real PV name (e.g. `ODIN-ChpSy1:Chop-WFMC-101:Spd_S`): 365 PVs for ODIN; their values are the current settings of the twin (twin server, `GET /epics`, every 0.5 s) |
| Forwarder | ESS forwarder | the same program (release v2.1.0, own conda environment `forwarder`), configured with every PV (fc00 message: topic of the real file, f144, pvAccess) and a periodic update every 5 s |
| Topics | `<instrument>_choppers`, `_motion`, ... | the same, from the real file |

```
python nicos/start_nicos.py --instrument odin --epics --filewriter     # or TWIN_EPICS=1 (the app container)
```
With the EPICS layer on, the twin server no longer publishes the device values itself (`snapshot_messages`, the f144
of `count_messages`): the forwarder does. It keeps publishing the neutrons and the proton charge of each pulse, which
come with the detector data. `compare.py` then checks the device values by value in force at their time (the
forwarder stamps them with the time of the PV update), not by identical times.

## Tests

Container test (`../container/smoke_test.py`, last step, GitHub only, Intel/AMD: it needs the file-writer): NICOS of
ODIN with `--epics --filewriter`, one job; the file-writer's file must have the same data as the twin's (every device
with a value, relayed by the forwarder), and the position of the sample stage set in NICOS must be in it.

## Limits, still to do

* The PVs are read-only: NICOS still drives the twin over HTTP (its devices of `nicos_twin`), not through the PVs as
  at ESS (`nicos.devices.epics.pva`: `EpicsAnalogMoveable`, `EpicsMappedMoveable`...). Next step.
* The PV names are those of the real file of the instrument; devices that the twin has but the file has not (diffuser,
  pinhole of the twin) have no PV.
* Only the pvAccess protocol (as at ESS); no Channel Access.

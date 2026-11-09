# EPICS layer of the twin: soft IOC and ESS forwarder

At ESS every device (motor, chopper, shutter, sensor) is an **EPICS PV**: a named value served on the network by an
**IOC**, the program in front of the hardware. The **forwarder** of ESS (https://github.com/ess-dmsc/forwarder)
subscribes to the PVs and relays their values to Kafka (f144 messages), where the file-writer and the live data
reduction read them. With `--epics`, the twin does the same:

| Piece | At ESS | In the twin |
|---|---|---|
| PVs | one IOC per piece of hardware | `ioc.py`: one soft IOC (p4p, pvAccess, on 127.0.0.1) serving every device written in the real ESS file of the instrument, with its real PV name (e.g. `ODIN-ChpSy1:Chop-WFMC-101:Spd_S`): 365 PVs for ODIN; their values are the current settings of the twin (twin server, `GET /epics`, every 0.5 s) |
| Forwarder | ESS forwarder | the same program (release v2.1.0, run from its source tree with `forwarder_launch.py` as ESS does, own conda environment `forwarder`), configured with every PV (fc00 message: topic of the real file, f144, pvAccess) and a periodic update every 5 s |
| Topics | `<instrument>_choppers`, `_motion`, ... | the same, from the real file |
| Motors driven by NICOS | EPICS motor records (`<record>.VAL`, `.RBV`, `.DMOV`, `.HLM`, `.EGU`...), NICOS class `nicos_ess.devices.epics.pva.motor.EpicsMotor` | the same class, on the motor records the soft IOC serves for the twin's motors (ODIN: `stage_x` = `ODIN-SpSt1:MC-LinY-01:Mtr`, `stage_rot` = `ODIN-SpSt1:MC-RotZ-01:Mtr`, the records of the real file); a target written to `VAL` moves the twin (`POST /epics/put`) |

```
python nicos/start_nicos.py --instrument odin --epics --filewriter     # or TWIN_EPICS=1 (the app container)
```
With the EPICS layer on, the twin server no longer publishes the device values itself (`snapshot_messages`, the f144
of `count_messages`): the forwarder does. It keeps publishing the neutrons and the proton charge of each pulse, which
come with the detector data. `compare.py` then checks the device values by value in force at their time (the
forwarder stamps them with the time of the PV update), not by identical times.

With `--epics`, the NICOS setup of ODIN (`nicos/nicos_twin/odin/setups/odin.py`) replaces the twin's devices `stage_x`
and `stage_rot` (HTTP) by `EpicsMotor` devices on these records: `move(stage_x, 500)` writes 500 to
`ODIN-SpSt1:MC-LinY-01:Mtr.VAL`, the soft IOC moves the twin (`DMOV` 1 -> 0 -> 1, `RBV` = 500 mm), the forwarder relays
the new value to Kafka and the file-writer writes it, as at ESS. The motors of the twin are ideal: always enabled, no
limit switch, no error, the target reached at once.

## Tests

Container test (`../container/smoke_test.py`, last step, GitHub only, Intel/AMD: it needs the file-writer): NICOS of
ODIN with `--epics --filewriter`, one job; NICOS must use `EpicsMotor` on the real motor record of the sample stage and
read back the position it set (500 mm); the file-writer's file must have the same data as the twin's (every device
with a value, relayed by the forwarder), and that position must be in it. Where the file-writer is installed, a
missing forwarder is a failure.

## Limits, still to do

* Only the motors are driven through EPICS. The choppers, shutter, pinhole and diffuser stay devices of `nicos_twin`
  (HTTP): at ESS the choppers have their own NICOS devices on many PVs of the chopper IOC, and the shutter of ODIN is a
  manual switch in its NICOS setups; the pinhole and the diffuser are switches of the twin.
* LoKI: the devices of its twin are switches (shutters, collimation, detector distance among fixed values), not
  motors, so they all stay on HTTP.
* The PV names are those of the real file of the instrument; devices that the twin has but the file has not (diffuser,
  pinhole of the twin) have no PV.
* Only the pvAccess protocol (as at ESS); no Channel Access.

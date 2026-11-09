# The ESS file-writer in the twins (started 2026-11-06; end to end with the real file-writer since 2026-11-07; in the app image and reduced since 2026-11-09)

At ESS the data files are not written by NICOS nor by the instrument: NICOS sends a *start* command to the
**file-writer** (`kafka-to-nexus`, by ECDC), which then reads the Kafka streams (the neutrons of the detectors and
monitors, the values of the devices sent by the EPICS forwarder) and writes the NeXus file. Today the twin writes its
files itself (`odin_nexus.py`, `loki_nexus.py`), in the same format. The goal: the real file-writer writes them, from
the streams of the twin, as at ESS.

| Step | What | Status |
|---|---|---|
| 1 | Build `kafka-to-nexus` from its sources (Linux only: C++, Conan 1 with the configuration of ECDC); image `ghcr.io/aglaenze/access-digital-twins-filewriter` (`Containerfile`, workflow `filewriter.yml`) | done 2026-11-07 (kafka-to-nexus b6722d0d) |
| 2 | The twin publishes what the file-writer reads, under the names of the real instrument: the neutrons of the detectors and of the monitors (`ev44`), the values of the devices (`f144`) | done 2026-11-06 |
| 3 | NICOS starts and stops the jobs (`pl72`/`6s4t`); the structure of the file and the template come from the real ESS file | done 2026-11-07 (with the real file-writer, workflow `filewriter.yml`) |
| 4 | Compare the file of the file-writer with the files of the twin (`compare.py`); then the ESS reduction (essimaging, esssans) on it | done: same data (2026-11-07); same reduced results (2026-11-09, see below) |
| 5 | The file-writer in the app image, started with NICOS (`start_nicos.py --filewriter`) | done 2026-11-09 (Linux x86-64 only) |

## How it works

Every stream of a real ESS file says where its data came from: its group has the attributes `writer_module` (`f144`:
values of a device, `ev44`: neutron events), `source` (EPICS PV name, detector or monitor name) and `topic` (Kafka
topic). Examples: ODIN `entry/instrument/timepix3/data` (ev44, source `timepix3`, topic `odin_detector`); LoKI
`beam_monitor_m1/monitor_events` (ev44, `cbm2`, `loki_beam_monitor`); ODIN `foc1/rotation_speed` (f144,
`ODIN-ChpSy1:Chop-FOC-101:Spd_R`, `odin_choppers`). The twin's files are copies of such a real file (the one shipped
with essimaging / esssans), so everything is made from it (`twin_filewriter.py`):

* **the template** of the file-writer (`make_template`): the real file without the streams the twin publishes and
  without the values of a run, with the static changes of the twin (ODIN: detector distance; LoKI: source distance).
  The file-writer copies it at the start of each job (`<hdf-template-prefix>/<instrument>/<instrument>.hdf`, chosen by
  the instrument name of the start command): the geometry and the pixel tables (16 million pixels for ODIN) are not
  sent through Kafka;
* **the start command** (`nexus_structure`): each stream of the real file as its writer module, same source and same
  topic (ODIN 367 streams, LoKI 154), plus the title, the proposal, the sample name and the start and end times
  (`mdat`); for LoKI also `entry/twin`, the settings of the twin at the start of the job (its configuration: what its
  reduction needs to find its wavelength table and calibration), as NICOS writes the values of its devices into the
  start command at ESS. It is sent as NICOS does at ESS (`nicos_ess/devices/datasinks/file_writer.py`): to the job pool
  (`<instrument>_filewriter_pool`), naming `<instrument>_filewriter` as the control topic, where the file-writer
  answers, takes the stop and reports the end of the file;
* **the messages**: just before the start of a job, the value of every device (`snapshot_messages`, as the EPICS
  forwarder has published them): the current settings of the twin (`nexus_logs()` of the instrument, the same values it writes
  in its own files), the other devices from the real file; for each count of the twin, the neutrons of every detector bank and monitor, one message per
  source pulse, and the device values set for the count (`count_messages`), sent at the times of the pulses: a count
  lasts its counting time, as on the instrument.

Not streamed by the twin: the chopper top-dead-center timestamps (`tdct`); they stay those of the real file, in the
template. The truths of the twin (`entry/twin/true_*`) and its event sampling are only in its own
files (they are not data of the instrument): the twin keeps writing its own files, which the exercises read (see
"Two kinds of files" below).

## Using it

* **Twin server** (`twin_server.py`): `POST /filewriter/start {title, proposal, folder}` and `POST /filewriter/stop`
  (which waits for the file and compares it with the twin's files of the job). Kafka broker: `TWIN_KAFKA`; templates
  written to `TWIN_FW_TEMPLATES` (default `<TWIN_RUN_ROOT>/filewriter/templates`).
* **NICOS**: with `TWIN_FILEWRITER=1`, `nexusfile_open` / `start_filewriting` / `stop_filewriting` (same commands as at
  ESS) start and stop a job: everything recorded in between goes into ONE file of the file-writer,
  `<instrument>_job_NNNNNN.hdf` in the proposal folder, as at ESS; NICOS then shows the comparison.
* **In the app image** (`container/Containerfile`: copied from the file-writer image, pinned by its digest; Linux
  x86-64 only, none on ARM): `python nicos/start_nicos.py --instrument odin --filewriter` (or `TWIN_FILEWRITER=1`,
  e.g. `docker run -e TWIN_FILEWRITER=1 ...` for the control room of the app) starts the Kafka broker and
  kafka-to-nexus for the instrument (`service.py`) next to NICOS, which then uses it. Without it (Windows, ARM, the
  option off) the launcher says so and the twin writes its files alone, as before.
* **The file-writer by hand** (Linux, in its image):

      kafka-to-nexus --brokers <broker> --command-status-topic <instrument>_filewriter
          --job-pool-topic <instrument>_filewriter_pool --hdf-output-prefix / --hdf-template-prefix <templates>

  It must see the data folders at the same paths as the twin. The broker must accept messages of 16 MB (one pulse of
  ODIN neutrons: about 5 MB).
* **Live display**: just-bin-it reads only the twin's superpixels (source `odin_detector`, `nicos_twin/odin/setups/
  live.py`), not the full pixels published for the file-writer on the same topic.
* **Comparison by hand**: `python filewriter/compare.py <file of the file-writer> <twin file> [...]`.

## What the file-writer requires (found with the real one, 2026-11-07)

* **Job and command ids** in the form of those of NICOS: a UUID with digits only up to position 14, `5` at
  position 14 and `8` at position 19 (`isValidUUID`, `src/CommandSystem/Handler.cpp`); others: "job id was invalid".
* **The template** in the HDF5 1.10 format (superblock 3: it opens its copy in SWMR mode), and without the root
  attributes it writes into each file (`HDF5_Version`, `file_name`, `creator`, `file_time`, `dynamic_version`).
* **Every topic** of the start command existing when the job starts (otherwise the job ends at once: "Unable to set up
  consumer ... as this topic does not exist"); `FileWriterControl.start` creates them. Its command and pool topics
  existing before it starts.
* **The attributes of every stream group** in the start command (found 2026-11-09): it creates these groups (they are
  not in the template) with only what the command gives. Without them a log that is a transformation loses its
  `depends_on`, `transformation_type` and `vector` (LoKI detector carriage: essreduce then cannot place the rear
  bank). `nexus_structure` copies them from the real file; `compare.py` checks them.
* **The device values published before the job starts** (found 2026-11-09): at the start of a job it looks in each
  topic for the messages from 10 s before the start; if there are none, it reads from the end of the topic, so a
  message published just after the start command can be missed (it was: chopper setpoints missing). As the EPICS
  forwarder at ESS, the twin publishes the value of every device before the start command, stamped 1 ms before the
  start; the file-writer keeps the last value before the start of each device and writes it (`SourceFilter`).
* **The time zones** (`tzdata`) in its image (it writes the time of the file).
* After its "finished writing" message (`wrdn`) it opens the file once more to add the metadata (start and end times):
  read the file only once it is closed (`compare.open_fw` waits).
* It logs only to **syslog** (no console output): `-v /dev/log:/dev/log` gives it the journal of the host
  (`journalctl -t kafka-to-nexus`).

## What the ESS reduction needs on its files (2026-11-09)

A file of the file-writer has, for each device, every value received during the job: the one at the start of the job
(the forwarder's), then those of each measurement; a file of the twin has one. essreduce needs one value per setting:

* **chopper settings** (speed setpoint, delay, phase): "must be a scalar variable, got a 1d variable" (scippneutron,
  *processing NeXus choppers*). `odin_reduction` replaces the provider of the choppers by one that first takes the
  last value (`_settled_choppers`), with a warning if the values differ;
* **positions** (LoKI detector carriage): "Transform is time-dependent, but no filter is provided". essreduce has a
  parameter for it, `TransformationTimeFilter`; `loki_reduction.settled_transform` takes the last value, with a warning
  if they differ;
* the values given before the job must be the **current settings** of the twin (before: those of its last file,
  wrong when a setting had just changed);
* **ODIN, duration of a measurement**: the source pulses recorded (proton charge log) / 14 Hz instead of end - start:
  a job also lasts while the twin computes, without neutrons; the same value for a real file and a twin file; the
  proton charge is never in the snapshot (it would count one pulse more);
* **LoKI** reads its configuration in `entry/twin`, which the start command now gives;
* **arrival times in whole nanoseconds** (`event_time_offset`, int32, as ev44): the ODIN twin wrote them with
  decimals (float64); the file-writer's were then up to 0.5 ns different, and the wavelengths by up to 7e-8 Å
  (2026-11-09). The twin now writes whole nanoseconds after the pulse time (rounded to the ns too), as at ESS (LoKI
  already did: uint32).

Checked first on files made like those of the file-writer (every log of real twin files given a second value): ODIN
(60 s, iron plate) image and spectrum identical, duration 60 s and proton charge identical; LoKI (silica spheres,
solvent, empty beam) I(Q) of the rear and middle banks identical. Then in the app image (smoke test, below).
At ESS the same will happen with long jobs (a value at every change): to tell the scipp team.

## Two kinds of files (decision proposed 2026-11-09)

The twin keeps writing its own files, one per count, and the file-writer (when on) writes one per job, as at ESS:

* the exercises, quizzes and notebooks read the twin's files: they hold the truths (`true_*`) and the event sampling,
  and exist everywhere (Windows, ARM, without Kafka), where kafka-to-nexus cannot run;
* the file-writer's files show the real ESS chain (one file per `nexusfile_open` block, the NICOS commands, the
  comparison printed by NICOS) and reduce to the same results: an option for the control room (MSc, free beamtime),
  off by default (a Kafka broker and every neutron twice on disk).

## Tests

* `e2e_test.py`, run by the workflow `filewriter.yml` after the build: a Kafka broker and kafka-to-nexus on the runner;
  for ODIN and LoKI, a job with a measurement made from the real file (its pulses moved to now: no McStas needed),
  then `compare.py`. Passed on 2026-11-07: ODIN 1 000 000 events of `timepix3`, LoKI the 14 event streams (5 beam
  monitors, 9 detector banks, 2 230 to 13 020 events each), identical to the twin's files; the device values set
  during the measurement (3 of 3), the title, the sample name, the start and end times written.
* `container/smoke_test.py` step 6, in the app image (amd64), by `container.yml`: NICOS started with
  `--filewriter`; ODIN jobs dark, open beam, iron plate and LoKI jobs empty beam, solvent, silica spheres, through
  `nexusfile_open`; NICOS must report "same data" for each; then essimaging (transmission, spectrum and image) and
  esssans (I(Q), rear, middle and front banks) from the file-writer's files and from the twin's: the same results.
* On Windows (no file-writer): the twin server with a stand-in file-writer that answers the commands (2026-11-06, ODIN
  count of 5 s: 2 149 838 neutrons published in 70 messages, source `timepix3`, the count lasting its 5 s).

## Still to do

* Decide whether the file-writer is on by default in the control room of the app (above: proposed off).
* To discuss with ECDC (ESS): which version of kafka-to-nexus to use, and whether a ready-made image exists; with the
  scipp team: time-dependent chopper settings in files of long jobs.
* Its log: syslog only, none in the app image (its errors reach NICOS in its answers).

Sources: https://github.com/ess-dmsc/kafka-to-nexus (mirror of gitlab.esss.lu.se/ecdc/ess-dmsc/kafka-to-nexus):
`documentation/commands.md`, `writer_module_*.md`, `src/Master.cpp` (template path); https://github.com/ess-dmsc/conan-configuration.

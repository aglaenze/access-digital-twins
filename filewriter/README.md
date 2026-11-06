# The ESS file-writer in the twins (work in progress, started 2026-11-06)

At ESS the data files are not written by NICOS nor by the instrument: NICOS sends a *start* command to the
**file-writer** (`kafka-to-nexus`, by ECDC), which then reads the Kafka streams (the neutrons of the detectors and
monitors, the values of the devices sent by the EPICS forwarder) and writes the NeXus file. Today the twin writes its
files itself (`odin_nexus.py`, `loki_nexus.py`), in the same format. The goal: the real file-writer writes them, from
the streams of the twin, as at ESS.

| Step | What | Status |
|---|---|---|
| 1 | Build `kafka-to-nexus` from its sources (Linux only: C++, Conan 1 with the configuration of ECDC); image `ghcr.io/aglaenze/access-digital-twins-filewriter` (`Containerfile`, workflow `filewriter.yml`) | in progress |
| 2 | The twin publishes what the file-writer reads, under the names of the real instrument: the neutrons of the detectors and of the monitors (`ev44`), the values of the devices (`f144`) | done 2026-11-06 |
| 3 | NICOS starts and stops the jobs (`pl72`/`6s4t`); the structure of the file and the template come from the real ESS file | done 2026-11-06 (checked on Windows with a stand-in file-writer; with the real one: workflow) |
| 4 | Compare the file of the file-writer with the files of the twin (`compare.py`); then the ESS reduction (essimaging, esssans) on it | comparison done; reduction to do |

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
  (`mdat`);
* **the messages**: at the start of a job, the last value of every device (`snapshot_messages`, as the EPICS forwarder
  has published them); for each count of the twin, the neutrons of every detector bank and monitor, one message per
  source pulse, and the device values set for the count (`count_messages`), sent at the times of the pulses: a count
  lasts its counting time, as on the instrument.

Not streamed by the twin: the chopper top-dead-center timestamps (`tdct`); they stay those of the real file, in the
template. The truths and settings of the twin (`entry/twin`) are only in the twin's own files (they are not data of
the instrument): the twin keeps writing its own files, which the exercises read.

## Using it

* **Twin server** (`twin_server.py`): `POST /filewriter/start {title, proposal, folder}` and `POST /filewriter/stop`
  (which waits for the file and compares it with the twin's files of the job). Kafka broker: `TWIN_KAFKA`; templates
  written to `TWIN_FW_TEMPLATES` (default `<TWIN_RUN_ROOT>/filewriter/templates`).
* **NICOS**: with `TWIN_FILEWRITER=1`, `nexusfile_open` / `start_filewriting` / `stop_filewriting` (same commands as at
  ESS) start and stop a job: everything recorded in between goes into ONE file of the file-writer,
  `<instrument>_job_NNNNNN.hdf` in the proposal folder, as at ESS; NICOS then shows the comparison.
* **The file-writer** (Linux, in its image):

      kafka-to-nexus --brokers <broker> --command-status-topic <instrument>_filewriter
          --job-pool-topic <instrument>_filewriter_pool --hdf-output-prefix / --hdf-template-prefix <templates>

  It must see the data folders at the same paths as the twin. The broker must accept messages of 16 MB (one pulse of
  ODIN neutrons: about 5 MB).
* **Live display**: just-bin-it reads only the twin's superpixels (source `odin_detector`, `nicos_twin/odin/setups/
  live.py`), not the full pixels published for the file-writer on the same topic.
* **Comparison by hand**: `python filewriter/compare.py <file of the file-writer> <twin file> [...]`.

## Tests

* `e2e_test.py`, run by the workflow `filewriter.yml` after the build: a Kafka broker and kafka-to-nexus on the runner;
  for ODIN and LoKI, a job with a measurement made from the real file (its pulses moved to now: no McStas needed),
  then `compare.py`.
* On Windows (no file-writer): the twin server with a stand-in file-writer that answers the commands (2026-11-06, ODIN
  count of 5 s: 2 149 838 neutrons published in 70 messages, source `timepix3`, the count lasting its 5 s).

## Still to do

* The file-writer next to the twin in the app (a second container, or in the twin's image); NICOS started with
  `TWIN_FILEWRITER=1` there.
* The ESS reduction on the file-writer's files (step 4); then decide whether the twin stops writing its own files
  (the truths of `entry/twin` would then go elsewhere).
* To discuss with ECDC (ESS): which version of kafka-to-nexus to use, and whether a ready-made image exists.

Sources: https://github.com/ess-dmsc/kafka-to-nexus (mirror of gitlab.esss.lu.se/ecdc/ess-dmsc/kafka-to-nexus):
`documentation/commands.md`, `writer_module_*.md`, `src/Master.cpp` (template path); https://github.com/ess-dmsc/conan-configuration.

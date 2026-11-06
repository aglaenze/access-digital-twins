# The ESS file-writer in the twins (work in progress, started 2026-11-06)

At ESS the data files are not written by NICOS nor by the instrument: NICOS sends a *start* command to the
**file-writer** (`kafka-to-nexus`, by ECDC), which then reads the Kafka streams (the neutrons of the detectors, the
values of the devices sent by the EPICS forwarder) and writes the NeXus file, with the structure given in the command.
Today the twin writes its files itself (`odin_nexus.py`, `loki_nexus.py`), in the same format. The goal: the real
file-writer writes them, from the streams of the twin, as at ESS.

| Step | What | Status |
|---|---|---|
| 1 | Build `kafka-to-nexus` from its sources (Linux only: C++, Conan 1 with the configuration of ECDC); image `ghcr.io/aglaenze/access-digital-twins-filewriter` (`Containerfile`, workflow `filewriter.yml`) | started |
| 2 | The twin publishes what the file-writer reads: the neutrons (`ev44`, already done for the live data), the values of the devices (`f144`: `kafka/forwarder.py`, `TWIN_FORWARD=1`), the monitors | devices done 2026-11-06 (checked with the local Kafka: 29 values at start, then each change); monitors to do |
| 3 | NICOS sends the start/stop commands (`pl72`/`6s4t`) with the NeXus structure (JSON) of the instrument, built from the template of the real file (the devices of the ESS NICOS for the file-writer, `nicos_ess`) | to do |
| 4 | Compare the file of the file-writer with the file of the twin; the ESS reduction (essimaging, esssans) on it; then the twin stops writing its own files | to do |

Notes
- The file-writer runs only on Linux: in the container (and on a Linux server); on Windows without the container the
  twin keeps writing its files.
- Its configuration: an INI file (`brokers=localhost:9092`, `command-status-topic=...`, `job-pool-topic=...`,
  `hdf-output-prefix=...`), started with `--config-file`.
- The NeXus structure JSON: groups with `children`; streams as modules (`{"module": "f144", "config": {"source": ...,
  "topic": ...}}`, `ev44` for the events), static values as `{"module": "dataset", ...}`, links as `{"module": "link"}`.
- To discuss with ECDC (ESS): which version to use, and whether a ready-made image exists.

Sources: https://github.com/ess-dmsc/kafka-to-nexus (mirror of gitlab.esss.lu.se/ecdc/ess-dmsc/kafka-to-nexus),
its `documentation/commands.md`; https://github.com/ess-dmsc/conan-configuration.

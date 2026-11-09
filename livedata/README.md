# Live data reduction of ESS (esslivedata) with the twin

At ESS, the data of a running measurement are reduced live by **esslivedata** (scipp, https://github.com/scipp/esslivedata):
backend services read the events and the device values on Kafka, reduce them (detector images, monitor spectra, for
LoKI the I(Q) with the transmission) and publish the results; a dashboard (a web page) shows them next to NICOS, and
NICOS reads a few of them as "derived devices" (total counts, images). The twin runs the same program, unmodified,
on the same topics: the student sees the data of a count being reduced live, as in the control room of ESS.

| Piece | In the twin |
|---|---|
| esslivedata | release 26.11.0 (GitHub tag; it is not on PyPI nor conda-forge), own conda environment `livedata` (Python 3.13) in the image; its versions of essimaging and esssans (26.10.0, 26.6.0) are its own |
| Topics | the production ones, as at ESS: `<instrument>_detector`, `_beam_monitor`, `_choppers`... in; `<instrument>_livedata_data`, `_livedata_nicos_data`, `_livedata_commands`... |
| Events | each count of the twin is published as the instrument does (real sources and pixel numbers, at the times of its pulses): the same messages as for the ESS file-writer (`../filewriter/twin_filewriter.py`, `count_messages`) |
| Dashboard | http://127.0.0.1:5009 (theme "nicos", made to sit next to the NICOS window) |

## Use

```
python nicos/start_nicos.py --instrument odin --livedata     # or TWIN_LIVEDATA=1 (the app container)
```
The launcher starts the Kafka broker, the four backend services (`detector_data`, `monitor_data`, `data_reduction`,
`timeseries`) and the dashboard (`service.py`; logs `<TWIN_RUN_ROOT>/nicos/livedata_*.log`). A failure of esslivedata
does not stop NICOS. In the dashboard, start the reductions (the "workflows": ODIN detector image, monitors; LoKI
I(Q)...), then count in NICOS.

## Tests

The container test (`../container/smoke_test.py`, last step, on GitHub only): NICOS of ODIN with `--livedata`, the
dashboard answers, the ODIN image is started as from the dashboard (`service.start_workflow`: a `workflow_config`
command on `odin_livedata_commands`), a count of 10 s through `nexusfile_open`; the total that esslivedata publishes
for NICOS (`timepix3_counts_total`) must equal the number of neutrons in the twin's file.

After each count the twin sends 2 s of empty pulses (no neutrons) on every detector and monitor source
(`twin_filewriter.tail_messages`), as the real detectors keep sending: esslivedata closes a batch only when a later
pulse arrives (its clock is the time of the data), so without them the last pulse of a count was never reduced (found
on GitHub, 2026-11-09: 1.8 % of the neutrons of a 10 s count of ODIN missing).

## Limits, still to do

* With the ESS file-writer on as well, its files get these 2 s of empty pulses (pulses without neutrons: same data).
* Only the counts that write a file (inside `nexusfile_open`) are published: a count outside a file (`write=false`)
  is not seen by esslivedata yet.
* The dashboard is not in the control room of the app yet (a browser page on port 5009 of the container).
* NICOS does not read the derived devices of esslivedata yet (it shows the histograms of just-bin-it, `--live`).
* LoKI: the I(Q) workflow needs its parameters (transmission run, beam center): not tested yet.
* The reference data that some workflows download on first use (`SCIPP_DATA_DIR`, `<TWIN_RUN_ROOT>/livedata/cache`)
  need the network the first time.

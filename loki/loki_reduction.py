"""Reduction brick of the LoKI twin: the official ESS code (`esssans`, workflow `LokiWorkflow`), unmodified.

The twin's NeXus files (loki_nexus.py) go through the same workflow as those of the real LoKI (ESS notebook
"loki-reduction-ess"): events -> wavelength (lookup table) -> Q, normalization by the incident monitor, transmission
from the monitors of the transmission and empty-beam runs, solid angle, background subtraction.

What the twin provides, as the instrument team does at ESS:
  * the time -> λ lookup table of each chopper configuration, built by essreduce from the McStas beam at the sample
    position (`make_wavelength_lut_from_simulation`, the method ESS uses with McStas or `tof` simulations);
  * the "direct beam" function D(λ) of each detector bank, the calibration that makes I(Q) absolute (cm⁻¹ once divided
    by the sample thickness). As at a real instrument it is measured with a standard of known cross-section: here the
    twin measures its D₂O (flat incoherent scattering, 0.05 cm⁻¹ sr⁻¹) and an empty beam for one hour in the same
    configuration, once, and keeps the result. It corrects what the plain geometry does not know: the four layers of
    tubes and the seven straws per tube of LoKI overlap as seen from the sample, so the solid angle summed over the
    pixels is about ten times the true one (D ≈ 0.08-0.1 times the plain monitor ratio, slightly different per bank).

    import loki_reduction as red
    iq = red.reduce(sample="loki_000003.nxs", background="loki_000002.nxs", empty_beam="loki_000001.nxs")
"""
import os
import warnings

import numpy as np
import scipp as sc

warnings.filterwarnings("ignore", category=FutureWarning, module="ess")

import loki_paths as paths            # noqa: E402
import loki_mcstas as lm              # noqa: E402
import loki_nexus as lnx              # noqa: E402

LUT_DIR = f"{paths.RUN_ROOT}/lookup_tables"
Q_BINS = sc.geomspace("Q", 3e-3, 0.5, 101, unit="1/angstrom")


def _front_folder(info):
    return lm.front_folder(collen=float(info["collen"]), l_min=float(info["l_min"]), l_max=float(info["l_max"]),
                           sourceapx=float(info["sourceapx"]), sampleapx=float(info["sampleapx"]),
                           pulseskip=int(info["pulseskip"]), ncount=float(info["ncount"]))


def lookup_table(file):
    """Path of the time -> λ table for the chopper configuration of `file` (built once from the McStas beam)."""
    from ess.reduce.unwrap.lut import BeamlineComponentReading, SimulationResults, make_wavelength_lut_from_simulation
    info = lnx.read_twin(file)
    folder = _front_folder(info)
    os.makedirs(LUT_DIR, exist_ok=True)
    path = f"{LUT_DIR}/{os.path.basename(folder)}.h5"
    if os.path.isfile(path):
        return path
    b = lm.read_mcpl(lm.mcpl_path(folder, "beam_at_sample"))
    lam = sc.array(dims=["event"], values=b["lam"], unit="angstrom")
    w = sc.array(dims=["event"], values=b["w"])
    readings = {}
    # readings of the beam that reaches the sample (after all choppers), propagated back in free flight to 9.5 m
    # upstream (before the incident monitor) and at the sample; the table covers the monitors and all detector banks
    for name, dz in (("upstream", -9.5), ("sample", 0.0)):
        toa = b["t"] + (dz - b["z"]) / (lm.H_OVER_M / b["lam"])
        readings[name] = BeamlineComponentReading(time_of_arrival=sc.array(dims=["event"], values=toa * 1e6, unit="us"),
                                                  wavelength=lam, weight=w,
                                                  distance=sc.scalar(lm.L1 + dz, unit="m"))
    table = make_wavelength_lut_from_simulation(
        SimulationResults(readings=readings, choppers=None),
        ltotal_range=(sc.scalar(lm.L1 - 9.0, unit="m"), sc.scalar(lm.L1 + 11.0, unit="m")),
        distance_resolution=sc.scalar(0.05, unit="m"), time_resolution=sc.scalar(100.0, unit="us"),
        pulse_period=sc.scalar(1e6 / 14, unit="us"), pulse_stride=1 + int(info["pulseskip"]))
    table.save_hdf5(path)
    return path


def _plain_direct_beam(lam_min=0.5, lam_max=25.0):
    """D(λ) without calibration: neutrons on the sample per neutron counted by the incident monitor (the twin's monitor
    counts the beam that reaches the sample with the efficiency MONITOR_EFFICIENCY)."""
    lam = sc.linspace("wavelength", lam_min, lam_max, 50, unit="angstrom")
    return sc.DataArray(sc.full(dims=["wavelength"], shape=[50], value=1.0 / lnx.MONITOR_EFFICIENCY),
                        coords={"wavelength": lam})


CALIBRATION_TIME = 3600.0          # s of D₂O and of empty beam for the calibration
D2O_FLAT = 0.05                    # cm⁻¹ sr⁻¹: the cross-section of the standard (loki_samples.d2o)


def direct_beam(file, bank):
    """Calibrated D(λ) of `bank` for the configuration of `file` (measured once by the twin, then read back)."""
    from ess.sans.types import EmptyBeamRun, Filename, IntensityQ, SampleRun, TransmissionRun, WavelengthBands
    info = lnx.read_twin(file)
    folder = os.path.basename(_front_folder(info))
    dist = float(info["detector_distance"])
    path = f"{LUT_DIR}/direct_beam_ff_{folder}_det{dist:g}m_{bank}.h5"
    if os.path.isfile(path):
        return sc.io.load_hdf5(path)
    os.makedirs(LUT_DIR, exist_ok=True)
    runs = _calibration_runs(info)
    l_min, l_max = float(info["l_min"]), float(info["l_max"])
    edges = sc.geomspace("wavelength", l_min, l_max, 9, unit="angstrom")
    wf = workflow(runs["d2o"], bank, direct=_plain_direct_beam())          # with the flat field
    wf[Filename[SampleRun]] = runs["d2o"]
    wf[Filename[TransmissionRun[SampleRun]]] = runs["d2o"]
    wf[Filename[EmptyBeamRun]] = runs["empty_beam"]
    wf[WavelengthBands] = edges
    da = wf.compute(IntensityQ[SampleRun])
    import loki_samples as ls
    thick_cm = ls.SAMPLES["d2o"][2] * 100
    ratio = []
    for k in range(da.sizes["band"]):
        v = da["band", k].values
        ok = np.isfinite(v) & (v > 0)
        ratio.append(np.median(v[ok]) / (D2O_FLAT * thick_cm) if ok.sum() > 3 else np.nan)
    ratio = np.array(ratio)
    centers = np.sqrt(edges.values[1:] * edges.values[:-1])
    good = np.isfinite(ratio)
    coef = np.polyfit(np.log(centers[good]), ratio[good], 1 if good.sum() > 2 else 0)
    lam = np.linspace(0.5, 25.0, 50)
    k = np.polyval(coef, np.log(np.clip(lam, l_min, l_max)))
    d = sc.DataArray(sc.array(dims=["wavelength"], values=k / lnx.MONITOR_EFFICIENCY),
                     coords={"wavelength": sc.array(dims=["wavelength"], values=lam, unit="angstrom")})
    d.save_hdf5(path)
    return d


def _calibration_runs(info):
    """Files of the calibration (D₂O and empty beam, CALIBRATION_TIME each) in the configuration of `info`."""
    import glob
    from virtual_loki import VirtualLoki
    folder = os.path.basename(_front_folder(info))
    session = f"calibration/{folder}_det{float(info['detector_distance']):g}m"
    v = VirtualLoki(session=session, seed=12345)
    files = sorted(glob.glob(f"{v.folder}/loki_*.nxs"))
    if len(files) >= 2:
        return dict(empty_beam=files[0], d2o=files[1])
    v.move(heavy_shutter="open", shutter="open", collimation=info["collimation"],
           pulse_skipping=info["pulse_skipping"], detector_distance=float(info["detector_distance"]))
    out = {}
    for s in ("empty_beam", "d2o"):
        v.move(sample=s)
        out[s] = v.count(CALIBRATION_TIME, title=f"calibration: {s}")
    return out


_DETS = {}
FLAT_BLOCK = 32                    # pixels along a tube grouped in one cell of the flat field


def _flat_field_provider():
    """Provider of esssans' SolidAngle that multiplies the solid angle of each pixel by its efficiency (flat field)."""
    from typing import NewType
    import scippnexus as snx
    from ess.sans import normalization
    from ess.sans.types import DetectorPixelShape, EmptyDetector, NeXusTransformation, Position, RunType, SolidAngle
    global PixelEfficiency
    PixelEfficiency = NewType("PixelEfficiency", sc.Variable)

    def solid_angle_flat_field(data: EmptyDetector[RunType], pixel_shape: DetectorPixelShape[RunType],
                               transform: NeXusTransformation[snx.NXdetector, RunType],
                               sample_position: Position[snx.NXsample, RunType],
                               efficiency: PixelEfficiency) -> SolidAngle[RunType]:
        omega = normalization.solid_angle(data, pixel_shape, transform, sample_position)
        return SolidAngle[RunType](omega * efficiency)
    return solid_angle_flat_field


PixelEfficiency = None
_FLAT = _flat_field_provider()


def flat_field(file, bank, wf=None):
    """Efficiency of the pixels of `bank` relative to the bank (1 = average), measured as at a real SANS instrument
    with a flat scatterer: the twin's D₂O calibration run (one hour). Counts / solid angle, in cells (one tube, FLAT_BLOCK
    pixels along it, the 4 layers and 7 straws together: a few thousand counts each), normalized to the median cell.
    It corrects what one factor per bank cannot: the pixels near the edges of the middle and front banks receive more
    or fewer neutrons than their solid angle says (overlapping layers and straws). Kept in the calibration folder."""
    from ess.sans.types import EmptyBeamRun, Filename, RawDetector, SampleRun, SolidAngle, TransmissionRun
    info = lnx.read_twin(file)
    folder = os.path.basename(_front_folder(info))
    dist = float(info["detector_distance"])
    path = f"{LUT_DIR}/flat_field_{folder}_det{dist:g}m_{bank}.npy"
    if os.path.isfile(path):
        cells = np.load(path)
    else:
        runs = _calibration_runs(info)
        w = workflow(runs["d2o"], bank, direct=_plain_direct_beam(), flat=False)
        w[Filename[SampleRun]] = runs["d2o"]
        w[Filename[TransmissionRun[SampleRun]]] = runs["d2o"]
        w[Filename[EmptyBeamRun]] = runs["empty_beam"]
        raw = w.compute(RawDetector[SampleRun])
        counts = raw.bins.size().values.astype(float) if raw.bins is not None else raw.values
        omega = w.compute(SolidAngle[SampleRun]).values
        mask = w.compute(_masks_type())
        hidden = np.zeros(counts.shape, bool)
        for m in mask.values():
            hidden |= m.values
        L, T, S, P = counts.shape
        nb = P // FLAT_BLOCK
        c = np.where(hidden, 0, counts)[..., :nb * FLAT_BLOCK].reshape(L, T, S, nb, FLAT_BLOCK).sum(axis=(0, 2, 4))
        o = np.where(hidden, 0, omega)[..., :nb * FLAT_BLOCK].reshape(L, T, S, nb, FLAT_BLOCK).sum(axis=(0, 2, 4))
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.where((c >= 200) & (o > 0), c / o, np.nan)
        cells = np.where(np.isfinite(r), r / np.nanmedian(r), 1.0)
        os.makedirs(LUT_DIR, exist_ok=True)
        np.save(path, cells)
    if wf is None:
        return cells
    from ess.sans.types import DetectorIDs
    ids = wf.compute(DetectorIDs)
    L, T, S, P = ids.shape
    eff = np.repeat(cells, FLAT_BLOCK, axis=1)[:, :P]
    if eff.shape[1] < P:
        eff = np.pad(eff, ((0, 0), (0, P - eff.shape[1])), constant_values=1.0)
    eff = np.broadcast_to(eff[None, :, None, :], (L, T, S, P)).copy()
    return sc.array(dims=list(ids.dims), values=eff)


def _masks_type():
    from ess.sans.types import DetectorMasks
    return DetectorMasks


def masks(file, bank, wf):
    """{name: mask} of the pixels to exclude (beam stop and banks hidden by closer ones), for the detector distance
    of `file`: the twin computes them from the real geometry and keeps them, as the instrument team provides mask
    files at ESS."""
    from ess.sans.types import DetectorIDs
    dist = float(lnx.read_twin(file)["detector_distance"])
    path = f"{LUT_DIR}/masked_ids_det{dist:g}m_{bank}.npy"
    if os.path.isfile(path):
        hidden = np.load(path)
    else:
        os.makedirs(LUT_DIR, exist_ok=True)
        if dist not in _DETS:
            _DETS[dist] = lnx.RealDetector(dist)
        hidden = _DETS[dist].hidden_ids(bank)
        np.save(path, hidden)
    ids = wf.compute(DetectorIDs)
    mask = sc.zeros(sizes=ids.sizes, dtype="bool")
    mask.values[np.isin(ids.values, hidden)] = True
    return {"beam stop and shadows": mask}


def settled_transform(transform):
    """A time-dependent position (e.g. the detector carriage) reduced to one value, for essreduce
    (TransformationTimeFilter: it refuses time-dependent positions by default). A file of the twin has one value per
    log; a file of the ESS file-writer has every value received during the job: the one at its start (as the EPICS
    forwarder gives it), then those of each measurement. The last one is used; a warning if they differ (the
    detector moved during the job: one job per configuration, as at ESS)."""
    v = transform.values
    if not np.allclose(v, v[-1], rtol=1e-9, atol=1e-12):
        warnings.warn(f"position changed during the measurement ({np.unique(v)}); the last value is used",
                      stacklevel=2)
    return transform.data[transform.dims[0], -1]


def workflow(file, bank="loki_detector_0", wavelength_bins=None, q_bins=None, direct=None, flat=True):
    """LokiWorkflow with the parameters of the ESS notebook, for the configuration of `file`; flat: with the flat field
    of the pixels (flat_field)."""
    from ess import loki
    from ess.sans.types import (BeamCenter, CorrectForGravity, DetectorMasks, DirectBeam, Filename,
                                LookupTableFilename, NeXusDetectorName, QBins, ReturnEvents, SampleRun,
                                UncertaintyBroadcastMode, WavelengthBins)
    info = lnx.read_twin(file)
    from ess.reduce.nexus.types import TransformationTimeFilter
    wf = loki.LokiWorkflow()
    wf[TransformationTimeFilter] = settled_transform
    wf[NeXusDetectorName] = bank
    wf[WavelengthBins] = wavelength_bins if wavelength_bins is not None else sc.geomspace(
        "wavelength", float(info["l_min"]), float(info["l_max"]), 81, unit="angstrom")
    wf[QBins] = q_bins if q_bins is not None else Q_BINS
    wf[CorrectForGravity] = True
    wf[UncertaintyBroadcastMode] = UncertaintyBroadcastMode.upper_bound
    wf[ReturnEvents] = False
    wf[BeamCenter] = sc.vector([0.0, 0.0, 0.0], unit="m")          # the twin's beam is centered on the axis
    wf[Filename[SampleRun]] = file          # (replaced by the caller; here for the pixel numbers of the masks)
    wf[LookupTableFilename] = lookup_table(file)
    wf.insert(_FLAT)
    # pixel numbers needed by the flat field and the masks: before the masks are set (that removes their provider)
    eff = flat_field(file, bank, wf) if flat else sc.scalar(1.0)
    wf[DetectorMasks] = masks(file, bank, wf)
    wf[PixelEfficiency] = eff
    wf[DirectBeam] = direct if direct is not None else direct_beam(file, bank)
    return wf


def reduce(sample, background=None, empty_beam=None, sample_transmission=None, background_transmission=None,
           banks=("loki_detector_0",), q_bins=None):
    """I(Q) [cm⁻¹ per cm of sample... divided by the thickness: see absolute()] per bank, background subtracted if a
    background run is given. The transmission runs default to the sample/background runs themselves (the twin's
    transmission monitor always sees the transmitted beam)."""
    from ess.sans.types import (BackgroundRun, BackgroundSubtractedIofQ, EmptyBeamRun, Filename, IntensityQ,
                                SampleRun, TransmissionRun)
    out = {}
    for bank in banks:
        wf = workflow(sample, bank, q_bins=q_bins)
        wf[Filename[SampleRun]] = sample
        wf[Filename[TransmissionRun[SampleRun]]] = sample_transmission or sample
        wf[Filename[EmptyBeamRun]] = empty_beam
        if background is not None:
            wf[Filename[BackgroundRun]] = background
            wf[Filename[TransmissionRun[BackgroundRun]]] = background_transmission or background
            out[bank] = wf.compute(BackgroundSubtractedIofQ)
        else:
            out[bank] = wf.compute(IntensityQ[SampleRun])
    return out


BANK_GROUPS = {"rear": ["loki_detector_0"], "middle": [f"loki_detector_{i}" for i in range(1, 5)],
               "front": [f"loki_detector_{i}" for i in range(5, 9)]}


def to_arrays(da, thickness_cm):
    """(Q centers, I, dI) of one esssans result, divided by the sample thickness (-> cm⁻¹ sr⁻¹), empty bins removed."""
    q = sc.midpoints(da.coords["Q"]).values
    i, di = da.values / thickness_cm, np.sqrt(da.variances) / thickness_cm
    ok = np.isfinite(i) & np.isfinite(di) & (di > 0)
    return q[ok], i[ok], di[ok]


def combine(results, thickness_cm, groups=None):
    """{group: (Q, I, dI)}: the banks of each group (rear, middle, front) merged bin by bin (inverse-variance mean)."""
    out = {}
    for g, banks in (groups or BANK_GROUPS).items():
        banks = [b for b in banks if b in results]
        if not banks:
            continue
        q = sc.midpoints(results[banks[0]].coords["Q"]).values
        num, den = np.zeros(len(q)), np.zeros(len(q))
        for b in banks:
            i, var = results[b].values / thickness_cm, results[b].variances / thickness_cm ** 2
            ok = np.isfinite(i) & np.isfinite(var) & (var > 0)
            num[ok] += i[ok] / var[ok]
            den[ok] += 1 / var[ok]
        ok = den > 0
        out[g] = (q[ok], num[ok] / den[ok], 1 / np.sqrt(den[ok]))
    return out


def kind(state):
    """Kind of a measurement for the reduction, from the state of the instrument in the logbook."""
    if state.get("heavy_shutter", "open") != "open" or state.get("shutter") != "open":
        return "shutter closed"
    return {"empty_beam": "empty beam", "d2o": "solvent"}.get(state.get("sample"), "sample")

description = 'NICOS startup setup'
group = 'lowlevel'

# At ESS the startup setup stays empty and the instrument setups are chosen in the "Instrument Setup" panel. The
# twin loads its basic setup at once (all the devices of the twin), so that a first session needs no setup choice.
includes = ['loki']

startupcode = '''
from nicos.core import SIMULATION
if Exp._mode != SIMULATION:
    try:
        SetMode('master')
        SetDetectors(det)
    except Exception as err:
        printwarning('could not prepare the session: %s' % err)
printinfo("============================================================")
printinfo("LoKI digital twin (ESS small-angle neutron scattering), first version.")
printinfo("Devices: heavy_shutter, fast_shutter, collimation, sample_holder, det.")
printinfo("1. Your experiment:  NewExperiment(1234, 'silica spheres')   (or the Experiment panel)")
printinfo("2. Measure:          move(heavy_shutter, 'Open', fast_shutter, 'Open')")
printinfo("                     with nexusfile_open('silica spheres, 10 min'):")
printinfo("                         count(t=600)")
printinfo("Files (I(Q) per detector bank): <dataroot>/loki/<year>/<proposal>/raw/")
printinfo("============================================================")
'''

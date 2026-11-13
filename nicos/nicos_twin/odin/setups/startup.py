description = 'NICOS startup setup'
group = 'lowlevel'

# At ESS the startup setup stays empty and the instrument setups are chosen in the "Setup" panel. The twin loads
# its basic setup at once (all the devices of the twin), so that a first session needs no setup choice.
includes = ['odin']

startupcode = '''
from nicos.core import SIMULATION
if Exp._mode != SIMULATION:
    try:
        SetMode('master')
        SetDetectors(det)
        import os
        if os.environ.get('TWIN_EPICS') == '1':     # the sample stage through its EPICS motor records
            AddSetup('sample_stage')
    except Exception as err:
        printwarning('could not prepare the session: %s' % err)
printinfo("============================================================")
printinfo("ODIN digital twin (ESS neutron imaging).")
printinfo("Devices: choppers, wfm_delta, shutter, pinhole, diffuser, stage_x, stage_rot, load, sample_holder, det.")
printinfo("Camera (white-beam imaging): radiograph(t, title), tomography(t, step)")
printinfo("1. Your proposal:    tab Experiment, Find my proposal, choose it, Apply   (script: NewExperiment(1234, 'title'))")
printinfo("2. Measure:          move(shutter, 'open', stage_x, 500)")
printinfo("                     with nexusfile_open('open beam'):")
printinfo("                         count(t=10)")
printinfo("Files: <dataroot>/odin/<year>/<proposal>/raw/  (see Exp.proposalpath)")
printinfo("============================================================")
'''

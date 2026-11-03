description = 'startup setup of the ODIN digital twin'
group = 'lowlevel'

includes = ['odin']

startupcode = '''
from nicos.core import SIMULATION
if Exp._mode != SIMULATION:
    try:
        SetMode('master')
        if not Exp.proposal:
            NewExperiment(0, 'ODIN digital twin session')
        SetDetectors(det)
    except Exception as err:
        printwarning('could not prepare the session: %s' % err)
printinfo("============================================================")
printinfo("ODIN digital twin. Devices: choppers, wfm_delta, shutter, pinhole, diffuser, stage_x, stage_rot.")
printinfo("Example:  move(shutter, 'open', stage_x, 500); count(t=10)")
printinfo("The data files (NeXus, ESS format) are written by the twin to McStas_runs/twin/odin/nicos/.")
printinfo("============================================================")
'''

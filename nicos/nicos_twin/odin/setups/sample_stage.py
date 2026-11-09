description = 'sample stage of ODIN through its EPICS motor records (start_nicos.py --epics)'
group = 'optional'

# As at ESS: the motor class of ESS on the motor records of the real instrument (names written in the real ODIN file),
# served here by the soft IOC of the twin (epics/ioc.py), which moves the twin. Loaded by the startup code after the
# switch to master mode (an EPICS device created in slave mode stays in slave mode: EpicsDevice._setMode of NICOS
# does not pass the mode on), as a setup chosen in the Setup panel at ESS.
devices = dict(
    stage_x = device('nicos_ess.devices.epics.pva.motor.EpicsMotor',
        description = 'horizontal sample translation (out of the beam: 500 mm); EPICS motor record',
        motorpv = 'ODIN-SpSt1:MC-LinY-01:Mtr', monitor = True, pva = True, has_powerauto = False,
        has_errormsg = False, has_errorbit = False, has_reseterror = False,
    ),
    stage_rot = device('nicos_ess.devices.epics.pva.motor.EpicsMotor',
        description = 'sample rotation about the vertical axis; EPICS motor record',
        motorpv = 'ODIN-SpSt1:MC-RotZ-01:Mtr', monitor = True, pva = True, has_powerauto = False,
        has_errormsg = False, has_errorbit = False, has_reseterror = False,
    ),
)

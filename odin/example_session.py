# Example session script for the virtual ODIN console (NICOS command syntax).
#   python twin_server.py --instrument odin --session example     (first terminal, in twin/)
#   python twin_console.py odin/example_session.py                 (second terminal, in twin/)
# The NeXus files are written to McStas_runs/twin/odin/example/; reduce them afterwards in the browser
# (page ODIN_virtual.ipynb) or in a notebook (odin_reduction.reduce).

status()

# 1. Dark run: shutter closed (it is closed at start-up)
count(10, title="dark")

# 2. Open beam: sample moved out of the beam
move(shutter, "open", stage_x, 0.5)
count(10, title="open beam")

# 3. Deliberate mistake: a pinhole that does not exist -> the instrument refuses
try:
    move(pinhole, 0.025)
except InstrumentError as e:
    print("refused:", e)

# 4. Sample in the beam
move(stage_x, 0.0)
count(10, title="iron plate")

# 5. Short rotation scan (3 angles)
scan(stage_rot, 0, 30, 3, t=5, title="rotation test")

log()

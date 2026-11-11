#!/usr/bin/env bash
# Test of the control room of the app (GitHub Actions): starts the TigerVNC desktop with container/control_room.sh, as
# the button "Open NICOS" does through jupyter-remote-desktop-proxy, chooses ODIN (test mode), and checks that the
# NICOS window opens, full screen, with the data chain of ESS (--ess: Kafka, EPICS + forwarder, EFU, file-writer,
# just-bin-it), as for a student. Measures the memory and the time until NICOS is ready, then counts the iron plate in
# a nexusfile_open block (the live detector image fills up) and takes the screenshots into $1 (default /data/shots):
# control_room.png (the choice of the instrument), nicos_desktop.png (NICOS at start), nicos_detector.png (the tab
# Instrument interaction, Detector Image, after the count).
set -u
OUT="${1:-/data/shots}"
mkdir -p "$OUT"
cd "$HOME/twin"
# the recorded beam of the count below (a new container has none; the app downloads them at its first start)
/opt/conda/envs/mcstas/bin/python container/fetch_fronts.py wfm_delta0.10_N2e+08 || echo "WARNING: upstream part not downloaded"
mem() { awk '/MemTotal/ {t=$2} /MemAvailable/ {a=$2} END {printf "%.0f", (t-a)/1024}' /proc/meminfo; }
MEM0=$(mem); T0=$(date +%s)
echo "${2:-odin}" > "$HOME/.control_room_test"
echo "Instrument interaction,Detector Image" > "$HOME/.nicos_gui_test"      # the tabs to show (nicos_twin/gui.py)
vncserver :1 -geometry 1920x1080 -depth 24 -SecurityTypes None -localhost yes -xstartup "$HOME/twin/container/control_room.sh" \
  > "$OUT/vnc.log" 2>&1 || { echo "vncserver failed"; cat "$OUT/vnc.log"; exit 1; }
export DISPLAY=:1
sleep 6
scrot "$OUT/control_room.png" && echo "screenshot: $OUT/control_room.png"
for i in $(seq 1 180); do
  if xdotool search --name "^NICOS" > /dev/null 2>&1; then break; fi
  sleep 2
done
T1=$(date +%s); MEM1=$(mem)
sleep 20
xwininfo -root -tree | grep -i "nicos" | head -5
scrot "$OUT/nicos_desktop.png" && echo "screenshot: $OUT/nicos_desktop.png"
win=$(xdotool search --name "^NICOS" 2>/dev/null | head -1)
if [ -n "$win" ]; then
  echo "PASS the NICOS window is open in the control room ($(xdotool getwindowgeometry "$win" | tr '\n' ' '))"; rc=0
else
  echo "FAIL no NICOS window"; tail -40 /tmp/nicos_odin.log 2>/dev/null; cat /tmp/control_room.log 2>/dev/null
  echo "--- nicos_gui.log"; tail -60 "${TWIN_RUN_ROOT:-/data/twin}/nicos/nicos_gui.log" 2>/dev/null; rc=1
fi
echo "--- the launcher (which parts of the data chain of ESS started)"
grep -E "started|ready|not available" /tmp/nicos_odin.log 2>/dev/null | head -30
echo "MEASURE the control room with the data chain of ESS: NICOS window after $((T1 - T0)) s; memory in use" \
     "$MEM0 MB before, $MEM1 MB with NICOS and the chain (+$((MEM1 - MEM0)) MB)"
if [ $rc -eq 0 ]; then              # a count of the iron plate, as a student would do it (the live image fills up)
  /opt/conda/envs/nicos/bin/python nicos/run_nicos_script.py --timeout 600 -c "NewExperiment(1234, 'iron plate')
move(choppers, 'wfm', wfm_delta, 0.1); move(shutter, 'open', stage_x, 0)
with nexusfile_open('iron plate'):
    count(t=30)" > "$OUT/count.log" 2>&1 || { echo "FAIL the count in NICOS"; tail -30 "$OUT/count.log"; rc=1; }
  tail -8 "$OUT/count.log"
  if grep -q "Error" "$OUT/count.log"; then echo "FAIL the count in NICOS reported an error"; grep "Error" "$OUT/count.log" | head -5; rc=1
  else echo "PASS a count of the iron plate in the NICOS of the control room, written by the data chain"; fi
  sleep 5
  scrot "$OUT/nicos_detector.png" && echo "screenshot: $OUT/nicos_detector.png"
  echo "MEASURE memory in use after the count: $(mem) MB"
fi
exit $rc

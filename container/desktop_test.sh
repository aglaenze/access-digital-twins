#!/usr/bin/env bash
# Test of the control room of the app (GitHub Actions): starts the TigerVNC desktop with container/control_room.sh, as
# the button "Open NICOS" does through jupyter-remote-desktop-proxy, chooses ODIN (test mode), and checks that the
# NICOS window opens, full screen. Screenshots into $1 (default /data/shots): control_room.png (the choice of the
# instrument), nicos_desktop.png (NICOS).
set -u
OUT="${1:-/data/shots}"
mkdir -p "$OUT"
cd "$HOME/twin"
echo "${2:-odin}" > "$HOME/.control_room_test"
vncserver :1 -geometry 1600x900 -depth 24 -SecurityTypes None -localhost yes -xstartup "$HOME/twin/container/control_room.sh" \
  > "$OUT/vnc.log" 2>&1 || { echo "vncserver failed"; cat "$OUT/vnc.log"; exit 1; }
export DISPLAY=:1
sleep 6
scrot "$OUT/control_room.png" && echo "screenshot: $OUT/control_room.png"
for i in $(seq 1 120); do
  if xdotool search --name "^NICOS" > /dev/null 2>&1; then break; fi
  sleep 2
done
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
exit $rc

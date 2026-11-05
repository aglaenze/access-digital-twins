#!/usr/bin/env bash
# Test of the NICOS window on the desktop of the container (GitHub Actions): starts a TigerVNC desktop (the one that
# the JupyterLab launcher "Desktop" opens in the browser), the ODIN twin with NICOS and its window, and takes a
# screenshot of the desktop into $1 (default /data/shots).
set -u
OUT="${1:-/data/shots}"
mkdir -p "$OUT"
cd "$HOME/twin"
vncserver :1 -geometry 1600x900 -depth 24 -SecurityTypes None -localhost yes -xstartup /usr/bin/startxfce4 \
  > "$OUT/vnc.log" 2>&1 || { echo "vncserver failed"; cat "$OUT/vnc.log"; exit 1; }
export DISPLAY=:1
sleep 8
python nicos/start_nicos.py --instrument "${2:-odin}" --background --session desktop_test > "$OUT/nicos.log" 2>&1 &
for i in $(seq 1 90); do
  if xwininfo -root -tree 2>/dev/null | grep -qi "nicos"; then break; fi
  sleep 2
done
sleep 25
xwininfo -root -tree | grep -i "nicos" | head -5
scrot "$OUT/nicos_desktop.png" && echo "screenshot: $OUT/nicos_desktop.png"
if xwininfo -root -tree | grep -qi "nicos"; then echo "PASS the NICOS window is open on the desktop"; rc=0;
else echo "FAIL no NICOS window"; tail -50 "$OUT/nicos.log"; rc=1; fi
tail -30 "${TWIN_RUN_ROOT}/nicos/nicos_gui.log" 2>/dev/null
exit $rc

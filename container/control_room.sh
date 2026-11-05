#!/bin/sh
# The "desktop" of the app for the MSc level and the free beamtime: not a Linux desktop, the control room of the
# instrument. Started by jupyter-remote-desktop-proxy (JUPYTER_REMOTE_DESKTOP_PROXY_XSTARTUP, Containerfile) when the
# student clicks "Open NICOS" in the app: choice of the instrument (control_room.py), then the NICOS window alone,
# full screen and logged in; closing it stops NICOS and brings the choice back. No terminal, no files.
cd "$HOME/twin" || exit 1
xsetroot -solid "#1D2433" 2>/dev/null
xfwm4 --compositor=off >/dev/null 2>&1 &                      # window manager (title bars, moving, closing)
# test mode (GitHub Actions, desktop_test.sh): the instrument chosen by itself, from this file
[ -f "$HOME/.control_room_test" ] && { export CONTROL_ROOM_INSTRUMENT=$(cat "$HOME/.control_room_test"); export CONTROL_ROOM_DELAY=10; rm -f "$HOME/.control_room_test"; }
NICOS_PY=/opt/conda/envs/nicos/bin/python
TWIN_PY=/opt/conda/envs/mcstas/bin/python
while true; do
  instr=$($NICOS_PY container/control_room.py 2>/tmp/control_room.log)
  [ -z "$instr" ] && { sleep 1; continue; }
  $TWIN_PY nicos/start_nicos.py --instrument "$instr" --until-gui-closes --session nicos \
    > "/tmp/nicos_$instr.log" 2>&1 &
  pid=$!
  for i in $(seq 1 180); do                                   # the NICOS window, full screen as soon as it appears
    win=$(xdotool search --name "^NICOS" 2>/dev/null | head -1)
    if [ -n "$win" ]; then
      sleep 1
      xdotool windowmove "$win" 0 0 windowsize "$win" 100% 100% 2>/dev/null
      break
    fi
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
  wait "$pid"
  unset CONTROL_ROOM_INSTRUMENT                               # (test mode: only the first time)
done

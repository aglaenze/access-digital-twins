#!/usr/bin/env bash
# Runs on the GitHub runner (not in the container): JupyterLab of the container, its "Desktop" opened in Chrome
# (noVNC, jupyter-remote-desktop-proxy), the NICOS window of ODIN started on that desktop, screenshots in ./shots.
#   bash container/browser_desktop_test.sh twin:test
set -u
IMAGE="${1:-twin:test}"
mkdir -p shots && chmod 777 shots
# (bash -c: a first word "jupyter" would be taken by start.sh as its own entry point, with a random token)
docker run -d --name jl -p 8888:8888 -e TWIN_MPI=4 "$IMAGE" \
  bash -c "exec jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --IdentityProvider.token=test --ServerApp.root_dir=/home/mambauser/twin"
for i in $(seq 1 60); do curl -sf "http://localhost:8888/api/status?token=test" > /dev/null && break; sleep 2; done
echo "desktop page: HTTP $(curl -s -o /dev/null -w '%{http_code}' "http://localhost:8888/desktop/?token=test")"
CHROME=$(command -v google-chrome || command -v chromium || command -v chromium-browser)
shot() {  # $1: file, $2: URL
  timeout 120 "$CHROME" --headless=new --no-sandbox --disable-gpu --window-size=1600,1000 --hide-scrollbars \
    --virtual-time-budget=25000 --screenshot="$1" "$2" > /dev/null 2>&1; ls -la "$1" 2>/dev/null
}
shot shots/catalogue.png "http://localhost:8888/voila/render/Catalogue.ipynb?token=test"
shot shots/desktop_empty.png "http://localhost:8888/desktop/?token=test"     # starts the VNC desktop
DISP=$(docker exec jl bash -c 'ls /tmp/.X11-unix 2>/dev/null | head -1 | tr -d X')
echo "VNC display: :${DISP}"
if [ -n "$DISP" ]; then
  docker exec -d -e DISPLAY=":${DISP}" jl bash -c \
    'cd /home/mambauser/twin && python nicos/start_nicos.py --instrument odin --background --session browser_test > /tmp/nicos.log 2>&1'
  sleep 120
  shot shots/desktop_nicos.png "http://localhost:8888/desktop/?token=test"
  docker exec jl bash -c 'tail -20 /tmp/nicos.log; xwininfo -display ":'"${DISP}"'" -root -tree | grep -i nicos | head -3' || true
fi
docker logs jl 2>&1 | tail -20
docker rm -f jl > /dev/null

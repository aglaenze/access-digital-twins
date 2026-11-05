#!/usr/bin/env bash
# The digital twins on your own computer (macOS, Linux), as an app: downloads the container image the first time,
# starts it, and opens the catalogue of exercises in your web browser. Needs Podman (free, recommended) or Docker.
#   bash run_twin.sh            # then work in the browser; Ctrl+C here to stop
# Your files stay in the volume "twin-data" (kept between sessions). Apple Silicon (M1-M4): the image is built for
# Intel/AMD processors and runs emulated, more slowly.
set -e
IMAGE="${TWIN_IMAGE:-ghcr.io/aglaenze/access-digital-twins:latest}"
PORT="${TWIN_PORT:-8888}"
ENGINE=$(command -v podman || command -v docker || true)
if [ -z "$ENGINE" ]; then
  echo "Install Podman (https://podman.io) or Docker first."; exit 1
fi
TOKEN=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 24)
echo "Getting the image (several GB the first time)..."
"$ENGINE" pull "$IMAGE"
URL="http://localhost:${PORT}/voila/render/Catalogue.ipynb?token=${TOKEN}"
( for i in $(seq 1 90); do
    if curl -sf "http://localhost:${PORT}/api/status?token=${TOKEN}" > /dev/null 2>&1; then
      echo "Open: $URL"; (command -v open > /dev/null && open "$URL") || (command -v xdg-open > /dev/null && xdg-open "$URL") || true
      break
    fi
    sleep 2
  done ) &
exec "$ENGINE" run --rm -it -p "${PORT}:8888" -v twin-data:/data "$IMAGE" \
  bash -c "python container/fetch_fronts.py || true; exec jupyter lab --ip=0.0.0.0 --port=8888 --no-browser \
           --IdentityProvider.token=${TOKEN} --ServerApp.root_dir=/home/mambauser/twin"

#!/usr/bin/env bash
# The app (Electron) in "container" mode against a freshly built image, on a Linux runner of GitHub Actions:
# creates an account, opens the catalogue, the ODIN BSc page (answers a question), the MSc notebook; screenshots.
#   bash app/ci_selftest.sh <image> <folder for the screenshots>
set -euo pipefail
IMAGE="$1"; OUT="$2"
cd "$(dirname "$0")"
sudo apt-get install -y -qq xvfb > /dev/null
npm ci --no-audit --no-fund
node node_modules/electron/install.js            # the Electron binary (in case install scripts were skipped)
mkdir -p "$OUT"
DATA="$(mktemp -d)"
TWIN_BACKEND=container TWIN_ENGINE=docker TWIN_IMAGE="$IMAGE" TWIN_APP_DATA="$DATA" TWIN_APP_SELFTEST="$OUT" \
  timeout 3600 xvfb-run -a -s "-screen 0 1600x1000x24" npx electron . --no-sandbox || rc=$?
cat "$OUT/selftest.log" || true
echo "--- server log of the container"; docker logs ess-twins-app 2>&1 | tail -30 || true
grep -q "SELFTEST PASSED" "$OUT/selftest.log"

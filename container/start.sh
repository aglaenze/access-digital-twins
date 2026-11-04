#!/usr/bin/env bash
# Entry point of the container (run inside the activated "mcstas" environment, in /home/mambauser/twin).
#   start.sh jupyter   (default) JupyterLab on port 8888: notebooks, pages (Voilà extension), terminal
#   start.sh voila     student page only (Voilà) on port 8866
#   start.sh nicos     twin server + NICOS cache, poller, daemon (port 1301) in the foreground
#   start.sh test      smoke test (used by GitHub Actions)
#   start.sh <command> any other command
# The upstream McStas parts are downloaded on first start into $TWIN_RUN_ROOT (a volume, so only once).
set -e
cd "$HOME/twin"
fetch() { python container/fetch_fronts.py || echo "WARNING: upstream parts not downloaded (network?)"; }
case "${1:-jupyter}" in
  jupyter) fetch; exec jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --ServerApp.root_dir="$HOME/twin" ;;
  voila)   fetch; exec voila odin/ODIN_virtual.ipynb --Voila.ip=0.0.0.0 --port=8866 --no-browser ;;
  nicos)   fetch; exec python nicos/start_nicos.py --instrument "${TWIN_INSTRUMENT:-odin}" --no-gui --background --session "${TWIN_SESSION:-nicos}" ;;
  test)    exec python container/smoke_test.py ;;
  *)       exec "$@" ;;
esac

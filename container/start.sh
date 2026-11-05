#!/usr/bin/env bash
# Entry point of the container (run inside the activated "mcstas" environment, in /home/mambauser/twin).
#   start.sh jupyter   (default) the app on port 8888: the catalogue of exercises as start page (Voilà), notebooks
#                      opened alone (no file browser), NICOS in the control room; extra arguments go to the server
#                      (e.g. --IdentityProvider.token=...). Teachers: JupyterLab is at /lab.
#   start.sh voila     web pages only (Voilà) on port 8866: the catalogue at /voila/render/Catalogue.ipynb
#   start.sh nicos     twin server + NICOS cache, poller, daemon (port 1301) in the foreground
#                      (-e TWIN_LIVE=1: live data, Kafka broker + just-bin-it, as at ESS)
#   start.sh test      smoke test (used by GitHub Actions)
#   start.sh <command> any other command
# The upstream McStas parts are downloaded on first start into $TWIN_RUN_ROOT (a volume, so only once).
set -e
cd "$HOME/twin"
fetch() { python container/fetch_fronts.py || echo "WARNING: upstream parts not downloaded (network?)"; }
case "${1:-jupyter}" in
  jupyter) fetch
           mkdir -p "$TWIN_RUN_ROOT/work" && ln -sfn "$TWIN_RUN_ROOT/work" "$HOME/twin/work"   # students' notebooks, kept
           export JUPYTER_CONFIG_PATH="$HOME/twin/container/app_config"                        # no file browser
           [ $# -gt 0 ] && shift
           exec jupyter server --ip=0.0.0.0 --port=8888 --no-browser --ServerApp.root_dir="$HOME/twin" \
                --ServerApp.default_url=/voila/render/Catalogue.ipynb "$@" ;;
  voila)   fetch; exec voila . --Voila.ip=0.0.0.0 --port=8866 --no-browser ;;
  nicos)   fetch; exec python nicos/start_nicos.py --instrument "${TWIN_INSTRUMENT:-odin}" --no-gui --background --session "${TWIN_SESSION:-nicos}" ${TWIN_LIVE:+--live} ;;
  test)    exec python container/smoke_test.py ;;
  *)       exec "$@" ;;
esac

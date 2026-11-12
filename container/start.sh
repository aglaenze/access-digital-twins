#!/usr/bin/env bash
# Entry point of the container (run inside the activated "mcstas" environment, in /home/mambauser/twin).
#   start.sh jupyter   (default) the server of the app (app/, Electron) on port 8888: pages (Voilà), notebooks
#                      opened alone (no file browser), NICOS in the control room; extra arguments go to the server
#                      (e.g. --IdentityProvider.token=...). Teachers: JupyterLab is at /lab.
#   start.sh voila     web pages only (Voilà) on port 8866
#   start.sh web       the online version for a class (no app): start page + guided pages (Voilà) on port $PORT (7860)
#   start.sh nicos     twin server + NICOS cache, poller, daemon (port 1301) in the foreground
#                      (-e TWIN_LIVE=1: live data, Kafka broker + just-bin-it, as at ESS)
#   start.sh test      smoke test (used by GitHub Actions)
#   start.sh <command> any other command
# The upstream McStas parts are downloaded on first start into $TWIN_RUN_ROOT (a volume, so only once).
set -e
cd "$HOME/twin"
fetch() { python container/fetch_fronts.py || echo "WARNING: upstream parts not downloaded (network?)"; }
case "${1:-jupyter}" in
  web)     # the online version, for a class without the app: Voila alone (the guided pages, no notebook, no NICOS,
           # nothing that runs code sent by the browser); a start page asks for the name of the student (web_user.py)
           fetch
           export JUPYTER_PATH="$HOME/twin/container/app_data"                                 # Voila template, start page
           export TWIN_WEB=1
           python container/web_warmup.py || echo "WARNING: warm-up failed (the first count will be slow)"
           [ $# -gt 0 ] && shift
           exec voila --no-browser --Voila.ip=0.0.0.0 --port="${PORT:-7860}" --template=twin                 --Voila.root_dir="$HOME/twin" --Voila.tornado_settings="{'websocket_ping_interval': 30000}"                 --MappingKernelManager.cull_idle_timeout=7200 --MappingKernelManager.cull_interval=300 "$@" ;;
  jupyter) fetch
           mkdir -p "$TWIN_RUN_ROOT/work" && ln -sfn "$TWIN_RUN_ROOT/work" "$HOME/twin/work"   # students' notebooks, kept
           export JUPYTER_CONFIG_PATH="$HOME/twin/container/app_config"                        # no file browser
           export JUPYTER_PATH="$HOME/twin/container/app_data"                                 # Voila template (formulas)
           export JUPYTERLAB_SETTINGS_DIR="$HOME/twin/container/app_settings"                # every cell kept in the page
           export PYTHONPATH="$HOME/twin/container${PYTHONPATH:+:$PYTHONPATH}"                 # twin_app.py: API of the app
           [ $# -gt 0 ] && shift
           exec jupyter server --ip=0.0.0.0 --port=8888 --no-browser --ServerApp.root_dir="$HOME/twin" \
                --ServerApp.jpserver_extensions="{'twin_app': True}" \
                ${TWIN_KERNEL_POOL:+--ServerApp.kernel_manager_class=twin_kernels.PooledKernelManager} \
                --ServerApp.default_url=/lab "$@" ;;
  voila)   fetch; exec voila . --Voila.ip=0.0.0.0 --port=8866 --no-browser ;;
  nicos)   fetch; exec python nicos/start_nicos.py --instrument "${TWIN_INSTRUMENT:-odin}" --no-gui --background --session "${TWIN_SESSION:-nicos}" ${TWIN_LIVE:+--live} ;;
  test)    exec python container/smoke_test.py ;;
  *)       exec "$@" ;;
esac

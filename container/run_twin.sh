#!/usr/bin/env bash
# The ESS digital twins as an app on your own computer (macOS, Linux).
#
# First time: in a terminal, `bash run_twin.sh`. It installs the app "ESS digital twins" (macOS: on the desktop and in
# Applications; Linux: on the desktop and in the menu), downloads the twins (several GB, once) and opens them. After
# that: double-click the app. Closing its window stops the twins. Your work is kept between sessions (volume
# "twin-data"). The image exists for Intel/AMD and for ARM (Apple Silicon M1-M4): the right one is downloaded.
#
# Needs Podman Desktop (free, recommended) or Docker Desktop. Teachers: TWIN_IMAGE, TWIN_PORT.
APP="ESS digital twins"
IMAGE="${TWIN_IMAGE:-ghcr.io/aglaenze/access-digital-twins:latest}"
PORT="${TWIN_PORT:-8888}"
CONTAINER=ess-twins
HOME_DIR="$HOME/.ess-twins"
RAW=https://raw.githubusercontent.com/aglaenze/access-digital-twins/main/container
export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin:/opt/podman/bin:/Applications/Docker.app/Contents/Resources/bin"
MAC=0; [ "$(uname)" = Darwin ] && MAC=1

say() {   # a message window (the app has no terminal)
  if [ $MAC = 1 ]; then osascript -e "display dialog \"$1\" with title \"$APP\" buttons {\"OK\"} default button 1" > /dev/null 2>&1
  elif command -v zenity > /dev/null; then zenity --info --title="$APP" --text="$1" 2> /dev/null
  else echo "$1"; fi
}

# 1. Install (once): this script in ~/.ess-twins, and an app that starts it without a terminal
mkdir -p "$HOME_DIR"
SELF="$HOME_DIR/run_twin.sh"
if [ "$(cd "$(dirname "$0")" && pwd)/$(basename "$0")" != "$SELF" ]; then
  cp "$0" "$SELF" && chmod +x "$SELF"
  curl -sfL "$RAW/app_icon.png" -o "$HOME_DIR/app_icon.png" || true
  if [ $MAC = 1 ]; then
    for dest in "$HOME/Applications" "$HOME/Desktop"; do
      B="$dest/$APP.app/Contents"
      mkdir -p "$B/MacOS" "$B/Resources"
      printf '#!/bin/bash\nexec bash "%s"\n' "$SELF" > "$B/MacOS/run" && chmod +x "$B/MacOS/run"
      cat > "$B/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
<key>CFBundleName</key><string>$APP</string><key>CFBundleExecutable</key><string>run</string>
<key>CFBundleIdentifier</key><string>eu.access.ess-twins</string><key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleIconFile</key><string>app_icon.icns</string>
</dict></plist>
EOF
      if [ -f "$HOME_DIR/app_icon.png" ] && command -v sips > /dev/null; then
        sips -s format icns "$HOME_DIR/app_icon.png" --out "$B/Resources/app_icon.icns" > /dev/null 2>&1 || true
      fi
    done
  else
    D="[Desktop Entry]
Type=Application
Name=$APP
Comment=The ESS instruments ODIN and LoKI, virtual
Exec=bash \"$SELF\"
Icon=$HOME_DIR/app_icon.png
Terminal=false
Categories=Education;Science;"
    mkdir -p "$HOME/.local/share/applications"
    echo "$D" > "$HOME/.local/share/applications/ess-twins.desktop"
    if [ -d "$HOME/Desktop" ]; then
      echo "$D" > "$HOME/Desktop/ess-twins.desktop" && chmod +x "$HOME/Desktop/ess-twins.desktop"
      command -v gio > /dev/null && gio set "$HOME/Desktop/ess-twins.desktop" metadata::trusted true 2> /dev/null
    fi
  fi
fi

# 2. The container engine (Podman or Docker), running
ENGINE=$(command -v podman || command -v docker || true)
if [ -z "$ENGINE" ]; then
  say "Please install Podman Desktop first (free): https://podman-desktop.io  Then open '$APP' again."; exit 1
fi
ready() { "$ENGINE" info > /dev/null 2>&1; }
if ! ready; then
  case "$ENGINE" in
    *podman) "$ENGINE" machine start > /dev/null 2>&1 ;;
    *) [ $MAC = 1 ] && open -a Docker ;;
  esac
  for i in $(seq 1 60); do ready && break; sleep 3; done
  ready || { say "Podman (or Docker) does not start. Open Podman Desktop, start it, then try again."; exit 1; }
fi

# 3. The twins: the image (downloaded the first time, updated when there is a new one), the container
STATE="$HOME_DIR/token"
if [ -n "$("$ENGINE" ps -q --filter "name=^${CONTAINER}$")" ] && [ -f "$STATE" ]; then
  TOKEN=$(cat "$STATE")
else
  "$ENGINE" rm -f "$CONTAINER" > /dev/null 2>&1
  if ! "$ENGINE" image inspect "$IMAGE" > /dev/null 2>&1; then
    say "First start: the twins are downloaded now (several GB, 10-30 minutes). The app opens by itself at the end."
    "$ENGINE" pull "$IMAGE" || { say "The download did not finish (network?). Open '$APP' to try again."; exit 1; }
  else
    ( "$ENGINE" pull -q "$IMAGE" > /dev/null 2>&1 & )         # update, for next time
  fi
  TOKEN=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 24)
  echo "$TOKEN" > "$STATE"
  "$ENGINE" run -d --rm --name "$CONTAINER" -p "127.0.0.1:${PORT}:8888" -v twin-data:/data "$IMAGE" \
    jupyter "--IdentityProvider.token=$TOKEN" > /dev/null
fi
URL="http://localhost:${PORT}/?token=${TOKEN}"
for i in $(seq 1 120); do curl -sf "http://localhost:${PORT}/api/status?token=${TOKEN}" > /dev/null && break; sleep 2; done

# 4. The window of the app (Chrome, Edge or Chromium in app mode: no address bar, no tabs); closing it stops the twins
BROWSER=""
for b in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
         "/Applications/Chromium.app/Contents/MacOS/Chromium" "$(command -v google-chrome || true)" "$(command -v chromium || true)" \
         "$(command -v chromium-browser || true)" "$(command -v microsoft-edge || true)"; do
  [ -n "$b" ] && [ -x "$b" ] && { BROWSER="$b"; break; }
done
if [ -n "$BROWSER" ]; then
  "$BROWSER" --app="$URL" --user-data-dir="$HOME_DIR/window" --no-first-run --no-default-browser-check \
    --window-size=1400,900 > /dev/null 2>&1
  "$ENGINE" stop -t 5 "$CONTAINER" > /dev/null 2>&1
else   # (no Chrome-like browser: a tab of the default browser, e.g. Safari; the twins stop when the computer does)
  if [ $MAC = 1 ]; then open "$URL"; else xdg-open "$URL"; fi
fi

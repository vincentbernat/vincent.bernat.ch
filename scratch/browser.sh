#!/bin/sh
# Starts the headless browser the recorder drives. Run it in its own terminal
# and leave it there; scratch/record.mjs connects to it over the DevTools
# protocol on port 9222.
#
#   sh scratch/browser.sh
#
# The flatpak only gets access to scratch/, where it keeps its profile. It
# reaches everything else through scratch/serve.mjs over HTTP.

set -eu

repo=$(cd "$(dirname "$0")/.." && pwd)
port=${MSTP_CDP_PORT:-9222}
mkdir -p "$repo/scratch/out" "$repo/scratch/chromium-profile"

echo "starting headless chromium on port $port"
echo "log: scratch/out/chromium.log"

exec flatpak run \
  --filesystem="$repo/scratch" \
  --command=chromium \
  io.github.ungoogled_software.ungoogled_chromium \
  --headless=new \
  --remote-debugging-port="$port" \
  --remote-allow-origins='*' \
  --user-data-dir="$repo/scratch/chromium-profile" \
  --disable-gpu \
  --no-first-run \
  --no-default-browser-check \
  --hide-scrollbars \
  --force-device-scale-factor=1 \
  --force-color-profile=srgb \
  --window-size=1920,1080 \
  >"$repo/scratch/out/chromium.log" 2>&1

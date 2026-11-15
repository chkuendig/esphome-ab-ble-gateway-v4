#!/usr/bin/env bash
# Compile the firmware with the pinned ESPHome Docker image.
# Output: build/<config name>.ota.bin (app-only image for OTA updates).
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
config=${1:-ab-ble-gateway-v4.yaml}
cache=${BUILD_CACHE_DIR:-$root/.cache}
image=ghcr.io/esphome/esphome:2026.10.2@sha256:4a918585150e95e7675be84a347384ff308fde1bd32d0e4472666e1252cc0e8f
slot_size=$((0x100000))

mkdir -p "$cache"/{platformio,cache,uv-cache,data} "$root/build"
cache=$(cd -- "$cache" && pwd)
docker run --rm --user "$(id -u):$(id -g)" \
  -e PLATFORMIO_CORE_DIR=/cache/platformio \
  -e XDG_CACHE_HOME=/cache/cache \
  -e UV_CACHE_DIR=/cache/uv-cache \
  -e ESPHOME_DATA_DIR=/cache/data \
  -e PLATFORMIO_SETTING_ENABLE_TELEMETRY=no \
  -v "$root:/config" -v "$cache:/cache" -w /config \
  "$image" compile "$config"

name=$(basename "$config" .yaml)
built=$cache/data/build/$name/build/firmware.ota.bin
[[ -f "$built" ]] || { echo "$built not found" >&2; exit 1; }
cp "$built" "$root/build/$name.ota.bin"
size=$(stat -c %s "$root/build/$name.ota.bin")
printf 'build/%s.ota.bin: %d bytes, %d bytes free in a 1 MiB OTA slot\n' \
  "$name" "$size" $((slot_size - size))
(( size <= slot_size )) || { echo "Image does not fit the stock OTA slot" >&2; exit 1; }

#!/usr/bin/env bash
set -euo pipefail
proxy_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
build_config=${AB_BUILD_CONFIG:-xbg-proxy.yaml}
case "$build_config" in xbg-proxy.yaml|xbg-proxy-diagnostic.yaml) ;; *) exit 1 ;; esac
extra_mounts=()
# Optional local cache reuse when ignored private directories are symlinks.
if [[ -n "${XBG_SHARED_WORKSPACE:-}" ]]; then
  [[ "$XBG_SHARED_WORKSPACE" == /* && -d "$XBG_SHARED_WORKSPACE" ]] || exit 1
  extra_mounts=(-v "$XBG_SHARED_WORKSPACE:$XBG_SHARED_WORKSPACE")
fi
for runner in ${AB_CHECK_RUNNERS:-}; do
  runner_processes=$(docker top "$runner" -eo pid,comm) || exit 1
  if [[ "$runner_processes" == *Runner.Worker* ]]; then
    printf 'CI is active in %s; build deferred.\n' "$runner" >&2
    exit 1
  fi
done
mkdir -p "$proxy_root/private/uv-cache" "$proxy_root/private/cache" \
  "$proxy_root/private/platformio" "$proxy_root/private/data"
docker run --rm --name xbg-esphome-build --cpus 2 --memory 3g --user "$(id -u):$(id -g)" \
  -e UV_CACHE_DIR=/config/private/uv-cache \
  -e XDG_CACHE_HOME=/config/private/cache \
  -e PLATFORMIO_CORE_DIR=/config/private/platformio \
  -e ESPHOME_DATA_DIR=/config/private/data \
  -e PLATFORMIO_SETTING_ENABLE_TELEMETRY=no \
  -v "$proxy_root:/config" "${extra_mounts[@]}" -w /config \
  ghcr.io/esphome/esphome@sha256:4a918585150e95e7675be84a347384ff308fde1bd32d0e4472666e1252cc0e8f \
  compile "$build_config"

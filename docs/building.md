# Build a firmware image

Run commands from the repository root. The standard configuration is `ab-ble-gateway-v4.yaml`; no Wi-Fi password or shared API key needs to be compiled into it.

## Pinned Docker build

Install Docker, then run:

```sh
./build.sh
```

The script uses a digest-pinned ESPHome Docker image (ESPHome 2026.10.2) and keeps its caches in gitignored `.cache/` (override with `BUILD_CACHE_DIR`). It copies the app-only image to:

```text
build/ab-ble-gateway-v4.ota.bin
```

## ESPHome CLI

With ESPHome 2026.10.2 installed:

```sh
esphome compile ab-ble-gateway-v4.yaml
```

With the default ESPHome data directory, the CLI writes (and prints as `Created: …`):

```text
.esphome/build/ab-ble-gateway-v4/build/firmware.ota.bin
```

The `build/`, `.cache/` and `.esphome/` directories are gitignored.

## Check the OTA image

The stock OTA slot is **0x100000 = 1,048,576 bytes (1 MiB)**. The complete app-only image must fit that slot:

```sh
wc -c < build/ab-ble-gateway-v4.ota.bin
```

Use the **app-only OTA image** (`ab-ble-gateway-v4.ota.bin` from the script, or `firmware.ota.bin` from the CLI) for OTA. A merged/factory image contains data intended for other flash addresses and must never be uploaded to an app-only OTA endpoint. This firmware keeps the stock partition layout, bootloader and NVS.

GitHub Actions also builds the firmware and reports image size. A successful build establishes compilation and size checks; follow the [migration guide](migrating-from-stock.md) before installing it.

## Validation scope

With ESPHome 2026.10.2 the image (Wi-Fi, Ethernet, Bluetooth proxy, serial proxy, stock recovery) is about **1,030,000 bytes**, leaving roughly 18 KB in the stock slot. Adding components can push it over; `build.sh` fails if the image no longer fits. A successful compile is not a hardware test.

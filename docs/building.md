# Build a firmware image

Run from the repository root. `ab-ble-gateway-v4.yaml` needs no compiled Wi-Fi password or shared API key.

## Docker

Install Docker, then run:

```sh
./build.sh
```

Uses digest-pinned ESPHome 2026.10.2. Cache: `.cache/` (override with `BUILD_CACHE_DIR`). App-only output:

```text
build/ab-ble-gateway-v4.ota.bin
```

## ESPHome CLI

With ESPHome 2026.10.2 installed:

```sh
esphome compile ab-ble-gateway-v4.yaml
```

Default output (printed as `Created: …`):

```text
.esphome/build/ab-ble-gateway-v4/build/firmware.ota.bin
```

`build/`, `.cache/` and `.esphome/` are gitignored.

## Check size and install

The complete app-only image must fit stock's **0x100000 = 1,048,576-byte (1 MiB)** OTA slot:

```sh
wc -c < build/ab-ble-gateway-v4.ota.bin
```

The image includes Wi-Fi, Ethernet, Bluetooth proxy, serial proxy and stock recovery: approximately **1,030,000 bytes**, leaving 18 KB. Adding components can exceed the slot; `build.sh` rejects oversized images. GitHub Actions also builds and reports size.

Upload only `ab-ble-gateway-v4.ota.bin` or the CLI's `firmware.ota.bin`. **Never upload a merged/factory image to an app-only OTA endpoint:** it targets other flash addresses. Firmware retains stock's partitions, bootloader and NVS. Follow the [migration guide](migrating-from-stock.md).

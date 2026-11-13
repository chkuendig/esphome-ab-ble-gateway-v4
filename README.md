# ESPHome — AB BLE Gateway V4

Reusable ESPHome firmware for the April Brother BLE Gateway V4: ESP32 Bluetooth
GATT connections alongside the existing Nordic advertising receiver.

**Development prototype. No installable release yet.** The development gateway
still runs stock firmware. The proposed ESPHome image requires a flash-layout
migration; it is not a drop-in upload for the vendor OTA endpoint. Do not flash
an application or merged factory image from this repository without a completed
migration and recovery procedure.

## Device settings stay on the device

The public YAML contains no Wi-Fi credentials, API key, MQTT broker or fixed
hardware address. Network credentials live in NVS, independently of the
application image. `ab_settings` can import existing personal Wi-Fi credentials
from the stock `storage` namespace into ESPHome's normal preferences. It also
reads the existing plaintext MQTT transport configuration and obtains the
source MAC from the ESP32. Unsupported MQTT configurations remain disabled.

The preferred migration is first-boot import: back up settings while stock
still runs, preserve NVS during installation, then let ESPHome copy the saved
credentials and reconnect. Verify the persisted settings and network before
accepting the firmware trial. Optional private pre-staging records can also be
prepared, but their writer and the partition migration are not implemented
yet. Do not confuse preparation with completed device provisioning.

API and OTA use a per-device key held in NVS, not a key compiled into public
firmware. A deliberate settings reset clears ESPHome settings and suppresses
stock reimport. No personal network is hardcoded as a reset fallback.

See [settings migration and publication rules](docs/SETTINGS-AND-MIGRATION.md).

## Current implementation

- Native ESPHome Bluetooth proxy: ESP32 scanning and one active GATT slot.
- Existing Nordic firmware and UART protocol retained, RX32/TX33 at 115200.
- Nordic advertisements currently use the stock MessagePack/MQTT transport.
  Native ESPHome delivery for Nordic is still under development.
- GPIO12 configuration button: ten-second hold resets settings; triple-click
  starts Wi-Fi SmartConfig. UART0 Improv provisioning is also enabled.
- Preserved stock image selection and a bounded trial watchdog, independently
  of ESPHome safe mode. These new ESPHome paths need live validation.

These are reusable components, but the hardware profile and recovery image
check currently target the inspected stock 1.5.13 application. Other V4 board
revisions and stock versions require verification; the marketing name does
not establish identical wiring.

## Documentation

- [Offline validation and remaining hardware tests](docs/VALIDATION.md)
- [Configuration button and reset behavior](docs/BUTTON-BEHAVIOR.md)
- [Hardware, Ethernet reset evidence and remaining recovery work](docs/HARDWARE-AND-RECOVERY.md)
- [Installed-image Ethernet evidence](tools/installed-network-evidence.json)

## Build and checks

`./build.sh` uses a pinned ESPHome 2026.10.2 Docker image and two compiler jobs.
It needs no `secrets.yaml`. Local caches and generated artifacts live under
ignored directories. Set `AB_CHECK_RUNNERS` to a space-separated list of CI
runner container names when building on a shared host; a busy or unreadable
runner prevents the build.

```sh
python3 -m unittest discover -s tests -v
g++ -std=c++17 -Wall -Wextra -Werror tests/gesture.cpp -o /tmp/ab-gesture-test
/tmp/ab-gesture-test
./build.sh
```

Never publish NVS images, full-flash backups, private staging records or older
personalized diagnostic builds. Even a generic binary needs a publication
check against known private values before upload. Compile success is not a
hardware acceptance test or evidence that a partition migration is safe.

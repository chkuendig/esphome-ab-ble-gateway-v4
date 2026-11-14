# ESPHome — AB BLE Gateway V4

Reusable ESPHome firmware for the April Brother BLE Gateway V4: ESP32 Bluetooth
GATT connections alongside the existing Nordic advertising receiver.

**Hardware-tested preview for the inspected stock profile.** See the
[preview release](https://github.com/chkuendig/esphome-ab-ble-gateway-v4/releases/tag/v0.1.0-preview.1)
for the app-only image and its exact validation limits. The compact native build
fits the inspected device's original 1 MiB OTA slots. Saved-network import, encrypted API/OTA, native Bluetooth delivery, GATT and
timed stock return have passed hardware trials. Home Assistant now reads the
plant battery through the proxy. MyCO2 is currently unavailable under both
stock and ESPHome; its reception remains unresolved. Use only an
app-only image through the verified migration procedure. Never upload a merged
factory image to the vendor OTA endpoint.

## Device settings stay on the device

The public YAML contains no Wi-Fi credentials, API key or fixed
hardware address. Network credentials live in NVS, independently of the
application image. `ab_settings` can import existing personal Wi-Fi credentials
from the stock `storage` namespace into ESPHome's normal preferences. No MQTT
client or broker configuration is included. Both receivers use ESPHome's
encrypted native Bluetooth API.

The preferred migration is first-boot import: back up settings while stock
still runs, preserve NVS during installation, then let ESPHome copy the saved
credentials and reconnect. Verify the persisted settings and network before
accepting the firmware trial. Optional private pre-staging records can also be
prepared, but no separate record writer is required by first-boot import. Do not confuse preparation with completed device provisioning.

API and OTA use a per-device key held in NVS, not a key compiled into public
firmware. A deliberate settings reset clears ESPHome settings and suppresses
stock reimport. No personal network is hardcoded as a reset fallback.

See [settings migration and publication rules](docs/SETTINGS-AND-MIGRATION.md).

## Current implementation

- Native ESPHome Bluetooth proxy: ESP32 scanning and one active GATT slot.
- Existing Nordic firmware and UART protocol retained, RX32/TX33 at 115200.
- Nordic advertisements use native Bluetooth API batches alongside ESP32
  advertisements. Unknown Bluetooth address types are preserved explicitly;
  ESP32 observations resolve them before GATT connections. No MQTT bridge.
- GPIO12 configuration button: ten-second hold resets settings; triple-click
  starts Wi-Fi SmartConfig. UART0 Improv provisioning is also enabled.
- Original flash layout retained. First boot copies hash-verified current
  stock from the other OTA slot into the existing factory slot, writing the
  header last and verifying the copy before selecting it for recovery.
- Bounded trial watchdog at entry to `app_main`, before ESPHome preferences,
  safe mode or component setup. Timed return to stock passed on hardware.
- Compact profile: error-level application logs, no gateway uptime entity,
  no GATT server, filesystem/stdio VFS or Bluetooth stack debug strings.
  GATT client, full C99 formatting, WPA2/WPA3 and encrypted API/OTA remain.

These are reusable components, but the hardware profile and recovery image
check currently target the inspected stock 1.5.13 application. Other V4 board
revisions and stock versions require verification; the marketing name does
not establish identical wiring.

## Documentation

- [Offline validation and remaining hardware tests](docs/VALIDATION.md)
- [Migration preflight and unattended-installation boundary](docs/MIGRATION-PREFLIGHT.md)
- [Configuration button and reset behavior](docs/BUTTON-BEHAVIOR.md)
- [Hardware, Ethernet reset evidence and remaining recovery work](docs/HARDWARE-AND-RECOVERY.md)
- [Installed-image Ethernet evidence](tools/installed-network-evidence.json)
- [Native Nordic delivery and address-type handling](docs/NATIVE-NORDIC.md)

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
gcc -std=c11 -Wall -Wextra -Werror -c components/ab_nordic/protocol.c -o /tmp/ab-protocol.o
g++ -std=c++17 -Wall -Wextra -Werror tests/native_nordic.cpp /tmp/ab-protocol.o -o /tmp/ab-native-test
/tmp/ab-native-test
./build.sh
```

The manual GitHub workflow runs the same checks on a hosted runner. Optional
build artifacts are encrypted to a supplied public recipient certificate;
no private settings or plaintext firmware are uploaded. The measured build
is **1,035,696 bytes**, leaving **12,880 bytes** in either original OTA slot.

Never publish NVS images, full-flash backups, private staging records or older
personalized diagnostic builds. Even a generic binary needs a publication
check against known private values before upload. Compile success is not a
hardware acceptance test.

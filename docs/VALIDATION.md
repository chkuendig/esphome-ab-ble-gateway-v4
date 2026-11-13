# Offline validation — 2026-11-14

The generic Wi-Fi prototype compiles with the pinned ESPHome 2026.10.2 / IDF
5.5.6 builder. Application size: **1,237,744 bytes**. SHA256:
`305d40b2361a44c7efa6742f708a1907206881aa13730625c1be83e43e63c019`.
No application from this repository has been installed on the gateway.

Completed checks:

- Host C++ tests: button timing boundaries, debounce, repeated hold,
  triple-click expiry, startup-held button and clock rollover.
- Native Nordic host tests: binary UART framing with embedded CR/LF, repeated
  frames, MAC byte order, signed RSSI, address-type observation/update/expiry,
  bounded eviction, unknown-type resolution/rejection and clock rollover.
- Native API compatibility test in a separate offline process using the
  installed `aioesphomeapi 46.25.0`, `bleak-esphome 4.0.0`, and
  `habluetooth 7.1.2`: protobuf round trip and actual scanner decoding preserve
  unknown/public/random address types, RSSI and service data. No HA API,
  adapter registration, network/radio setup or running HA state modification.
- Twelve Python tests: settings-record layout and input limits, rejecting
  unsupported enterprise Wi-Fi/empty keys, publication audit detection, and
  migration integrity checks for damaged backups/apps, overlapping partitions,
  moved settings, and interrupted partition-table writes. Emulator checkpoint
  tests also check preserved bootloader/NVS/PHY bytes, app placement and OTA
  selection isolated from the rest of flash.
- Tracked source and compiled OTA application checked against known private
  network/device values and both old and newly staged keys: no matches.
  This checks known values, not every possible secret.
- ESPHome's preferences-open failure path disassembled: its NVS erase call
  reaches `__wrap_nvs_flash_erase`, which refuses whole-default-NVS erasure.
- Linked startup path disassembled: IDF's `main_task` calls `__wrap_app_main`,
  which prepares stock selection and the RTC guard before calling ESPHome's
  real `app_main`. This fixes reliance on ordinary component setup, which safe
  mode can skip. It is compile/link evidence, not a demonstrated watchdog reset.
- Generated defines include runtime-key OTA and encryption-required guards.
- Linked Bluetooth open call reaches `__wrap_esp_ble_gattc_open`; unknown
  address types are resolved from ESP32 observations or rejected before the
  controller call. No MQTT or legacy MessagePack-packer symbols remain.
- Application checksum/hash validation passes. It fits the proposed 1.5 MiB
  OTA slots but exceeds both current 1 MiB stock OTA slots.

The full native migration removes MQTT, broker import and the legacy MessagePack
encoder. Nordic advertisements now use the existing encrypted Bluetooth API,
including explicit handling of the address type omitted by stock UART. This
saves **100,944 bytes** against the preceding 1,338,688-byte build, while still
exceeding the original 1 MiB slots by **189,168 bytes**. API Noise and
runtime-key encrypted OTA remain enabled. No feature claim depends on a broker.

The new [migration preflight](MIGRATION-PREFLIGHT.md) passes against the two
identical development backups and this candidate. It explicitly reports that
remote installation is not ready. A separate read-only inspection of saved NVS
found valid page headers, 63 empty entries in the active page and one empty
page; there is space for the small settings records without replacing NVS.
These are backup/offline observations, not a live migration or write test.

The size checker warns about the 960 KiB factory partition: it is reserved
for the preserved stock application, not ESPHome. The builder's merged
`firmware.factory.bin` is **not an installation artifact** for this layout;
never flash it. A safe installer has not been implemented. No downloadable
binary release is advertised yet.

Not validated: first-boot credential import on hardware, SmartConfig/Improv,
physical reset behavior and LED feedback, Ethernet startup, ESPHome GATT,
concurrent Nordic scanning with native delivery, new trial rollback, ordinary
OTA and partition migration. The native transport is implemented and tested
offline, but no hardware acceptance or HA integration retirement has occurred.

## Emulator investigation — inconclusive

Private checkpoint images were prepared from the matching device backups and
the earlier candidate, before MQTT removal. Espressif QEMU versions
`esp_develop_9.2.2_20260417` (recommended
by the pinned IDF tools manifest) and `esp_develop_9.2.2_20261109` were tried in
an isolated container without LAN access, with snapshot writes. Downloaded
archives were SHA256-checked against the IDF manifest or release asset digest.

Unmodified ROM tests produced no boot trace. A monitor sample with the stock
bootloader showed PC `0x40009a65`, in ROM `Cache_Flush`, before application
startup. A control image using the current IDF bootloader also produced no boot
trace. Instruction-count timing and single-thread translation did not resolve
this. An explicitly emulator-only ROM bypass of `Cache_Flush` advanced into the
stock bootloader (sample PC `0x40078d99`) but still did not reach the application.
Neither the bypass nor the alternate bootloader was applied to the device or
included in release sources/images.

**No stock/new-layout boot, settings import, timed return or watchdog reset is
claimed from these runs.** The emulator attempt is an unresolved tool/platform
limitation, not evidence that either firmware boots or fails on real hardware.
The fixture generator remains useful for reproducible investigation. Its unit
tests validate image construction only.

References: [Espressif QEMU documentation](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-guides/tools/qemu.html),
[November emulator release](https://github.com/espressif/qemu/releases/tag/esp-develop-9.2.2-20261109).
The latter explicitly retains the lack of Bluetooth emulation.

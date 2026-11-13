# Offline validation — 2026-11-14

The generic Wi-Fi prototype compiles with the pinned ESPHome 2026.10.2 / IDF
5.5.6 builder. Application size: **1,338,688 bytes**. SHA256:
`14f3808de029de8e0d2bcafceaa04533237758dd33e84a02543d2ef640e7b068`.
No application from this repository has been installed on the gateway.

Completed checks:

- Host C++ tests: button timing boundaries, debounce, repeated hold,
  triple-click expiry, startup-held button and clock rollover.
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
- Application checksum/hash validation passes. It fits the proposed 1.5 MiB
  OTA slots but exceeds both current 1 MiB stock OTA slots.

The supported size reduction removes unused MQTT transports and enterprise
Wi-Fi support, retaining the TLS helpers required by ESP-IDF's TCP transport.
Together with the early-recovery change it saves 10,256 bytes against the
original prototype, but still exceeds the original 1 MiB slots by 290,112 bytes.
API Noise and runtime-key encrypted OTA remain enabled.

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
concurrent Nordic scanning, new trial rollback, ordinary OTA and partition
migration. Native delivery of Nordic advertisements is not implemented; its
current MQTT transport remains necessary.

## Emulator investigation — inconclusive

Private checkpoint images were prepared from the matching device backups and
the candidate. Espressif QEMU versions `esp_develop_9.2.2_20260417` (recommended
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

# Offline validation — 2026-11-13

The generic Wi-Fi prototype compiles with the pinned ESPHome 2026.10.2 / IDF
5.5.6 builder. Application size: **1,338,464 bytes**. SHA256:
`09414cd15c17802a53bf41c4e67a2c03d95d19f993fb6cb94cee951b6ad0c533`.
No application from this repository has been installed on the gateway.

Completed checks:

- Host C++ tests: button timing boundaries, debounce, repeated hold,
  triple-click expiry, startup-held button and clock rollover.
- Nine Python tests: settings-record layout and input limits, rejecting
  unsupported enterprise Wi-Fi/empty keys, publication audit detection, and
  migration integrity checks for damaged backups/apps, overlapping partitions,
  moved settings, and interrupted partition-table writes.
- Tracked source and compiled OTA application checked against known private
  network/device values and both old and newly staged keys: no matches.
  This checks known values, not every possible secret.
- ESPHome's preferences-open failure path disassembled: its NVS erase call
  reaches `__wrap_nvs_flash_erase`, which refuses whole-default-NVS erasure.
- Generated defines include runtime-key OTA and encryption-required guards.
- Application checksum/hash validation passes. It fits the proposed 1.5 MiB
  OTA slots but exceeds both current 1 MiB stock OTA slots.

The supported size reduction removes unused MQTT transports and enterprise
Wi-Fi support, retaining the TLS helpers required by ESP-IDF's TCP transport.
It saves 10,480 bytes against the previous build, but the resulting
application still exceeds the original 1 MiB slots by 289,888 bytes.
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

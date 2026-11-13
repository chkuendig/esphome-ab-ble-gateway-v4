# Offline validation — 2026-11-13

The generic Wi-Fi prototype compiles with the pinned ESPHome 2026.10.2 / IDF
5.5.6 builder. Application size: **1,348,944 bytes**. SHA256:
`927a7556084428284f915bc1ee5c11900f53cdfdf2a219452a5f22b5c8052c87`.
No application from this repository has been installed on the gateway.

Completed checks:

- Host C++ tests: button timing boundaries, debounce, repeated hold,
  triple-click expiry, startup-held button and clock rollover.
- Four Python tests: settings-record layout and input limits, rejecting
  unsupported enterprise Wi-Fi/empty keys, and publication audit detection
  of secrets in both source and decoded binary key bytes.
- Tracked source and compiled OTA application checked against known private
  network/device values and both old and newly staged keys: no matches.
  This checks known values, not every possible secret.
- ESPHome's preferences-open failure path disassembled: its NVS erase call
  reaches `__wrap_nvs_flash_erase`, which refuses whole-default-NVS erasure.
- Generated defines include runtime-key OTA and encryption-required guards.
- Application checksum/hash validation passes. It fits the proposed 1.5 MiB
  OTA slots but exceeds both current 1 MiB stock OTA slots.

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

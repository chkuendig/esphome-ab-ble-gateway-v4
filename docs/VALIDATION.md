# Validation — 2026-11-14

## Compact native build

Source commit `c2826f1`, pinned ESPHome 2026.10.2 / IDF 5.5.6.
[Hosted build and checks](https://github.com/chkuendig/esphome-ab-ble-gateway-v4/actions/runs/43539136086)
passed. App-only size **1,035,696 bytes**; original-slot margin **12,880 bytes**.
SHA256: `e3db7976d02dc8227583b9d2bd518d6af5f5a98bc05c2cfbb02c7a1ae76334b0`.
First bounded trial booted and imported saved Wi-Fi, provisioned its private
API key, and reconnected with encryption. It remains unaccepted pending timed
recovery. Raw Bluetooth delivery exposed a C++ serializer size assumption:
marker 255 requires two bytes, but the optimized batch calculator reserves one.
The next candidate uses 127 and retains the connection type-resolution guard.
No GATT read succeeded during this first trial because delivery was interrupted.

Completed offline checks:

- Thirteen Python tests cover settings records, private-value audit, image
  integrity, layout preservation, exact 1 MiB boundary and 16-byte overflow,
  and emulator fixture construction.
- C++ gesture tests cover debounce, hold/click boundaries and clock rollover.
- Nordic protocol/cache tests cover binary framing, byte order, signed RSSI,
  observed/unknown address types, eviction, expiry and connection rejection.
- New stock-copy failure injection covers every operation, partial erase/write,
  damaged source/destination, retry, region overlap and flash boundaries. The
  original stock source remains unchanged and a partial copy is never selected.
- Image checksum/appended hash and SDK feature checks passed. GATT client,
  full Newlib, encrypted API/OTA and native Bluetooth proxy remain enabled.
- Downloaded build evidence was decrypted locally. Source and app audit against
  17 known private patterns found zero matches. This checks known values only.
- Real-backup preflight passes against two identical 4 MiB device backups:
  both original OTA slots fit, no partition-table change, NVS/PHY preserved.
- Linked recovery wrapper selects verified stock and arms its guard before
  ESPHome startup. NVS erase wrappers protect stock settings. Bluetooth open
  wrapper resolves unknown address type from actual ESP32 observations.
- Earlier offline native API compatibility check used aioesphomeapi 46.25.0,
  bleak-esphome 4.0.0 and habluetooth 7.1.2 to verify raw advertisement decoding.

Size reduction retains assertion checks but removes their strings, Bluetooth
stack debug output, unused GATT server, filesystem/stdio VFS and error-name
lookup. Application logging is ERROR; the optional gateway uptime entity was
removed. Full C99 formatting and WPA2/WPA3 remain. No MQTT or broker importer.
The original-layout recovery copy replaces the previously proposed repartition.

Not yet validated: hardware credential import and API onboarding, native GATT
and Nordic delivery, timed recovery, ordinary encrypted OTA, SmartConfig/Improv,
button hardware and LED feedback. Ethernet remains disabled in this Wi-Fi
profile. No downloadable firmware release is advertised.

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

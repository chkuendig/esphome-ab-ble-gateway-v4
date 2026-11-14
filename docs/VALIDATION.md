# Validation — 2026-11-14

## Live validation

The corrected image booted through stock's app-only OTA without changing the
partition table. Saved personal Wi-Fi and the privately provisioned API key
survived a stock return, a second installation and an encrypted native OTA.
Plaintext OTA fallback was disabled for the native OTA test.

- Initial bounded trial returned automatically to stock 1.5.13 after about
  15 minutes, without physical intervention. Visible network and gateway
  settings matched the pre-trial backup. No forced hung-loop RTC or physical
  power-cut test was performed.
- Corrected native delivery: 9,100 advertisements / 37 devices in 90 seconds,
  including Flower Care and the kettle. Unknown-type 127 packets demonstrate
  the Nordic UART path reaching the native API.
- Native ESP32 GATT read: Flower Care battery 45%, firmware 3.3.5. Another
  6,124 passive advertisements arrived in the following minute.
- After encrypted OTA/reboot: 9,451 advertisements / 35 devices in 90 seconds;
  repeat battery read 44%, followed by 6,430 advertisements in one minute.
  Neither GATT test wrote sensor characteristics or used the host adapter.
- Native captures contain temperature, illuminance, soil moisture and
  conductivity MiBeacon objects. The two radios share one native scanner
  identity; these counts are not a per-radio reception comparison.

Home Assistant onboarding passed. Its own Xiaomi BLE battery poll through the
proxy read **44%**; fresh plant measurements and kettle advertisements were
confirmed. The old MQTT gateway integration was disabled, leaving the broker
untouched. The acceptance command completed with an encrypted API response
and no recovery errors. Acceptance metadata has not been independently read
back. Upstream Xiaomi BLE polling remains once per day.

**MyCO2 remains unavailable:** two native captures contained no packets from
this device. A 90-second ESP32 active-scanning test also received none. A
controlled return to exact stock 1.5.13 with unchanged visible settings then
received 167 MQTT messages in 180 seconds, including 151 plant and 167 kettle
frames, but zero MyCO2 frames (both raw-wire MAC search and decoded records).
Stock therefore does not restore MyCO2 either; a migration regression has not
been established. The sensor/reception issue remains unresolved, and MyCO2
compatibility is not claimed as verified. The gateway was returned to the same
verified ESPHome image after this comparison; its encrypted API reconnected
with the existing key and remained responsive after 65 seconds. This also
exercised the native stock-return button without physical intervention. HA
reconnected automatically afterward and confirmed fresh plant readings and
kettle advertisements through the proxy, without an HA restart or new poll.

Physical reset gestures,
SmartConfig/Improv, LED feedback and Ethernet remain outside these tests.

The standalone provisioning helper additionally passed five mocked API tests:
reserved-key bootstrap, base64-text key encoding, private-key reconnection,
existing-key preservation, unexpected-firmware rejection and output-file
protection. The temporary server passed a loopback-only preflight/download/hash,
HEAD, unknown-path and private-file-permission check. These do not add a claim
of a separate end-to-end migration using the standalone wrappers.

## Corrected candidate

Source `5ae3c82`, [hosted build](https://github.com/chkuendig/esphome-ab-ble-gateway-v4/actions/runs/43540526377).
The unknown address-type marker is now 127 with a compile-time one-byte limit.
App size remains **1,035,696 bytes**; SHA256
`bf8dc77cab2cae8eae64767c464b286ffb64c27eda6db7dd8f39f61cf1f6b9fd`.
Offline checks, original-layout preflight and known-private-value audit passed.
Installed HA decoder tests also passed for marker 127. Corrected hardware trial passed the checks above.

## Compact native build

Source commit `c2826f1`, pinned ESPHome 2026.10.2 / IDF 5.5.6.
[Hosted build and checks](https://github.com/chkuendig/esphome-ab-ble-gateway-v4/actions/runs/43539136086)
passed. App-only size **1,035,696 bytes**; original-slot margin **12,880 bytes**.
SHA256: `e3db7976d02dc8227583b9d2bd518d6af5f5a98bc05c2cfbb02c7a1ae76334b0`.
First bounded trial booted and imported saved Wi-Fi, provisioned its private
API key, and reconnected with encryption. It was left unaccepted and returned automatically to stock 1.5.13 after
about 15 minutes. Visible stock network/gateway settings matched the backup. Raw Bluetooth delivery exposed a C++ serializer size assumption:
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

Not yet validated: SmartConfig/Improv, button hardware and LED feedback,
forced hung-loop RTC recovery and physical interruption during copying.
Ethernet remains disabled in this Wi-Fi profile. The initial candidate below
is superseded by the corrected candidate; it must not be installed.

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

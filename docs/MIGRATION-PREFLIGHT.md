# Migration preflight and installation boundary

`tools/check_migration.py` is an offline checker, not a flashing program. It
accepts two private full-device backups, an app-only ESPHome image and the
proposed layout. It never opens a network connection or modifies an input.
Its report contains geometry and hashes, not credentials or extracted NVS.

```sh
python3 tools/check_migration.py \
  private/flash-a.bin private/flash-b.bin \
  private/firmware.ota.bin layout-candidates/original-stock.csv
```

Exit status zero means the input checks completed. It does **not** mean the
device can be installed remotely. Check `remote_install_ready` and `blockers`;
the current implementation always reports `remote_install_ready: false`.

The checker requires:

- Two identical 4 MiB backups with the inspected stock partition geometry and
  a valid partition-table MD5.
- The exact inspected 944,400-byte stock application in its original slot,
  with valid ESP image checksum and appended SHA256.
- A valid ESP32 application that fits both proposed OTA partitions.
- Non-overlapping, aligned partitions within flash; unchanged NVS, OTA
  metadata and PHY geometry; a factory recovery slot that fits verified stock.

This deliberately rejects other board layouts and stock builds. It does not
infer hardware compatibility from the product name or accept arbitrary stock
firmware. The compact candidate passes against the matching development
backups and original layout: **1,035,696 bytes**, with no table change needed.
The checker remains an offline report; its `remote_install_ready: false` is
not a live trial result.

## Original-layout installation

The vendor OTA endpoint writes an app-only candidate into the unused 1 MiB OTA
slot. The running stock application, bootloader, NVS, PHY data and partition
table are retained. At the candidate's first `app_main` entry:

1. Find the exact hash-verified current stock application in the other OTA slot.
2. Select that stock image for the next boot and arm the trial watchdog.
3. Erase the existing factory slot and copy stock there, header sector last.
4. Verify the destination's descriptor and SHA256, then select it for recovery.
5. Start ESPHome, import saved personal Wi-Fi and provision its private API key.

Failure during copying leaves the source OTA image intact and selected. A
partial factory image is never deliberately selected. Host failure-injection
tests exercise each operation, partial writes/erase, retry and corrupt reads;
these are software-model tests, not physical power-cut tests. Faults before
`app_main` remain outside the application recovery guard.

The candidate then has two original-size OTA slots available, plus preserved
stock in factory. A bounded hardware trial is in progress. Network import,
Bluetooth delivery and timed recovery must be checked before acceptance.

## Superseded larger-layout investigation

Earlier builds needed 1.5 MiB OTA slots. That route was rejected for unattended
installation because the partition table occupies one erase sector: power loss
while replacing it can prevent all app boots, including stock. Espressif
[distinguishes app OTA from partition-table updates](https://docs.espressif.com/projects/esp-idf/en/v5.5.6/esp32/api-reference/system/ota.html).
The current build avoids that operation entirely. No table writer or bootloader
updater is included. The larger-layout fixtures below remain research tools.

## Private emulator checkpoints

`tools/prepare_emulation.py` uses the same input validation to create four
complete flash-image checkpoints: original layout, current stock copied into
the old factory slot, new layout booting stock, and new layout selecting the
proxy. It preserves bootloader, NVS and PHY bytes and generates the table MD5
and OTA selection record. These are completed states, **not an installer or a
validated ordering of device writes**.

```sh
python3 tools/prepare_emulation.py \
  private/flash-a.bin private/flash-b.bin private/firmware.ota.bin \
  layout-candidates/stock-and-dual-proxy.csv private/emulator-checkpoints
```

The destination must not already exist. Its permissions are 0700 and generated
files are 0600. **Every image contains private device settings. Never upload
them or use them as a hardware flashing artifact.**

The initial emulator attempt did not validate booting these images. See the
[validation record](VALIDATION.md) for the observed limitations. An emulator
also cannot establish real Bluetooth reception, network reconnection, physical
button behavior or power-loss recovery.

# Migration preflight and installation boundary

`tools/check_migration.py` is an offline checker, not a flashing program. It
accepts two private full-device backups, an app-only ESPHome image and the
proposed layout. It never opens a network connection or modifies an input.
Its report contains geometry and hashes, not credentials or extracted NVS.

```sh
python3 tools/check_migration.py \
  private/flash-a.bin private/flash-b.bin \
  private/firmware.ota.bin layout-candidates/stock-and-dual-proxy.csv
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
infer hardware compatibility from the product name or accept an arbitrary
firmware as stock. The two development backups pass these checks. Their old
factory application is 984,080 bytes and exceeds the proposed 983,040-byte
factory slot. The newer, verified stock app must replace it before changing
that geometry. Merely retaining the old factory bytes would break recovery.

## Why the current layout change is blocked for an unattended installation

The stock bootloader's inspected entry point at `0x400806a0` calls its partition
table loader (`0x4007936c`) before choosing or loading an application. Its error
path logs `load partition table error`; no independent recovery-table path was
established. Keeping a good stock application at `0x10000` therefore does not
make an invalid partition table bootable.

The table occupies one flash sector at `0x8000`. Replacing it involves an
erase/write interval in which neither table is valid. Offline tests model
erased and partially written tables through the MD5 record and verify their
rejection. This is an input-integrity model, not a hardware power-cut test.
Espressif likewise distinguishes [power-loss-safe app OTA from unsafe partition
table updates](https://docs.espressif.com/projects/esp-idf/en/v5.5.6/esp32/api-reference/system/ota.html).

The future installer must preserve bootloader/NVS/PHY, validate stock recovery
before retiring any old slot, verify every written app, and handle OTA metadata
under the old and new layouts. Even correct ordering cannot remove the single
table-sector interruption window. UART recovery would require physical access;
the UART adapters and actual board header have not been hardware-validated.

The native-only build removes MQTT entirely and forwards both receivers through
ESPHome's Bluetooth API. The application is 1,237,744 bytes: still 189,168 bytes
over the original 1 MiB slots. It therefore
needs a layout migration. A future smaller build would also need recovery
selection adapted to the original layout, plus hardware validation of startup,
credential import and timed return. Size alone does not establish that the
migration works.

No partition-table writer or bootloader updater is included. No live settings,
flash layout, Nordic firmware or Home Assistant configuration were changed by
these checks.

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

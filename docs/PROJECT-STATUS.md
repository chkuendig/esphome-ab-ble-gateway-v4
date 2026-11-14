# Project status and research handover — 2026-11-14

The migration and bounded UART investigation are complete for the tested unit.
It runs ESPHome with ESP32 Bluetooth scanning/GATT and the original Nordic
advertisement receiver. Nordic firmware remains **1.1.3**. No Nordic flash write,
DFU entry, SWD operation or read-protection change was performed.

Further Nordic GATT development is deferred until there is new evidence: a
matching firmware image, vendor protocol/update documentation, or a verified
read-only flash dump. The existing ESP32 path already supplies battery reads.

## What runs where

| Function | Implementation and limitation |
| --- | --- |
| Network and HA connection | ESP32 Wi-Fi and encrypted ESPHome native API. Ethernet is not enabled in this profile. |
| BLE connections / battery reads | ESP32, one concurrent GATT slot. HA's Xiaomi BLE integration successfully read the Flower Care battery through it. |
| Nordic reception | Existing AT scanner firmware over ESP RX32/TX33, 115200 8N1; passive scanning forwarded through the native API. |
| Receiver identity | Both radios share one logical native scanner. This does not turn Nordic into a connectable controller. See [address-type handling](NATIVE-NORDIC.md). |
| ESP32 scan mode | HA was left on Auto. Active scanning requests scan responses; GATT is a separate capability. Nordic remains passive. |
| Battery cadence | HA's upstream Xiaomi BLE integration polls daily. A configurable 72-hour interval was not implemented. No continuous connection or custom retry loop was added. |
| MQTT | Unneeded by the migrated firmware. The old installation's broker and HA entries were retired with private configuration retained for stock-data recovery. |
| UART investigation | Optional encrypted `serial_proxy`, exclusive ownership, 60-second lease and automatic scan restoration. No diagnostic client was left connected. |

The gateway can remain powered and networked near the sensors when the HA
server moves. Battery reads require **ESP32** radio coverage; hearing a device
only through Nordic does not establish GATT reachability. A final-placement
reception check after moving the server is still useful. A controlled per-radio
RSSI/dB comparison across devices has not been completed.

## Release versus tested diagnostic build

| Profile | Source / artifact | Size and status |
| --- | --- | --- |
| Normal proxy | [v0.1.0-preview.1](https://github.com/chkuendig/esphome-ab-ble-gateway-v4/releases/tag/v0.1.0-preview.1), binary built from `5ae3c82` | 1,035,696 bytes; 12,880 bytes spare in an original 1 MiB slot. Published app-only asset. |
| Optional serial diagnostics | `xbg-proxy-diagnostic.yaml`, tested source `62353b7`, [build 43589342639](https://github.com/chkuendig/esphome-ab-ble-gateway-v4/actions/runs/43589342639) | 1,039,312 bytes; 9,264 bytes spare. Installed and accepted on the test unit. Source merged in [PR #1](https://github.com/chkuendig/esphome-ab-ble-gateway-v4/pull/1); no diagnostic release asset published. |

The release asset was not silently replaced by the diagnostic build. Exact
hashes and validation are in [base validation](VALIDATION.md#corrected-candidate)
and [diagnostic validation](NORDIC-SERIAL-DIAGNOSTICS.md#validation-status).
Hosted encrypted build artifacts are temporary; the public source, pinned build
environment, hashes and test results are the durable reproduction record.

The diagnostic profile has a distinct acceptance key. Once that profile is
accepted, subsequent images sharing the same key are not automatically fresh
unaccepted trials. Developers must deliberately manage acceptance metadata for
future candidates; do not assume every OTA starts another 15-minute trial.

## Evidence established on hardware

- Original-layout app-only migration, saved Wi-Fi import, encrypted API/OTA,
  stock-return button and timed return passed. Stock settings survived.
- Plant temperature, illuminance, moisture and conductivity reached HA. ESP32
  battery reads succeeded repeatedly, including HA's own 44% reading at the
  time of testing. These are historical test values, not current telemetry.
- Kettle reception worked. MyCO2 reception returned after a sensor power cycle;
  the cause of its earlier outage and the receiving radio remain unproven.
- Serial queries returned Nordic `1.1.3`. Normal release, client disconnect and
  abandoned-client timeout all restored Nordic scanning. ESP32 plant reception
  continued during the Nordic pause.
- A separate eight-second ASCII scan produced 581 complete records. All used
  decimal payload lengths, contrary to the ABSniffer wiki's hexadecimal wording.
  Binary scanning resumed automatically afterward.

The first diagnostic restart sequence was too fast: 100 ms between commands
left Nordic stopped. A direct UART comparison established 600 ms as working;
the traced stock sequence waits approximately 510 ms. The diagnostic profile
uses 600 ms. The ordinary profile's existing startup timing was not changed.

Physical button gestures, SmartConfig/Improv, Ethernet, LED feedback, forced
hung-loop recovery, power-cut recovery and other PCB revisions remain untested.
Acceptance was sent successfully and the API remained responsive without
recovery errors; acceptance NVS was not independently read back.

## Nordic firmware research: findings and limits

Independent Opus and Sol investigations covered vendor repositories/history,
wiki revisions, forums, archived documentation and related public firmware.
The reconciled findings are:

| Finding | Evidence and qualification |
| --- | --- |
| ABSniffer 528 is the strongest family match | Matching CRLF framing, UART settings, command spellings and version response in the [vendor command reference](https://wiki.aprbrother.com/en/AT_Commands_For_ABSniffer_528.html). This is not an exact binary match or proof of exclusive in-house authorship. |
| Binary scan format has a documented sibling | Our `SCAN2` decoder matches [ZeroBeacon `SCAN4`](https://wiki.aprbrother.com/en/ZeroBeacon.html)'s prefix/MAC/RSSI/type/length/payload/CRLF layout. Command numbers and other capabilities differ between products. |
| Generic Nordic GATT is not established | Tested `CONN?`, `ROLE?`, `RADD?` and `RSSI?` returned `ERROR`. No applicable public GATT command interface was found. This does not prove all undocumented functions absent. |
| HCI is not the observed interface | [Vendor statement](https://bbs.aprbrother.com/t/1491) says the sibling dongle lacks HCI. Bounded H:4/H:5 probes received no reply at 115200 in the current mode. Nordic SoftDevice serialization is another protocol; H:5 framing alone does not establish HCI. |
| Exact Nordic image/source remains unavailable to this project | No matching public 1.1.3 image/source was found. A [V4 user's HEX request](https://bbs.aprbrother.com/t/1452) moved to private messages; their contents are unknown. |
| Remote Nordic updating remains unproven | A [2019 vendor reply](https://bbs.aprbrother.com/t/ab-ble-gateway-4-0/1509/3) says Bluetooth firmware could not then be updated OTA. Inspected ESP32 images exposed scan-control strings but no updater evidence. String searches do not prove code or embedded data absent. |
| Alternative public images are not recovery images for this unit | Nordic connectivity packages, newer nRF52840 dongle images and TI-target ZeroBeacon binaries have different targets/assumptions. None establishes a recoverable installation here. |

Do not infer source ancestry solely from identical pins or wire formats. Different
V2 serial framing likewise does not rule out shared source history. No Nordic
SDK/SoftDevice version or bootloader has been positively identified on this unit.

### Hardware and programmer uncertainty

[Published V4 schematics](https://github.com/AprilBrother/ab-hardware/tree/master/ab-ble-gateway-v4)
show an nRF52832, its TX/RX on P0.06/P0.08, and a Nordic programming header P3.
The drawings do not route Nordic reset or SWD to the ESP32. The observed unit's
LAN87xx Ethernet configuration and RX32/TX33 UART do not map cleanly to one
published revision. Confirm the actual PCB and chip markings before using any
header pinout; the firmware-reported hardware version is not a PCB revision.

**Correction retained from the research review:** upstream OpenOCD's inspected
[`ft232r` driver](https://github.com/openocd-org/openocd/blob/master/src/jtag/drivers/ft232r.c)
registers JTAG only. FT232RL SWD is not a validated no-purchase solution. An
[ESP32-hosted Nordic SWD implementation](https://github.com/atc1441/ESP32_nRF52_SWD)
is a possible future research route requiring physical wiring and separate
validation; it does not create SWD through the existing UART connection.

Read protection is unknown. Do not unlock by erasing: a full ESP32 backup does
not include Nordic flash, and this project has no verified Nordic recovery image.
Likewise, do not try the TI sibling's `AT+SBLUP`, guessed DFU commands or baud
setters as harmless queries. The serial lease cannot undo persistent changes.

## Resume from here

The owner plans to contact April Brother. This request can be copied without
including credentials, network settings or flash backups:

> I have an AB BLE Gateway V4 whose Nordic UART reports `OK+VERS:1.1.3`.
> Please distinguish this from the ESP32 gateway application version. Can you
> provide the matching Nordic scanner firmware image and checksum, target
> chip/PCB requirements, and complete UART command documentation, including
> `AT+SCAN2`? Does this build support generic GATT connections or any other
> host protocol? Is a bootloader installed, and is there a supported update
> and recovery procedure through UART or BLE? Please include signing/image
> requirements and SDK/SoftDevice versions if available.

No vendor message was sent by this project. If an image or instructions arrive,
inspect them offline first, establish an exact target and recovery path, and
only then consider another device experiment. A board photo and chip markings
would help resolve the hardware mismatch when physical access is convenient.

## Documentation and private evidence

- [Network return to stock and disaster recovery](HARDWARE-AND-RECOVERY.md#return-to-stock--disaster-recovery): verified vendor sources, private app extraction, OTA installation, slots and settings preservation.
- [Button behavior](BUTTON-BEHAVIOR.md): ten-second settings reset and triple-click provisioning; no guessed hold-at-boot action.
- [Settings migration](SETTINGS-AND-MIGRATION.md): private NVS/network/key handling and publication rules.
- [Serial diagnostics](NORDIC-SERIAL-DIAGNOSTICS.md): exclusive ownership, client usage, timing, tested recovery and remaining limits.
- [Validation record](VALIDATION.md): earlier migration trials, GATT, MyCO2 comparison, build sizes and unsuccessful emulator work.

Public documentation contains conclusions and reproducible source references.
Raw nearby-device captures, connection files, full-flash/NVS backups, private
research working files and generated artifacts remain excluded from GitHub.
For the original operator, private backup locations and hashes are retained in
the local maintenance handover. Keep those backups independently of short-lived
CI artifacts. Plant watering/feeding and lamp-monitoring automations belong to
the separate HA configuration; this repository implements the gateway transport.

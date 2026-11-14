# Hardware and recovery

This profile comes from a particular working stock 1.5.13 application. V4 PCB
revisions differ. Do not assume every device with the same case uses this
mapping. The Nordic firmware is left intact.

| Function | Evidence / status |
| --- | --- |
| ESP32 | Classic ESP32 with 4 MiB flash; native ESPHome GATT reads and concurrent Nordic delivery passed hardware tests. |
| Nordic UART | ESP RX32 / TX33, 115200. Stock Nordic 1.1.3 replies to AT commands and streams advertisements. |
| Nordic GATT | Not demonstrated through the stock UART protocol. `AT+ACT1` requests scan responses, not GATT connections. No Nordic SWD/DFU route or firmware backup has been validated. |
| Ethernet | Installed firmware uses LAN87xx, PHY address 1, MDC23 / MDIO18, output clock GPIO17. See trace below. |
| PHY reset | GPIO13, separate from configuration button. Installed firmware trace below establishes ordering and timing. The ESPHome Ethernet profile is not enabled in this Wi-Fi prototype. |
| Configuration button | GPIO12 active-low. Ten-second settings reset and triple-click SmartConfig traced in stock; replacement source implemented, hardware untested. |
| LED | Published drawings show GPIO5 active-low. Do not drive other revision-specific pins without evidence. Replacement stock LED feedback remains unfinished. |
| ESP serial recovery | Published header exposes GND, UART0, GPIO0, EN and 3.3 V. Orientation and actual board wiring must be checked before attaching a 3.3 V UART adapter. No physical recovery test yet. |
| Power | A power connector is not proof of onboard USB-to-UART. Optional PoE/modem circuitry in drawings does not prove population on a particular unit. |

Vendor references: [hardware drawings](https://github.com/AprilBrother/ab-hardware/tree/master/ab-ble-gateway-v4),
[quick start](https://wiki.aprbrother.com/en/Quick_Start_For_AB_BLE_Gateway_V4.html).
Stock discovery/configuration uses Ethernet/LAN HTTP, including `/info`.
ESPHome instead uses DHCP/mDNS and its native API; manual IP entry works when
multicast discovery does not. API pairing is separate from BLE device bonding.

## Flash layout and recovery limits

Stock has three 1 MiB application slots. Current stock is 944,400 bytes; the
compact ESPHome candidate is 1,035,696 bytes. The candidate retains the entire
original layout, including NVS at 0x9000, OTA metadata at 0xd000 and PHY at
0xf000. First boot selects current stock in the other OTA slot, copies it into
the existing factory slot with its header last, verifies it, then selects that
copy for recovery. The original source remains intact through the copy.

No partition-table or bootloader rewrite is needed. Never send a merged
ESPHome factory image to the stock application-only OTA endpoint. Host tests
model interrupted copies; normal first boot and timed stock return passed
hardware tests. Physical power interruption was not tested.

The recovery wrapper selects verified stock for the next boot and arms an RTC
guard at entry to `app_main`, before ESPHome initializes preferences or decides
whether to enter safe mode. Component setup adopts this state for a 15-minute
trial; the independent RTC guard expires ten seconds later if the main loop
cannot return to stock. Component setup alone cannot establish this protection:
safe mode can skip it. Faults before `app_main` remain outside this guard.
Acceptance is a separate operation.
The old diagnostic firmware's two timed stock returns succeeded, but this
ESPHome implementation returned to stock automatically in its first trial,
with visible settings unchanged. This did not separately force a hung-loop
RTC reset or a physical power interruption. Linker wrappers block whole-default-NVS
erasure so upstream preference recovery cannot erase vendor configuration.
An intentional ESPHome settings reset uses a namespace-specific operation.

ESPHome safe mode is different: it keeps basic network/OTA services but skips
ordinary components. It relies on previously persisted ESPHome Wi-Fi and API
settings. It cannot repair a damaged partition table or bootloader. UART ROM
recovery remains the last-resort physical path.

## Return to stock / disaster recovery

These are **network recovery** paths for the inspected 4 MiB/original-layout
profile. OTA requires a working application and network connection; it cannot
repair an erased bootloader or partition table. If every recognized stock
copy is lost, this preview stops before starting ESPHome, so its OTA service
may be unreachable. Physical recovery is outside this guide. None of these
paths programs the Nordic chip; an ESP32 backup does **not** include Nordic
firmware.

Use this order:

1. **Restore Stock Gateway Firmware:** press this software button on the
   gateway's ESPHome device page in HA, or through the encrypted native API.
   It selects verified stock for the next boot and restarts without clearing
   settings or downloading anything. This is the stock-return path tested on
   hardware, including the later stock/ESPHome reception comparison.
2. **Timed return:** an unaccepted trial returns to stock after approximately
   15 minutes. This passed on hardware. An accepted, healthy installation does
   not revert just because HA is unavailable. The separate hung-loop RTC guard
   was not forced in a test.
3. **Preserved factory-slot copy:** first boot automatically copies verified
   stock from the other OTA slot into `factory` at `0x10000`, verifies it, and
   selects it for recovery. This backs the first two paths; it is not another
   button or hold-at-boot gesture. The original OTA source stays selected until
   the copy is verified. See the copy limits above.
4. **Replacement stock app over OTA:** if a network uploader still works,
   obtain an app-only image as below. Prefer the exact stock app extracted
   from your own backup. Vendor updates need separate compatibility checks;
   they are not substitutes for this preview's hash-pinned recovery image.

### Obtain the app-only image

Full-flash backups contain device-specific Wi-Fi/NVS settings and keys: keep
them and their recorded SHA256 hashes private. Never upload a full backup to
an OTA endpoint, GitHub, or another gateway. This offline example checks two
matching backups, their partition table and the app checksum/digest, then
extracts only the exact supported stock app. Run from the repository root:

```sh
umask 077
python3 - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "tools")
from check_migration import EXPECTED, FLASH_SIZE, STOCK_SHA256, image, partitions

a = Path("private/flash-a.bin").read_bytes()
b = Path("private/flash-b.bin").read_bytes()
if a != b or len(a) != FLASH_SIZE:
    raise SystemExit("Need two matching 4 MiB backups")
slots = partitions(a[0x8000:0x9000])
if slots != EXPECTED:
    raise SystemExit("Not the supported original partition layout")
for name, kind, subtype, offset, size in slots:
    if kind != 0:
        continue
    try:
        info = image(a[offset:offset + size], padded=True)
    except ValueError:
        continue
    if info["sha256"] == STOCK_SHA256:
        with Path("private/stock-app.bin").open("xb") as output:
            output.write(a[offset:offset + info["size"]])
        print("Extracted", name, info)
        break
else:
    raise SystemExit("Exact supported stock app absent; do not guess an offset")
PY
sha256sum private/stock-app.bin
```

Expected: **944,400 bytes**, whole-file SHA256
`68f542ab048cf1b171dc8da3f44dfc5d94f5f801a21cf42e091cee572332dda0`;
descriptor `v1.5.12-3-gdb55502-dirty`, stock `/info` version `1.5.13`.
The descriptor and UI versions differ. Do not use a padded 1 MiB slot slice,
NVS image or merged factory image. Keep the extracted binary private too;
this repository does not redistribute April Brother firmware.

**Vendor sources verified on 2026-11-14:** April Brother's
[software page](https://wiki.aprbrother.com/en/Software_AB_BLE_Gateway_V4.html)
provides its configuration tool; the
[FAQ](https://wiki.aprbrother.com/en/FAQ_For_AB_BLE_Gateway_V4.html) describes
Advance → Update. A [vendor forum reply](https://bbs.aprbrother.com/t/upgrade-from-1-2-5-17-and-from-1-2-5-5-to-latest/1773)
links [this OTA file](http://ota.bconimg.com/gw4/1.2.5.5/ota.bin).
We also fetched the actual feed path
[`/gw4/1.5.13/ota.bin`](http://ota.bconimg.com/gw4/1.5.13/ota.bin).
Both returned valid ESP32 apps. The directory identifies the **starting
version**, not necessarily the downloaded version:

| Feed starting version | Downloaded app descriptor | Bytes | Whole-file SHA256 |
| --- | --- | --- | --- |
| 1.2.5.5 | `v1.4.15-dirty` | 984,080 | `bacb1caa660aa1d1afb66467199a4824a1b3c1d39383262d0261b469a25a905d` |
| 1.5.13 | `v1.5.18-8-g4eeba6b-dirty` (UI string 1.5.22.1) | 934,576 | `61d9f19e0c564b3ddc36981fe4edba46bee467dcca57d41b405fd54ec5ac0508` |

Neither is the pinned installed 1.5.13 image; neither was flashed in these
tests. Feed contents may change. Plain-HTTP downloads have image integrity
checks, not authenticated vendor signatures. We found no verified public
download of the exact installed image or a complete recovery package. If your
copy is gone, ask [April Brother support](https://bbs.aprbrother.com/c/ble-gateway/6)
for a matching image; their [stock-restore response](https://bbs.aprbrother.com/t/download-firmware-bin/1888)
provided assistance by email. Do not guess version URLs or bypass the preview's
stock hash check to migrate back from a different vendor build.

### Upload while ESPHome is running

The preview accepts a pushed app over **encrypted native OTA on TCP 3232**.
It has neither stock's `/update` API nor an HTTP download client, so no web
server is needed. Use its provisioned per-device API encryption key, also used
for OTA. Start from an accepted proxy that has been healthy for at least
60 seconds since boot, after its early recovery boot selection has settled.

This uses the same uploader call as the successful native OTA test, with
stock as the payload. Run in an environment with **ESPHome 2026.10.2** installed
(the pinned image in `build.sh` supplies it). The key prompt does not echo or
put the key in shell history. Replace the example address below with the gateway
address. **This stock-payload combination is source-reviewed,
not hardware-tested: the live native OTA test uploaded ESPHome to ESPHome.**

```sh
python3 - 192.0.2.20 <<'PY'
from getpass import getpass
from pathlib import Path
import hashlib
import sys
from esphome.espota2 import run_ota

app = Path("private/stock-app.bin")
if (app.stat().st_size != 944400 or
    hashlib.sha256(app.read_bytes()).hexdigest() !=
    "68f542ab048cf1b171dc8da3f44dfc5d94f5f801a21cf42e091cee572332dda0"):
    raise SystemExit("Expected the exact extracted stock app")
address = sys.argv[1]
key = getpass("Provisioned ESPHome API encryption key: ").strip()
status, _ = run_ota(address, 3232, None, app, noise_psk=key,
                    plaintext_fallback=False, allow_plaintext_upload=False)
raise SystemExit(status)
PY
```

The backend chooses the other OTA slot (`ota_0` at `0x110000` or `ota_1` at
`0x210000`), validates the transfer/image, selects it for boot, and reboots.
No manual offset or boot-selection write is needed. Factory recovery,
bootloader, partition table, NVS and PHY are not uploaded. Stock has no
ESPHome API; HA's ESPHome connection will disappear after return.

### Serve an app while stock is running

Stock's updater instead **pulls** an app from a LAN server. The tested
migration/reinstall changed its `ota-url` base, then posted `ota-update=1` to
`/update`. Stock reporting 1.5.13 fetched `<base>/1.5.13/ota.bin`; the POST
triggers a download, not a binary upload. The unused OTA slot receives the
app and is selected for boot. This was tested with ESPHome as the payload,
not as a separate stock-to-stock downgrade test.

Stage the extracted app using the existing restricted server, replacing the
example LAN addresses with your computer and gateway addresses:

```sh
python3 tools/serve_migration.py \
  private/flash-a.bin private/flash-b.bin private/stock-app.bin \
  private/stock-serve.json --bind-ip 192.0.2.10 --gateway-ip 192.0.2.20
```

This helper checks matching original backups (including stock in `ota_1`),
binds port 18081, serves only the chosen app to the specified gateway at an
unguessable path, and exits after 20 minutes. It saves `base_url` in the private
JSON file and makes **no device changes**. It is specific to source version
1.5.13 and the inspected layout, not a universal installer.

While serving, save stock's `/info`, `/config` and `/connection` responses
privately, including the original `ota-url`. Through the configuration tool
or form-encoded HTTP requests, with the gateway's HTTP authentication if enabled:

1. POST `/config` with `ota-url=<base_url from the private JSON>`.
2. POST `/update` with `ota-update=1` and allow the download/reboot. An HTTP
   disconnect alone is not a reason to trigger another update.
3. Verify the resulting application. Once stock is running, restore the
   **recorded original** `ota-url` through `/config`, read it back, and stop
   the server. Do not leave a temporary LAN server as the vendor update feed.

The serving/trigger sequence passed with ESPHome as the downloaded app.
Installing the extracted stock app through it remains untested on hardware.
The preserved-stock button needs neither this server nor an MQTT broker.

### Settings and verification after return

App-only OTA preserves **current NVS**; extracting an app from a backup does
not restore the backup's settings. Stock's `storage` namespace stays separate
from ESPHome preferences. Physical settings reset is a different operation;
do not use it as part of firmware return. The original stock app returned this
unit to its saved network. Compatibility with other vendor versions is unproven.

Fetch `http://<gateway-IP>/info` and check device identity and `firmwareVer`
(`1.5.13` for the extracted app). Compare `/config` and `/connection` with
private pre-migration snapshots; restore any temporary `ota-url` difference.
A version response alone does not prove the running image's SHA256: the
extraction and input hash identify supplied bytes, while the preserved-stock
route also verifies the on-device descriptor/digest. `/info` is not a flash
readback. Returning firmware does not reinstall HA integrations or a retired
MQTT broker; restore those separately if stock BLE delivery needs them.

The extraction example was run offline against both matching private backups
and produced the expected 944,400-byte app and SHA256. Both vendor downloads
were rechecked for valid ESP image checksums and appended SHA256; shell/Python
examples were syntax-checked. The upload examples were not executed on a device
for this documentation update.

See [validation](VALIDATION.md) for the trial, stock-return, settings comparison
and encrypted OTA results. No UART full-flash restore, power-cut recovery or
missing-all-stock-copies recovery is claimed here.

## Ethernet and two-radio integration work remaining

IDF's classic ESP32 Ethernet driver warns against simultaneous Wi-Fi and
ESP32-generated RMII output clock. A wired/Wi-Fi fallback profile therefore
needs explicit sequencing and validation; enabling both continuously is not
an established recovery solution. Current firmware is Wi-Fi only.

Native ESPHome has one adapter identity per Bluetooth proxy. Both radios now
feed that identity through the native API; MQTT is removed. Nordic UART omits
public/random address type. The replacement preserves an unknown type and
uses real ESP32 observations to resolve it before a connection; it never uses
the UART event type as an address type. Nordic RSSI does not establish ESP32
GATT reachability. See [native delivery](NATIVE-NORDIC.md) for the bounded cache,
connection guard and acceptance checks. The old HA scanner integration can be
retired after native delivery is accepted on hardware, as part of the cutover.

Acceptance needs repeated gateway-attributed GATT reads, fresh passive
advertisements from existing devices, network reconnection, ordinary OTA and
stock recovery. Prefer low-frequency battery reads; avoid continuous GATT
connections or tight retry loops. A successful compile is not these tests.

### Installed firmware reset trace — subsequent owner-requested investigation

This supersedes the earlier uncertainty about which Ethernet/reset profile to
choose for this unit. Ghidra analyzed the **944,400-byte application extracted
from the owner's gateway**, SHA256
`68f542ab048cf1b171dc8da3f44dfc5d94f5f801a21cf42e091cee572332dda0`,
internal version `v1.5.12-3-gdb55502-dirty` (stock UI 1.5.13). A byte comparison
also matched it to the stock ota_1 application in trial-6's later full backup.
This was not the similarly named downloaded update image.

Recovered initializer at `0x400d8930` calls reset `0x400d8cc4` before creating
the MAC/PHY and installing the Ethernet driver. The reset helper also appears
on the network-reinitialization path `0x400d8a5c`.

```c
// Reconstructed stock behavior; delays are scheduler ticks.
gpio_pad_select_gpio(13);                  // ROM 0x40009fdc
gpio_set_direction(13, GPIO_MODE_DISABLE); // 0x400e88d8, mode 0
vTaskDelay(11);                            // 0x4008b1f0
gpio_set_direction(13, GPIO_MODE_OUTPUT);  // mode 2
gpio_set_level(13, 0);                    // 0x400e873c
vTaskDelay(2);
gpio_set_level(13, 1);
```

The initial state is **disabled input and output**, not `GPIO_MODE_INPUT`.
There is no explicit final delay in this helper. Other driver startup/reset
operations run afterwards. Preserve that ordering rather than substituting a
generic reset pin with different timing.

Timing proof: `0x4008930c` initializes the CCOMPARE0 tick divisor to CPU Hz/100
(multiply `0x51eb851f`, signed shift37). Its CPU-frequency helper `0x400822b4`
returns ROM `g_ticks_per_us_pro` at `0x3ffe01e0` times 1,000,000. Tick setup and
ISR at `0x40089094` / `0x4008906c` consume that divisor. Thus 11 and2 ticks are
nominally 110 and20 ms, subject to scheduler phase. Do not carry raw tick counts
to a replacement firmware with a different RTOS frequency.

PHY constructor `0x400f1ce8` identifies itself as
`esp_eth_phy_new_lan87xx`. The initializer supplies address1, reset timeout100ms,
autonegotiation timeout4000ms and **driver reset GPIO -1**. GPIO13 is handled by
the separate helper, not by the PHY driver's reset-pin option. MAC defaults at
`0x3f403cb4` contain MDC23/MDIO18. The MAC constructor `0x400f10c4` resolves
default RMII clock selection to output mode2, GPIO17.

Resulting ESPHome profile: LAN8720-family driver, PHY1, MDC23, MDIO18,
GPIO17 CLK_OUT, no `power_pin` (to avoid a second driver-managed reset), plus
the separately ordered GPIO13 helper before Ethernet setup. The pinned
ESPHome setup priority for Ethernet is250; reset must precede it. This profile
is established from the working stock image, not physical chip identification.

Reproducible constants/hash check:
`tools/inspect_installed_network.py`; safe summary:
`installed-network-evidence.json` in the same directory. Private Ghidra exports and original firmware dumps are deliberately excluded
from this repository. No device reset, OTA, or GPIO probe was performed for this
offline investigation. The next uncertainty is live compatibility with the
ESPHome/IDF driver, not which stock reset sequence to reproduce.

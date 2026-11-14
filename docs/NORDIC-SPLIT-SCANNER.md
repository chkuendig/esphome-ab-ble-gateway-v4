# nRF52832 as a separate Home Assistant scanner

The default profile merges both radios into one logical ESPHome scanner. HA
then cannot tell which radio heard a packet, and treats nRF52832-only devices as
connectable through the ESP32 even though the nRF52832 cannot connect.

The split profile keeps the two receivers apart:

| HA scanner | Source | Radio | Connectable |
|---|---|---|---|
| ESPHome proxy (core `esphome`) | gateway Bluetooth MAC | ESP32 | yes (1 slot) |
| `ab_nordic` (this repo) | gateway network MAC | nRF52832, stock AT firmware | no |

The radio is the nRF52832 shown in the published V4 schematics; the chip
marking has not been inspected on a unit. The firmware component (`ab_nordic`),
the HA domain (`ab_nordic`) and the serial port name (`Nordic scanner`) are
internal identifiers kept for compatibility.

No ESPHome API change is needed. The nRF52832 stream uses the existing encrypted
`serial_proxy`, read through Home Assistant's own ESPHome connection.

## Firmware: `xbg-proxy-split.yaml`

- Adds a `serial_proxy` named **Nordic scanner** on the nRF52832 UART and sets
  `ab_nordic` to `serial_mode: split`.
- At boot `ab_nordic` starts the nRF52832 scanner (`SCAN0 → ACT0 → SCAN2`,
  600 ms apart), also when a client is already subscribed.
- While a client is subscribed, upstream `serial_proxy` is the only UART
  reader and forwards the unmodified binary SCAN2 stream. There is no lease:
  the HA client is permanent and never writes.
- Without a client, `ab_nordic` reads and **drops** nRF52832 adverts (owner
  decision): nothing nRF52832-heard reaches the connectable ESP32 scanner.
- When a client leaves, the firmware restores 115200 8N1 framing and
  restarts the scanner, in case the client changed either.
- Separate firmware-acceptance key (`0x58424703`), so the 15-minute stock
  return trial applies after installing it even if another profile was
  accepted before.
- No diagnostic button or lease. `tools/nordic_serial_probe.py` refuses to run
  against this profile, because the port belongs to the HA scanner.

Build with `AB_BUILD_CONFIG=xbg-proxy-split.yaml ./build.sh`, or select
`split` in the hosted build workflow.

## Home Assistant: `custom_components/ab_nordic`

1. Add this repository to HACS / the Marketplace as a custom *Integration*
   repository (`hacs.json` at the root), or copy `custom_components/ab_nordic`
   into HA's `custom_components`; restart HA. It requires the core `esphome`, `bluetooth` and `usb`
   integrations; `usb` registers HA's ESPHome serial-proxy transport.
2. Add **April Brother nRF52832 Scanner** and choose the gateway. Only loaded
   ESPHome entries exposing a `Nordic scanner` port are offered.
3. HA shows a new Bluetooth adapter "*gateway* nRF52832", next to the ESPHome
   proxy and any local adapters.

The integration opens
`esphome-hass://esphome/<esphome entry id>?port_name=Nordic%20scanner` with
`serialx`, parses `OK+SCAN:` records (`protocol.py`, mirroring
`components/ab_nordic/protocol.c`) and passes each one to a non-connectable
`BaseHaRemoteScanner`. The entry stores that URL as `device`, so HA's usb integration and the ESPHome
device page show the port as in use by this integration. HA's "Set up" picker
for serial ports lists only core integrations, so add this one from
*Add integration* instead. It reconnects with 5–60 s backoff after a gateway
reboot or ESPHome reload. Config-entry diagnostics report the stream counters
(bytes, records, malformed, connects, last error).

It never subscribes to Bluetooth advertisements itself. The ESPHome proxy
accepts only one advertisement subscriber, and that must stay HA's ESPHome
integration.

## Validation status

- Offline: the Python parser tests (`tests/test_ab_nordic_protocol.py`) cover
  binary length vs embedded CR/LF, command replies between records, mid-record
  starts, corrupt length/type/terminator, random chunking and bounded noise.
  `tests/split_owner.cpp` covers ownership/release transitions.
- Compile: [build 43609666943](https://github.com/chkuendig/esphome-ab-ble-gateway-v4/actions/runs/43609666943),
  source `b72ba9b`, 1,038,800 bytes (9,776 bytes spare in the original 1 MiB
  slot), SHA256 `b7a99f514ce9723b44db09d09c42270e74d31f4ff9095eba37ee1444540ec3c9`.
  The offline migration preflight passed against the unit's two identical backups.
- Hardware, 2026-11-14 on the test unit (Home Assistant 2026.11.1):
  - Encrypted app-only OTA, then accepted within the trial. Still running the
    split build after the 15-minute window; no stock return.
  - A direct, read-only 20 s subscription before HA setup received 1,558
    records from 31 devices, 0 malformed. Releasing it restored dropping
    without a reboot.
  - With `ab_nordic` set up, HA lists three adapters: the host adapter, the
    connectable ESPHome proxy and the non-connectable nRF52832 scanner. In one
    snapshot the nRF52832 heard 43 devices and the ESP32 51; 12 were heard only by
    the nRF52832 and are no longer offered as connectable through the ESP32.
  - Reloading the HA entry released and re-claimed the port without errors.
    After 14 minutes the stream had 65,428 records, 0 malformed, one connect.
  - Not yet exercised: reconnection after a gateway reboot or Wi-Fi loss,
    long-term stability, and HA restarts with the gateway offline.

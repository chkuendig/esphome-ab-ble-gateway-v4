# Nordic as a separate Home Assistant scanner

The default profile merges both radios into one logical ESPHome scanner. HA
then cannot tell which radio heard a packet, and treats Nordic-only devices as
connectable through the ESP32 even though the Nordic cannot connect.

The split profile keeps the two receivers apart:

| HA scanner | Source | Radio | Connectable |
|---|---|---|---|
| ESPHome proxy (core `esphome`) | gateway Bluetooth MAC | ESP32 | yes (1 slot) |
| `ab_nordic` (this repo) | gateway network MAC | Nordic, stock AT firmware | no |

No ESPHome API change is needed. The Nordic stream uses the existing encrypted
`serial_proxy`, read through Home Assistant's own ESPHome connection.

## Firmware: `xbg-proxy-split.yaml`

- Adds a `serial_proxy` named **Nordic scanner** on the Nordic UART and sets
  `ab_nordic` to `serial_mode: split`.
- At boot `ab_nordic` starts the Nordic scanner (`SCAN0 → ACT0 → SCAN2`,
  600 ms apart), also when a client is already subscribed.
- While a client is subscribed, upstream `serial_proxy` is the only UART
  reader and forwards the unmodified binary SCAN2 stream. There is no lease:
  the HA client is permanent and never writes.
- Without a client, `ab_nordic` reads and **drops** Nordic adverts (owner
  decision): nothing Nordic-heard reaches the connectable ESP32 scanner.
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

1. Copy `custom_components/ab_nordic` into HA's `custom_components` and
   restart HA. It requires the core `esphome`, `bluetooth` and `usb`
   integrations; `usb` registers HA's ESPHome serial-proxy transport.
2. Add **April Brother Nordic Scanner** and choose the gateway. Only loaded
   ESPHome entries exposing a `Nordic scanner` port are offered.
3. HA shows a new Bluetooth adapter "*gateway* Nordic", next to the ESPHome
   proxy and any local adapters.

The integration opens
`esphome-hass://esphome/<esphome entry id>?port_name=Nordic%20scanner` with
`serialx`, parses `OK+SCAN:` records (`protocol.py`, mirroring
`components/ab_nordic/protocol.c`) and passes each one to a non-connectable
`BaseHaRemoteScanner`. It reconnects with 5–60 s backoff after a gateway
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
- Compile and hardware validation are recorded separately once performed.

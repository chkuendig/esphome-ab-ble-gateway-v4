# Optional Nordic serial diagnostics

`xbg-proxy-diagnostic.yaml` adds upstream ESPHome `serial_proxy` on the existing
Nordic UART (ESP RX32/TX33, 115200 8N1) through the encrypted native API. It
does not flash Nordic or change the partition layout. The ordinary
`xbg-proxy.yaml` profile does not enable it.

Build with `AB_BUILD_CONFIG=xbg-proxy-diagnostic.yaml ./build.sh`, or select
`diagnostic` in the manual hosted build workflow. Check the measured app fits
the original 1 MiB slot before using encrypted app-only OTA. The diagnostic
profile has a separate firmware-acceptance key: the normal profile's previous
acceptance does not disable this profile's initial 15-minute stock-return trial.

## Ownership and recovery

The supported client arms **Begin Nordic Diagnostics** before subscribing.
Arming stops Nordic scanning and starts a non-renewable 60-second lease. While
armed or a serial client owns the port, `ab_nordic` does not read UART bytes or
send startup commands. Upstream `serial_proxy` is the sole raw reader and
permits only one client. ESP32 BLE scanning and GATT remain independent.

Unsubscribe/disconnect after an observed subscription, or expiry even if the
client never subscribed, releases diagnostics. The firmware evicts a remaining
subscriber on expiry, restores the ESP UART to 115200 8N1, clears the partial
parser/batch and restarts SCAN0 → ACT0 → SCAN2. No Nordic reset pin is used.
An undetected connection loss is bounded by the same lease. A subscribe and
unsubscribe within one loop pass still has the pre-armed deadline.

Use the supplied client, including its arming step. A third-party raw client
that subscribes, changes the scanner and unsubscribes between loop passes
without arming cannot be guaranteed automatic recovery. Repeated arming does
not extend an existing lease. Nordic-only devices can temporarily stop
reporting; tomato measurements and battery connections can continue through
the ESP32, subject to radio reachability.

This is authenticated raw UART access, not a firmware-enforced command
allowlist. Only trusted clients should use it. Do not send persistent baud,
reset, DFU, erase or guessed firmware-change commands. Restoring host framing
cannot undo an arbitrary change to Nordic firmware/settings. No RTS/DTR pins
are configured. These queries do not establish a Nordic GATT interface.

## Bounded query client

Use the pinned ESPHome environment's `aioesphomeapi`. Supply a private JSON
connection file containing `host`, `port` (6053), `mac`, and `noise_psk`; do not
put the key in command arguments or publish the connection/capture files.

```sh
python3 tools/nordic_serial_probe.py \
  --connection private/ha-connection.json \
  --output private/nordic-session.jsonl \
  --query status --query version
```

The default queries are `AT` and `AT+VERS?`. Optional named query forms
`connection`, `role`, `remote_address`, `rssi` repeat the earlier diagnostic's
read-only tests. At most ten queries are permitted, one second apart, with a
30-second overall probe deadline. The tool records raw byte chunks and TX
timestamps, always attempts unsubscribe, and does not initiate a GATT read.
RX chunks may split a response or combine several lines; retain the raw bytes.

## Validation status

Configuration validation passed. Lease tests cover no subscriber, disconnect,
a connected abandoned client, attempted renewal and clock wraparound. Client
tests cover pacing, rejected ownership and cleanup on failure. Build size and
live trial results must be recorded before claiming hardware validation.

Earlier diagnostic firmware (not this serial proxy) observed Nordic 1.1.3,
working AT/status/version replies, ERROR for the tested connection-related
queries, and no response to bounded H:4/H:5 probes at 115200 baud. A more
convenient transport does not change those results or prove hidden commands.

References: [ESPHome serial proxy](https://esphome.io/components/serial_proxy/),
[network stock recovery](HARDWARE-AND-RECOVERY.md#return-to-stock--disaster-recovery).

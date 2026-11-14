# Native ESPHome delivery from both receivers

The target is a full ESPHome migration. There is no MQTT component, broker
import, MessagePack encoder or replacement HA MQTT integration. The Nordic
stock firmware remains a passive UART receiver; ESP32 supplies active GATT.

## Data path

`ab_nordic` parses stock `OK+SCAN:` frames by their binary length, preserving
embedded CR/LF bytes. It converts the printable-order MAC, signed RSSI and
advertisement bytes into ESPHome `BluetoothLERawAdvertisementsResponse` batches.
The batches go only to the native proxy's subscribed encrypted API connection,
using its standard protobuf encoder and network backpressure handling. Batches
flush when full or every 250 ms; unavailable/full connections cause counted
drops rather than unbounded queues or replayed old measurements. A changed
subscriber discards the old subscriber's unsent batch.

ESP32 scanning and native GATT remain upstream ESPHome components. Both radios
appear as **one logical HA scanner**, not two independent adapter identities.
The Nordic component has counters logged at INFO (omitted by the compact
ERROR profile), but native
HA packet records do not distinguish which physical receiver heard a frame.

## Address types and connections

Stock UART includes advertising event type (0–4), but not public/random
Bluetooth address type. Those are different fields. MAC prefix/OUI is not a
reliable substitute either.

The native advertisement-filter hook observes genuine ESP32 scan results and
returns true so their normal delivery continues. It remembers up to 256
address/type pairs for ten minutes in RAM, with bounded replacement and
millisecond-clock rollover handling. Nordic packets use that observed type
when known; otherwise they carry **127 (unknown)** in the API's uint32 field.
Unknown packets still supply passive measurements. This sentinel is a local
firmware convention, not a new upstream per-packet connectability flag.
The first live trial exposed a serialization limit missed by Python-only
round-trip tests: ESPHome's optimized C++ batch size calculator allows only
one byte for a nonzero address type. The initial marker 255 used two bytes,
truncating batches. Marker 127 remains outside real types 0–3 and fits that
contract; a compile-time assertion prevents regression.

The tested HA libraries (`aioesphomeapi 46.25.0`, `bleak-esphome 4.0.0`,
`habluetooth 7.1.2`) preserve unknown type and still decode service data.
HA can retain the first packet's address-type details even after later
packets have a known type. Therefore the firmware also wraps the ESP32
`esp_ble_gattc_open` call: unknown requests use the current observed type, or
return `ESP_ERR_INVALID_ARG` immediately if none exists. Upstream ESPHome's
open-error path releases the connection slot and reports the failure. No
unknown type reaches the controller, and no address type is guessed.

This does **not** make the Nordic connectable. A device heard only by Nordic
may provide passive readings while GATT is unavailable through the ESP32.
Even a recently observed address type is not a promise of current radio range.
HA sees one proxy with active capability; it can attempt such a connection and
receive an error. Packet-level separation would require a richer upstream API.

The component owns the proxy's single advertisement-filter hook. Do not add a
second external filter without explicitly composing the callbacks. The GATT
linker wrapper is specific to the pinned ESP32/Bluedroid implementation and
must be rechecked when changing ESPHome or Bluetooth backends.

## Validation and cutover

Host tests cover UART framing, byte order, RSSI, address-type observation,
expiration, bounded eviction, unknown-type rejection and clock rollover.
`tests/native_api_compat.py` exercises protobuf round trips and the installed
HA scanner decoder in a separate process with synthetic packets; it does not
contact HA or Bluetooth. This establishes software compatibility, not live
radio delivery or a successful GATT connection.

Native plant/kettle delivery, ESP32 GATT, encrypted OTA/reconnection and timed
stock recovery have now passed hardware trials; HA independently read the plant
battery through the proxy. The old `ab_ble_gateway` entry is disabled and the
broker remains untouched. MyCO2 reception is an open regression blocking release.
Full-queue backpressure and every physical recovery path have not been exercised
on hardware. See [validation](VALIDATION.md) for the exact boundaries.

# nRF52832 UART protocol

Reverse-engineered interface for April Brother scanner firmware **1.1.3**. ESP32 RX=GPIO32, TX=GPIO33; **115200 baud, 8 data bits, no parity, 1 stop bit**. Commands and replies end in CRLF (`0D 0A`); binary records use their length field to locate it.

## Commands

Append `\r\n` to each command.

| Command | Reply or behavior |
| --- | --- |
| `AT` | `OK` |
| `AT+VERS?` | `OK+VERS:1.1.3` |
| `AT+SCAN0` | Stops scanning |
| `AT+SCAN1` | Starts ASCII advertisements |
| `AT+SCAN2` | Starts binary advertisements |
| `AT+ACT0` | Passive scan; no scan-response requests |
| `AT+ACT1` | Active scan; requests scan responses, no connections |
| `AT+CONN?`, `AT+ROLE?`, `AT+RADD?`, `AT+RSSI?` | `ERROR` |

Start sequence:

```text
AT+SCAN0\r\n
(wait about 600 ms)
AT+ACT0\r\n
(wait about 600 ms)
AT+SCAN2\r\n
```

100 ms intervals leave scanning stopped; stock waits approximately 510 ms. HA sends the 600 ms sequence on each connection; firmware transports bytes through `serial_proxy`.

## Binary SCAN2 record

Zero-based offsets; `N` is payload length.

| Offset | Bytes | Meaning |
| --- | --- | --- |
| 0–7 | 8 | ASCII `OK+SCAN:` (`4F 4B 2B 53 43 41 4E 3A`) |
| 8–13 | 6 | MAC in display order: `12 34 56 78 9A BC` = `12:34:56:78:9A:BC`; do not reverse |
| 14 | 1 | Signed 8-bit RSSI, dBm (two's complement) |
| 15 | 1 | Advertising event type, 0–4; not public/random address type |
| 16 | 1 | Binary payload length `N`, 0–31 |
| 17–(16+N) | N | Raw advertising data; empty when N=0 |
| 17+N | 1 | CR (`0D`) |
| 18+N | 1 | LF (`0A`) |

Total: **19+N bytes**. CR/LF may occur in any binary field: never split into lines. UART/API chunks may split or combine records; the [parser](../custom_components/ab_nordic/protocol.py) buffers incomplete records and resynchronizes after invalid input.

| Value | Event |
| --- | --- |
| 0 | Connectable undirected advertisement |
| 1 | Connectable directed advertisement |
| 2 | Scannable undirected advertisement |
| 3 | Non-connectable undirected advertisement |
| 4 | Scan response |

Public/random address type is not sent. The scanner cannot connect, even to connectable advertisers.

### Worked example

```text
4F 4B 2B 53 43 41 4E 3A  12 34 56 78 9A BC  BA 03 05
04 FF 0D 0A 0D  0D 0A
```

24 bytes: MAC `12:34:56:78:9A:BC`, RSSI **−70 dBm** (`BA`), event **3**, length **5**, payload `04 FF 0D 0A 0D`. Only the final `0D 0A` terminates the record.

## ASCII SCAN1 record

```text
OK+SCAN:<MAC>,<RSSI>,<type>,<length>,<hex payload>\r\n
```

MAC: 12 hex characters, no separators. RSSI: signed decimal. Type: same as SCAN2. Firmware **1.1.3 uses decimal length**, counting decoded payload bytes: ten bytes = `10`, not `0A`, unlike the ABSniffer wiki. HA consumes binary SCAN2.

## Radio limits and references

The integration supports neither generic GATT/connections nor HCI. No supported update path or matching recovery image is known for the installed nRF52832 firmware; ESP32 backups exclude it.

References: [ABSniffer 528 AT commands](https://wiki.aprbrother.com/en/AT_Commands_For_ABSniffer_528.html) (event types), [ZeroBeacon SCAN4](https://wiki.aprbrother.com/en/ZeroBeacon.html) (matching binary layout), [ESPHome serial proxy](https://esphome.io/components/serial_proxy/) (transport).

# nRF52832 UART protocol

This is the reverse-engineered scanner interface observed on April Brother firmware **1.1.3**. The ESP32 uses RX=GPIO32 and TX=GPIO33 at **115200 baud, 8 data bits, no parity, 1 stop bit**. Commands and text replies end in CRLF (`0D 0A`). Binary records also end in CRLF, but their length field determines where that terminator belongs.

## Commands

Append `\r\n` to each command.

| Command | Observed reply or behavior |
| --- | --- |
| `AT` | `OK` |
| `AT+VERS?` | `OK+VERS:1.1.3` |
| `AT+SCAN0` | Stops scanning |
| `AT+SCAN1` | Starts ASCII advertisement records |
| `AT+SCAN2` | Starts binary advertisement records |
| `AT+ACT0` | Passive scan: no scan-response requests |
| `AT+ACT1` | Active scan: requests scan responses; does not create connections |
| `AT+CONN?`, `AT+ROLE?`, `AT+RADD?`, `AT+RSSI?` | `ERROR` |

The working start sequence is:

```text
AT+SCAN0\r\n
(wait about 600 ms)
AT+ACT0\r\n
(wait about 600 ms)
AT+SCAN2\r\n
```

A 100 ms interval left the scanner stopped; stock waits approximately 510 ms. The Home Assistant integration sends the 600 ms sequence each time it connects. The firmware only transports the UART bytes through `serial_proxy`.

## Binary SCAN2 record

Offsets are zero-based. `N` is the payload length.

| Offset | Bytes | Meaning |
| --- | --- | --- |
| 0–7 | 8 | ASCII `OK+SCAN:` (`4F 4B 2B 53 43 41 4E 3A`) |
| 8–13 | 6 | MAC in display order: `12 34 56 78 9A BC` means `12:34:56:78:9A:BC`; do not reverse it |
| 14 | 1 | Signed 8-bit RSSI in dBm (two's complement) |
| 15 | 1 | Advertising event type, 0–4; **not** public/random address type |
| 16 | 1 | Binary payload length `N`, 0–31 |
| 17–(16+N) | N | Raw advertising data; empty when N=0 |
| 17+N | 1 | CR (`0D`) |
| 18+N | 1 | LF (`0A`) |

Total record size is **19+N bytes**. CR/LF can occur inside any binary field, including the payload. Never split the stream into lines before parsing. UART/API chunks can split or combine records; the [parser](../custom_components/ab_nordic/protocol.py) buffers incomplete records and resynchronizes after invalid input.

Event types follow the [ABSniffer 528 command reference](https://wiki.aprbrother.com/en/AT_Commands_For_ABSniffer_528.html):

| Value | Event |
| --- | --- |
| 0 | Connectable undirected advertisement |
| 1 | Connectable directed advertisement |
| 2 | Scannable undirected advertisement |
| 3 | Non-connectable undirected advertisement |
| 4 | Scan response |

An event describing a connectable advertiser does not give this scanner a connection capability. The advertiser's public/random address type is not sent.

### Worked example

```text
4F 4B 2B 53 43 41 4E 3A  12 34 56 78 9A BC  BA 03 05
04 FF 0D 0A 0D  0D 0A
```

This 24-byte record decodes to MAC `12:34:56:78:9A:BC`, RSSI **−70 dBm** (`BA`), event **3**, length **5**, payload `04 FF 0D 0A 0D`. Only the final `0D 0A` terminates the record. This example was run through `NordicParser.feed()` and produced one record with no malformed input.

## ASCII SCAN1 record

```text
OK+SCAN:<MAC>,<RSSI>,<type>,<length>,<hex payload>\r\n
```

The MAC has 12 hexadecimal characters without separators; RSSI is signed decimal, and type has the same event meaning as SCAN2. On firmware **1.1.3, length is decimal**, counting decoded payload bytes. For example, ten payload bytes are written as `10`, not `0A`. This differs from the ABSniffer wiki's description of a hexadecimal length. The HA integration consumes binary SCAN2.

## Scope and references

Tested on hardware: status/version queries, the listed rejected queries, SCAN1 decimal lengths, binary reception, and the paced start sequence. No generic GATT/connection interface or HCI transport is supported by this integration; bounded HCI probes produced no response. There is no known supported update path or matching recovery image for the installed nRF52832 firmware. An ESP32 flash backup does not contain that radio's firmware.

The closest published protocol references are [ABSniffer 528 AT commands](https://wiki.aprbrother.com/en/AT_Commands_For_ABSniffer_528.html) and [ZeroBeacon SCAN4](https://wiki.aprbrother.com/en/ZeroBeacon.html), whose binary layout matches this SCAN2 format. Related command names do not establish firmware compatibility. For transport details, see [ESPHome serial proxy](https://esphome.io/components/serial_proxy/).

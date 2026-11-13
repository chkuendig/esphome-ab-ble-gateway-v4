# Hardware and recovery

This profile comes from a particular working stock 1.5.13 application. V4 PCB
revisions differ. Do not assume every device with the same case uses this
mapping. The Nordic firmware is left intact.

| Function | Evidence / status |
| --- | --- |
| ESP32 | Classic ESP32 with 4 MiB flash; diagnostic GATT reads worked alongside Nordic scanning. ESPHome proxy acceptance is still pending. |
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

Stock has three 1 MiB application slots. Current stock is 944,400 bytes. The
candidate retains a 960 KiB factory stock slot and two 1.5 MiB ESPHome slots,
while preserving NVS at 0x9000, OTA metadata at 0xd000 and PHY data at 0xf000.
The older 984,080-byte factory image does not fit the smaller factory slot;
the verified current stock image must be copied and verified first.

The partition table has not been changed. Replacing its sector is not an
ordinary power-failure-safe application OTA. A generic settings bundle does
not solve that failure window. Bootloader compatibility and a recoverable
installer remain prerequisites. Never send a merged ESPHome factory image to
the stock application-only OTA endpoint.

The recovery wrapper selects verified stock for the next boot and arms an RTC
guard at entry to `app_main`, before ESPHome initializes preferences or decides
whether to enter safe mode. Component setup adopts this state for a 15-minute
trial; the independent RTC guard expires ten seconds later if the main loop
cannot return to stock. Component setup alone cannot establish this protection:
safe mode can skip it. Faults before `app_main` remain outside this guard.
Acceptance is a separate operation.
The old diagnostic firmware's two timed stock returns succeeded, but this
ESPHome implementation is untested. Linker wrappers block whole-default-NVS
erasure so upstream preference recovery cannot erase vendor configuration.
An intentional ESPHome settings reset uses a namespace-specific operation.

ESPHome safe mode is different: it keeps basic network/OTA services but skips
ordinary components. It relies on previously persisted ESPHome Wi-Fi and API
settings. It cannot repair a damaged partition table or bootloader. UART ROM
recovery remains the last-resort physical path.

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

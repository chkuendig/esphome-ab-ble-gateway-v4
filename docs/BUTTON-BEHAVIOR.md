# Configuration button: stock behavior and replacement status

Examined stock firmware 1.5.13, internal app version
`v1.5.12-3-gdb55502-dirty`, SHA256
`68f542ab048cf1b171dc8da3f44dfc5d94f5f801a21cf42e091cee572332dda0`.
This was extracted from the development gateway and matched against a later
full-flash backup. Investigation did not press the button or reset the device.

## Confirmed stock application actions

The recessed configuration button beside the Ethernet connector is GPIO12,
active low. This is separate from GPIO13 Ethernet PHY reset and GPIO0 ROM
download-mode selection.

| Gesture after the application starts | Stock behavior |
| --- | --- |
| Hold for about 10 seconds | Calls factory reset: clears the vendor `storage` settings namespace, commits it, closes it, waits nominally 2.01 seconds, then restarts. This is a destructive configuration reset, not just a reboot. |
| Three quick clicks/releases | Starts Wi-Fi SmartConfig provisioning. The handler counts release events separated by less than 500 timer units (the millisecond helper); this is not Ethernet pairing. |
| Single short click | Updates the click counter; no standalone restart action was found in the release handler. |

A settings reset does **not** select a different firmware image in the traced
handler. Returning to a preserved stock application while retaining its
settings would therefore be a different feature, not stock-equivalent button
behavior.

Evidence in the installed application:

- `0x400d966c`: creates GPIO12/active-low button, registers the ten-second
  serial/hold callback and release callback.
- `0x400d9644`: logs `press 10s` and calls `0x400d8e48`.
- `0x400d8e48`: opens `storage` read/write, erases its entries, commits/closes,
  waits 201 ticks at 100 Hz, and calls restart `0x400d8cfc`.
- `0x400d95d8`: release handler; counts rapid releases and calls `0x400d8bd4`
  on the third.
- `0x400d8bd4`: identifies itself as `app_netif_wifi_smartconfig`, configures
  LED blinking and Wi-Fi provisioning.
- `0x400dc078`: button creation installs an edge interrupt and debounce timers.

The vendor also documents powering the device first and holding the recessed
button for ten seconds: [April Brother FAQ](https://wiki.aprbrother.com/en/FAQ_For_AB_BLE_Gateway_V4.html).

## Replacement implementation

`ab_button` implements the same application gestures: GPIO12 active-low,
ten-second hold and three rapid release events. There is no added hold-at-boot
shortcut. Contact bounce is filtered for 5 ms. Host tests cover the timing
boundaries, bounce, one action per hold, startup-held behavior and millisecond
counter rollover. These tests do not exercise the hardware.

The replacement's hold clears the **ESPHome** settings namespace and restarts
after a nominal 2.01-second delay. It records stock-import suppression before
erasing, so a deliberate reset does not silently restore the old Wi-Fi network.
Firmware acceptance metadata and the preserved stock application's own settings
remain for recovery. This is the equivalent settings-reset action for ESPHome,
not byte-for-byte equivalence to erasing stock's `storage` namespace. It is
unavailable during an unaccepted firmware trial.

Triple-click invokes ESP-IDF SmartConfig (ESP-Touch/AirKiss). Credentials are
passed to ESPHome's saved Wi-Fi settings from the main loop. A session without
received credentials expires after three minutes and resumes the existing
Wi-Fi configuration. Stock's LED feedback is not yet replicated. Provisioning,
Wi-Fi reconnection and reset persistence still need live validation.

`Restore Stock Gateway Firmware` is a separate software/API action. It selects
the preserved stock image without clearing its configuration. A physical
settings reset does not select stock firmware. ESPHome safe mode, ROM serial
recovery and Ethernet PHY reset are also distinct operations.

**Status: source implemented, host gesture tests pass, no live button test or
ESPHome deployment.** Do not describe the entire replacement behavior as
hardware-verified stock equivalence.

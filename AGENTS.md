# Development rules

Read README.md and docs/BUTTON-BEHAVIOR.md before changing recovery behavior.
This is a preview tested on one inspected stock profile, not a universal V4
hardware profile. Preserve the documented validation limits.

- Preserve Nordic firmware. ESP32 GATT and Nordic scanning are distinct.
- Never commit credentials, generated firmware, flash backups or Ghidra
  databases. Use an explicit source-file list when staging changes.
- Treat stock settings reset, ESPHome settings reset, reboot, safe mode, ROM
  serial recovery and stock-firmware return as different operations.
- Record implementation, compile validation and live validation separately.
- Use the installed-image hash and function evidence for this unit. Do not
  infer a different board's GPIO mapping from the marketing model name.
- Respect the development host's local capacity rules before builds or agent
  dispatch. Set AB_CHECK_RUNNERS to its runner container names where needed.
  Coordinate HA changes with its separate owner.

#pragma once

namespace esphome::ab_nordic {
// Split mode: a serial-proxy client (the HA ab_nordic integration) receives the
// Nordic's raw SCAN2 stream as its own scanner. Track ownership so the firmware
// steps aside while a client holds the port and restarts scanning after it
// leaves, in case the client changed the scanner state or UART framing.
class SplitOwner {
 public:
  // Returns true exactly once per release, after ownership ends.
  bool released(bool owned) {
    const bool was_owned = owned_;
    owned_ = owned;
    return was_owned && !owned;
  }
  bool owned() const { return owned_; }

 private:
  bool owned_{false};
};
}  // namespace esphome::ab_nordic

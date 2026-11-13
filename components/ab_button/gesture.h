#pragma once
#include <cstdint>

namespace esphome::ab_button {
enum class Action { NONE, RESET_SETTINGS, SMARTCONFIG };
// Stock GPIO12 gestures: 5 ms debounce, 10 s hold, three releases <500 ms apart.
class Gesture {
 public:
  Action update(bool pressed, uint32_t now) {
    if (!initialized_) {
      initialized_ = true;
      raw_ = stable_ = pressed;
      armed_ = !pressed;  // No invented hold-at-boot action.
      changed_ = now;
      return Action::NONE;
    }
    if (pressed != raw_) { raw_ = pressed; changed_ = now; }
    if (raw_ != stable_ && uint32_t(now - changed_) >= 5) {
      stable_ = raw_;
      if (!armed_) { if (!stable_) armed_ = true; return Action::NONE; }
      if (stable_) { held_since_ = now; fired_ = false; }
      else if (!fired_) {
        clicks_ = clicks_ && uint32_t(now - released_) < 500 ? clicks_ + 1 : 1;
        released_ = now;
        if (clicks_ == 3) { clicks_ = 0; return Action::SMARTCONFIG; }
      }
    }
    if (armed_ && stable_ && !fired_ && uint32_t(now - held_since_) >= 10000) {
      fired_ = true;
      clicks_ = 0;
      return Action::RESET_SETTINGS;
    }
    return Action::NONE;
  }
 private:
  bool initialized_{false}, raw_{false}, stable_{false}, armed_{false}, fired_{false};
  uint8_t clicks_{0};
  uint32_t changed_{0}, held_since_{0}, released_{0};
};
}

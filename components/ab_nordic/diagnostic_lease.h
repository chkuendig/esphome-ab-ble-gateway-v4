#pragma once
#include <cstdint>

namespace esphome::ab_nordic {
// No renewal: a connected but abandoned client must not suppress scanning forever.
class DiagnosticLease {
 public:
  static constexpr uint32_t LIMIT_MS = 60000;
  bool begin(uint32_t now) {
    if (active_) return false;
    active_ = true;
    seen_owner_ = false;
    start_ = now;
    return true;
  }
  bool active() const { return active_; }
  bool finished(uint32_t now, bool owner) {
    if (!active_) return false;
    seen_owner_ |= owner;
    if ((seen_owner_ && !owner) || uint32_t(now - start_) >= LIMIT_MS) {
      active_ = false;
      return true;
    }
    return false;
  }
 private:
  bool active_{false}, seen_owner_{false};
  uint32_t start_{0};
};
}  // namespace esphome::ab_nordic

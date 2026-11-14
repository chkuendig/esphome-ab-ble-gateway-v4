#pragma once
#include <array>
#include <cstddef>
#include <cstdint>

namespace esphome::ab_nordic {
// UART carries event type, not address type. Preserve that distinction on the
// native API's uint32 address_type field. Never derive type from MAC/OUI/bits.
// ESPHome's optimized raw-advertisement size calculator reserves one varint
// byte for this field. 255 needs two bytes and truncates a batch on the wire.
// 127 remains outside the controller's real types (0..3), without that issue.
constexpr uint8_t UNKNOWN_ADDRESS_TYPE = 0x7f;
static_assert(UNKNOWN_ADDRESS_TYPE > 3 && UNKNOWN_ADDRESS_TYPE < 128);
inline uint8_t resolve_address_type(unsigned requested, uint8_t observed) {
  if (requested <= 3) return static_cast<uint8_t>(requested);
  return observed <= 3 ? observed : UNKNOWN_ADDRESS_TYPE;
}
inline uint64_t address_from_bytes(const uint8_t *mac) {
  uint64_t result = 0;
  for (unsigned i = 0; i < 6; ++i) result = (result << 8) | mac[i];
  return result;
}

template<size_t Capacity = 256> class AddressTypes {
 public:
  static constexpr uint32_t MAX_AGE_MS = 600000;
  void observe(uint64_t address, uint8_t type, uint32_t now) {
    if (address == 0 || type > 3) return;
    Entry *slot = &entries_[next_];
    for (auto &entry : entries_) {
      if (entry.address == address) { entry.type = type; entry.seen = now; return; }
    }
    *slot = {address, now, type};
    next_ = (next_ + 1) % Capacity;
  }
  uint8_t lookup(uint64_t address, uint32_t now) const {
    if (address == 0) return UNKNOWN_ADDRESS_TYPE;
    for (const auto &entry : entries_)
      if (entry.address == address && now - entry.seen <= MAX_AGE_MS) return entry.type;
    return UNKNOWN_ADDRESS_TYPE;
  }
 private:
  struct Entry { uint64_t address{0}; uint32_t seen{0}; uint8_t type{UNKNOWN_ADDRESS_TYPE}; };
  std::array<Entry, Capacity> entries_{};
  size_t next_{0};
};
}  // namespace esphome::ab_nordic

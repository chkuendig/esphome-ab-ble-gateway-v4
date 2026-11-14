#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>

namespace esphome::stock_recovery {
struct Region {
  uint32_t address, size;
  bool valid() const {
    return address >= 0x10000 && address % 0x10000 == 0 && size && size % 4096 == 0 &&
           uint64_t(address) + size <= 0x400000;
  }
  bool overlaps(Region other) const {
    return uint64_t(address) < uint64_t(other.address) + other.size &&
           uint64_t(other.address) < uint64_t(address) + size;
  }
};

// Ops uses partition APIs, never raw flash addresses. The current stock OTA
// image stays selected throughout all destructive operations on factory.
template<typename Ops>
bool copy_factory(Ops &ops, Region running, Region source, Region factory, size_t length, uint8_t *buffer) {
  if (!buffer || !running.valid() || !source.valid() || !factory.valid() ||
      factory.address != 0x10000 || (factory.size != 0x100000 && factory.size != 0xf0000) ||
      source.overlaps(running) || factory.overlaps(running) || factory.overlaps(source) ||
      !length || length % 16 || length > source.size || length > factory.size)
    return false;
  if (!ops.verify_source() || !ops.select_source() || !ops.erase_factory()) return false;
  // Write the header sector last. An interrupted copy is not presented as a
  // complete app; regardless, boot selection still points at the intact source.
  for (size_t offset = 4096; offset < length; offset += 4096) {
    const size_t count = std::min(size_t(4096), length - offset);
    if (!ops.read_source(offset, buffer, count) || !ops.write_factory(offset, buffer, count)) return false;
  }
  const size_t first = std::min(size_t(4096), length);
  if (!ops.read_source(0, buffer, first) || !ops.write_factory(0, buffer, first)) return false;
  return ops.verify_factory() && ops.select_factory();
}
}  // namespace esphome::stock_recovery

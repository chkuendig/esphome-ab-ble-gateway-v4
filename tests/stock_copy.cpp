#include "../components/stock_recovery/copy.h"
#include <cassert>
#include <cstring>
#include <vector>

using namespace esphome::stock_recovery;
static constexpr Region RUNNING{0x110000, 0x100000}, SOURCE{0x210000, 0x100000}, FACTORY{0x10000, 0x100000};
static constexpr size_t LENGTH = 0x3010;
struct Storage {
  std::vector<uint8_t> source = std::vector<uint8_t>(LENGTH, 0x5a);
  std::vector<uint8_t> factory = std::vector<uint8_t>(FACTORY.size, 0xa5);
  std::vector<size_t> writes;
  int step{0}, fail_at{-1}, selected{0};
  bool source_valid{true}, factory_valid{false}, corrupt_read{false};
  Storage() {
    for (size_t i = 0; i < source.size(); ++i) source[i] = (i * 13 + (i / 4096) * 37) % 251;
  }
  bool ok() { return ++step != fail_at; }
  bool verify_source() { return ok() && source_valid; }
  bool select_source() { if (!ok()) return false; selected = 1; return true; }
  bool erase_factory() {
    assert(selected == 1);
    // Model partial erasure on failure, not just failure before any mutation.
    std::fill(factory.begin(), factory.begin() + 4096, 0xff);
    if (!ok()) return false;
    std::fill(factory.begin(), factory.end(), 0xff);
    return true;
  }
  bool read_source(size_t offset, uint8_t *out, size_t count) {
    assert(selected == 1 && offset + count <= source.size());
    if (!ok()) return false;
    std::memcpy(out, source.data() + offset, count);
    if (corrupt_read) out[0] ^= 1;
    return true;
  }
  bool write_factory(size_t offset, const uint8_t *data, size_t count) {
    assert(selected == 1 && offset + count <= factory.size());
    writes.push_back(offset);
    // A failed write can have programmed part of the destination.
    std::memcpy(factory.data() + offset, data, count / 2);
    if (!ok()) return false;
    std::memcpy(factory.data() + offset, data, count);
    return true;
  }
  bool verify_factory() {
    if (!ok()) return false;
    factory_valid = std::equal(source.begin(), source.end(), factory.begin());
    return factory_valid;
  }
  bool select_factory() {
    assert(factory_valid);
    if (!ok()) return false;
    selected = 2;
    return true;
  }
};
int main() {
  uint8_t buffer[4096];
  Storage good;
  const auto expected = good.source;
  assert(copy_factory(good, RUNNING, SOURCE, FACTORY, LENGTH, buffer));
  assert(good.selected == 2 && good.writes.back() == 0);
  assert(good.source == expected);
  const int operations = good.step;
  // Every I/O failure must leave the source intact and never select a partial
  // destination. A later retry must repair even a partially written header.
  for (int fail = 1; fail <= operations; ++fail) {
    Storage interrupted;
    interrupted.fail_at = fail;
    assert(!copy_factory(interrupted, RUNNING, SOURCE, FACTORY, LENGTH, buffer));
    assert(interrupted.selected != 2);
    assert(interrupted.source == good.source);
    interrupted.fail_at = -1;
    assert(copy_factory(interrupted, RUNNING, SOURCE, FACTORY, LENGTH, buffer));
    assert(interrupted.selected == 2);
  }
  Storage invalid_source;
  invalid_source.source_valid = false;
  assert(!copy_factory(invalid_source, RUNNING, SOURCE, FACTORY, LENGTH, buffer));
  assert(invalid_source.writes.empty() && invalid_source.selected == 0);
  Storage corrupted_copy;
  corrupted_copy.corrupt_read = true;
  assert(!copy_factory(corrupted_copy, RUNNING, SOURCE, FACTORY, LENGTH, buffer));
  assert(corrupted_copy.selected == 1);
  for (const Region bad : {Region{0x8000, 0x100000}, Region{0x10000, 0x200000},
                           Region{0x110000, 0x100000}, Region{0x10000, 0}}) {
    Storage state;
    assert(!copy_factory(state, RUNNING, SOURCE, bad, LENGTH, buffer));
    assert(state.step == 0);
  }
  for (const Region bad : {RUNNING, FACTORY, Region{0x310000, 0x100000}, Region{0x210000, 0x1000}}) {
    Storage state;
    assert(!copy_factory(state, RUNNING, bad, FACTORY, LENGTH, buffer));
    assert(state.step == 0);
  }
  for (size_t length : {size_t(0), LENGTH - 1, size_t(0x100010)}) {
    Storage state;
    assert(!copy_factory(state, RUNNING, SOURCE, FACTORY, length, buffer));
    assert(state.step == 0);
  }
}

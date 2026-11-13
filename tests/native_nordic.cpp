#include "../components/ab_nordic/address_types.h"
extern "C" {
#include "../components/ab_nordic/protocol.h"
}
#include <cassert>
#include <cstring>
#include <vector>

using namespace esphome::ab_nordic;

int main() {
  const uint8_t mac[] = {0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc};
  const uint64_t address = address_from_bytes(mac);
  assert(address == 0x123456789abcULL);
  AddressTypes<2> cache;
  assert(cache.lookup(address, 0) == UNKNOWN_ADDRESS_TYPE);
  // An address's high bits/OUI say nothing about public vs random. Only an
  // actual ESP32 scan observation can establish it, including an update.
  cache.observe(address, 1, 10);
  assert(cache.lookup(address, 11) == 1);
  cache.observe(address, 0, 12);
  assert(cache.lookup(address, 13) == 0);
  cache.observe(address, UNKNOWN_ADDRESS_TYPE, 14);
  assert(cache.lookup(address, 15) == 0);
  assert(cache.lookup(address, 12 + cache.MAX_AGE_MS) == 0);
  assert(cache.lookup(address, 13 + cache.MAX_AGE_MS) == UNKNOWN_ADDRESS_TYPE);
  cache.observe(address, 1, 0xfffffff0);
  assert(cache.lookup(address, 0x20) == 1);  // millis rollover
  cache.observe(address + 1, 0, 0x20);
  cache.observe(address + 2, 0, 0x21);  // bounded eviction
  assert(cache.lookup(address, 0x22) == UNKNOWN_ADDRESS_TYPE);
  assert(cache.lookup(0, 0) == UNKNOWN_ADDRESS_TYPE);

  assert(resolve_address_type(0, 1) == 0);
  assert(resolve_address_type(1, 0) == 1);
  assert(resolve_address_type(255, 0) == 0);
  assert(resolve_address_type(255, 1) == 1);
  assert(resolve_address_type(255, 255) == UNKNOWN_ADDRESS_TYPE);
  assert(resolve_address_type(256, 255) == UNKNOWN_ADDRESS_TYPE);

  xbg_parser parser{};
  xbg_ad ad{};
  char line[160];
  std::vector<uint8_t> wire{'O','K','+','S','C','A','N',':'};
  wire.insert(wire.end(), mac, mac + 6);
  // Event type 3 is NOT random/public address type. Payload contains CRLF:
  // length-based framing must preserve it and must recover consecutive frames.
  wire.insert(wire.end(), {0xba, 3, 5, 4, 0xff, 0x0d, 0x0a, 7, 0x0d, 0x0a});
  unsigned frames = 0;
  for (unsigned repetition = 0; repetition < 2; ++repetition) {
    for (const uint8_t byte : wire) {
      if (xbg_feed(&parser, byte, &ad, line, sizeof(line)) != XBG_AD) continue;
      frames++;
      assert(ad.len == 13 && ad.data[0] == 3);
      assert(address_from_bytes(ad.data + 1) == address);
      assert(static_cast<int8_t>(ad.data[7]) == -70);
      const uint8_t expected[] = {4, 0xff, 0x0d, 0x0a, 7};
      assert(std::memcmp(ad.data + 8, expected, sizeof(expected)) == 0);
    }
  }
  assert(frames == 2 && parser.malformed == 0);
  assert(cache.lookup(address, 0x23) == UNKNOWN_ADDRESS_TYPE); // UART never teaches a type
}

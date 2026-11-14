#include "../components/ab_nordic/diagnostic_lease.h"
#include <cassert>
#include <cstdint>
using esphome::ab_nordic::DiagnosticLease;
int main() {
  DiagnosticLease lease;
  assert(!lease.finished(0, false));
  assert(lease.begin(100));
  assert(!lease.begin(50000));  // Cannot extend the deadline.
  assert(!lease.finished(60099, false));
  assert(lease.finished(60100, false));  // Client never subscribed.
  assert(!lease.active());
  assert(lease.begin(70000));
  assert(!lease.finished(70001, true));
  assert(lease.finished(70002, false));  // Explicit unsubscribe/disconnect.
  assert(lease.begin(80000));
  assert(!lease.finished(80001, true));
  assert(lease.finished(140000, true));  // Stuck connected client.
  assert(lease.begin(UINT32_MAX - 100));
  assert(!lease.finished(59898, true));
  assert(lease.finished(59899, true));  // millis() wraparound.
}

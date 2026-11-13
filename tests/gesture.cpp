#include "../components/ab_button/gesture.h"
#include <cassert>
#include <cstdint>
#include <iostream>
using esphome::ab_button::Gesture;
using esphome::ab_button::Action;

static Action click(Gesture &g, uint32_t t) {
  assert(g.update(true, t) == Action::NONE);
  assert(g.update(true, t + 5) == Action::NONE);
  assert(g.update(false, t + 40) == Action::NONE);
  return g.update(false, t + 45);
}
int main() {
  Gesture triple;
  triple.update(false, 0);
  assert(click(triple, 10) == Action::NONE);
  assert(click(triple, 200) == Action::NONE);
  assert(click(triple, 400) == Action::SMARTCONFIG);
  assert(click(triple, 600) == Action::NONE);

  Gesture slow;
  slow.update(false, 0);
  assert(click(slow, 10) == Action::NONE);
  assert(click(slow, 510) == Action::NONE); // Exactly 500 ms is outside window.
  assert(click(slow, 700) == Action::NONE);
  assert(click(slow, 800) == Action::SMARTCONFIG);

  Gesture hold;
  hold.update(false, 0);
  hold.update(true, 10);
  hold.update(true, 15);
  assert(hold.update(true, 10014) == Action::NONE);
  assert(hold.update(true, 10015) == Action::RESET_SETTINGS);
  assert(hold.update(true, 30000) == Action::NONE);
  hold.update(false, 30001);
  assert(hold.update(false, 30006) == Action::NONE);
  assert(click(hold, 30100) == Action::NONE);
  assert(click(hold, 30200) == Action::NONE);

  Gesture bounce;
  bounce.update(false, 0);
  for (uint32_t t = 10; t < 100; t += 4) {
    assert(bounce.update(true, t) == Action::NONE);
    assert(bounce.update(false, t + 2) == Action::NONE);
  }
  assert(bounce.update(false, 110) == Action::NONE);
  assert(click(bounce, 200) == Action::NONE);
  assert(click(bounce, 300) == Action::NONE);
  assert(click(bounce, 400) == Action::SMARTCONFIG);

  Gesture boot;
  boot.update(true, 0);
  assert(boot.update(true, 20000) == Action::NONE);
  boot.update(false, 20001);
  boot.update(false, 20006);
  assert(click(boot, 20100) == Action::NONE);
  assert(click(boot, 20200) == Action::NONE);
  assert(click(boot, 20300) == Action::SMARTCONFIG);

  Gesture wrap;
  uint32_t start = UINT32_MAX - 2000;
  wrap.update(false, start);
  wrap.update(true, start + 10);
  wrap.update(true, start + 15);
  assert(wrap.update(true, start + 10014) == Action::NONE);
  assert(wrap.update(true, start + 10015) == Action::RESET_SETTINGS);
  std::cout << "Gesture thresholds, bounce, startup and clock rollover passed\n";
}

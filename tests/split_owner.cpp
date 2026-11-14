#include "../components/ab_nordic/split_owner.h"
#include <cassert>
using esphome::ab_nordic::SplitOwner;
int main() {
  SplitOwner split;
  assert(!split.released(false));  // Boot without a client: nothing to restore.
  assert(!split.owned());
  assert(!split.released(true));   // Client subscribes.
  assert(split.owned());
  assert(!split.released(true));   // Still owned.
  assert(split.released(false));   // Unsubscribe/disconnect: restart scanning once.
  assert(!split.released(false));
  assert(!split.released(true));   // A later client is tracked again.
  assert(split.released(false));
  return 0;
}

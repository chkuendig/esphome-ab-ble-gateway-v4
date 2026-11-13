#pragma once
#include "esphome/core/component.h"

namespace esphome::ab_settings {
class AbSettings : public Component {
 public:
  void setup() override;
  float get_setup_priority() const override { return setup_priority::WIFI + 1; }
};
}

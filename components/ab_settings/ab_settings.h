#pragma once
#include "esphome/core/component.h"
#include "esphome/components/ab_nordic/ab_nordic.h"

namespace esphome::ab_settings {
class AbSettings : public Component {
 public:
  void setup() override;
  float get_setup_priority() const override { return setup_priority::WIFI + 1; }
  void set_nordic(ab_nordic::AbNordic *nordic) { nordic_ = nordic; }
 protected:
  ab_nordic::AbNordic *nordic_{nullptr};
};
}

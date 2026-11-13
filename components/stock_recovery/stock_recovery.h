#pragma once
#include "esphome/core/component.h"
#include "esphome/core/preferences.h"
#include "esp_partition.h"

namespace esphome::stock_recovery {
class StockRecovery : public Component {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::HARDWARE; }
  bool accept();
  void restore_stock();
  bool reset_settings();
 protected:
  bool select_proxy_();
  const esp_partition_t *stock_{nullptr};
  ESPPreferenceObject preference_;
  bool accepted_{false}, guard_active_{false}, restore_requested_{false};
  uint32_t start_{0};
};
}  // namespace esphome::stock_recovery

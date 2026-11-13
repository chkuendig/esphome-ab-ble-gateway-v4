#pragma once
#include "gesture.h"
#include "esphome/core/component.h"
#include "esphome/components/stock_recovery/stock_recovery.h"
#include "esp_event.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

namespace esphome::ab_button {
class AbButton : public Component {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }
  void set_recovery(stock_recovery::StockRecovery *recovery) { recovery_ = recovery; }
 private:
  struct Event { int32_t type; char ssid[33]; char password[65]; };
  static void on_smartconfig_(void *, esp_event_base_t, int32_t, void *);
  void start_smartconfig_();
  void stop_smartconfig_();
  stock_recovery::StockRecovery *recovery_{nullptr};
  Gesture gesture_;
  QueueHandle_t events_{nullptr};
  esp_event_handler_instance_t handler_{nullptr};
  bool provisioning_{false}, reset_pending_{false}, credentials_applied_{false};
  uint32_t provision_started_{0}, reset_started_{0};
};
}

#pragma once
#include "esphome/core/component.h"
#include "esphome/components/uart/uart.h"
extern "C" {
#include "protocol.h"
}

namespace esphome::ab_nordic {
class AbNordic : public Component, public uart::UARTDevice {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  void set_topic(const std::string &topic) { topic_ = topic; }
  float get_setup_priority() const override { return setup_priority::DATA; }
 protected:
  xbg_parser parser_{};
  xbg_ad batch_[128]{};
  uint8_t packet_[6000]{};
  uint8_t source_[6]{};
  std::string topic_;
  size_t count_{0};
  uint32_t last_publish_{0}, last_stats_{0}, message_id_{0}, adverts_{0}, dropped_{0};
  uint8_t start_stage_{0};
  uint32_t start_time_{0};
};
}  // namespace esphome::ab_nordic

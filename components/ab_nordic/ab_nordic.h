#pragma once
#include "esphome/core/component.h"
#include "esphome/components/uart/uart.h"
#include "esphome/components/bluetooth_proxy/bluetooth_proxy.h"
#include "address_types.h"
extern "C" {
#include "protocol.h"
}

namespace esphome::ab_nordic {
class AbNordic : public Component, public uart::UARTDevice {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  void set_proxy(bluetooth_proxy::BluetoothProxy *proxy) { proxy_ = proxy; }
  uint8_t address_type(uint64_t address) const { return types_.lookup(address, millis()); }
  float get_setup_priority() const override { return setup_priority::DATA; }
 protected:
  xbg_parser parser_{};
  AddressTypes<> types_;
  bluetooth_proxy::BluetoothProxy *proxy_{nullptr};
  api::APIConnection *batch_client_{nullptr};
  api::BluetoothLERawAdvertisementsResponse batch_;
  void queue_(const xbg_ad &ad);
  void flush_();
  uint32_t last_publish_{0}, last_stats_{0}, adverts_{0}, dropped_{0}, unknown_type_{0};
  uint8_t start_stage_{0};
  uint32_t start_time_{0};
};
}  // namespace esphome::ab_nordic

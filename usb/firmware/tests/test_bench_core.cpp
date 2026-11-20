#include "../hamda_usb_bench/src/bench_core.h"

#include <stdint.h>
#include <stdlib.h>

#include <iostream>
#include <string>
#include <vector>

namespace {

#define CHECK(condition) do { if (!(condition)) { \
  std::cerr << __func__ << ":" << __LINE__ << ": " #condition "\n"; \
  exit(1); } } while (false)

const uint8_t kA[6] = {0x10, 0x00, 0x3B, 0xCC, 0x97, 0xD8};
const uint8_t kB[6] = {0x10, 0x00, 0x3B, 0xCC, 0x1C, 0x78};
const uint8_t kUnknown[6] = {0, 1, 2, 3, 4, 5};

struct FakeClock : hamda::Clock {
  uint32_t now = 0;
  uint32_t now_ms() const override { return now; }
  void advance(uint32_t ms) { now += ms; }
};

struct Event {
  uint8_t pin;
  bool high;
  bool prepare;
};

struct FakeGpio : hamda::Gpio {
  bool high[256] = {};
  bool prepared[256] = {};
  int fail_prepare_pin = -1;
  int fail_high_pin = -1;
  FakeClock* clock = nullptr;
  uint32_t high_cost_ms = 0;
  std::vector<Event> events;
  bool prepare_low(uint8_t pin) override {
    events.push_back(Event{pin, false, true});
    high[pin] = false;
    prepared[pin] = true;
    return pin != fail_prepare_pin;
  }
  bool write(uint8_t pin, bool value) override {
    events.push_back(Event{pin, value, false});
    if (value && pin == fail_high_pin) return false;
    high[pin] = value;
    if (value && clock != nullptr) clock->advance(high_cost_ms);
    return true;
  }
  bool all_off() const {
    for (size_t i = 0; i < 256; ++i) if (high[i]) return false;
    return true;
  }
};

struct Rig {
  FakeClock clock;
  FakeGpio gpio;
  hamda::Controller core;
  explicit Rig(const uint8_t* mac = kA) : core(mac, clock, gpio) {
    gpio.clock = &clock;
    core.begin();
    clock.advance(250);
    core.tick();
  }
  void bytes(const std::string& text) {
    for (size_t i = 0; i < text.size(); ++i) core.receive(text[i]);
  }
  void command(const std::string& text) { bytes(text + "\n"); }
  std::string drain() {
    std::string result;
    while (core.next_reply_size() != 0) {
      const size_t size = core.next_reply_size();
      result.append(core.next_reply(), size);
      core.consume_reply(size);
    }
    return result;
  }
};

void profiles_and_startup() {
  Rig a;
  Rig b(kB);
  CHECK(a.core.known_device() && b.core.known_device());
  CHECK(std::string(a.core.profile()->name) == "A");
  CHECK(std::string(b.core.profile()->name) == "B");
  CHECK(a.gpio.events.size() == 4);
  const uint8_t expected[] = {3, 2, 1, 0};
  for (size_t i = 0; i < 4; ++i) {
    CHECK(a.gpio.events[i].prepare);
    CHECK(!a.gpio.events[i].high);
    CHECK(a.gpio.events[i].pin == expected[i]);
    CHECK(b.core.profile()->pins[i] == expected[i]);
  }
  CHECK(a.gpio.all_off() && !a.core.active());
  CHECK(!a.gpio.prepared[18] && !a.gpio.prepared[19]);
  a.core.begin();
  CHECK(a.gpio.events.size() == 4);  // no reinitialization side effects
}

void unknown_never_touches_gpio() {
  Rig r(kUnknown);
  r.command("PULSE 15 250");
  r.command("STOP");
  r.command("invalid");
  r.command("ID");
  r.clock.advance(1000);
  r.core.tick();
  CHECK(!r.core.known_device());
  CHECK(!r.core.active());
  CHECK(r.gpio.events.empty());
  const std::string replies = r.drain();
  CHECK(replies.find("ERR UNKNOWN_DEVICE\n") != std::string::npos);
  CHECK(replies.find("UNKNOWN 00:01:02:03:04:05\n") != std::string::npos);
}

void startup_pause() {
  FakeClock clock;
  FakeGpio gpio;
  hamda::Controller core(kA, clock, gpio);
  core.begin();
  const std::string pulse = "PULSE 1 10\n";
  for (char c : pulse) core.receive(c);
  CHECK(!core.active());
  clock.advance(249);
  core.tick();
  for (char c : pulse) core.receive(c);
  CHECK(!core.active());
  clock.advance(1);
  for (char c : pulse) core.receive(c);
  CHECK(core.active());
}

void mask_and_autonomous_deadline() {
  Rig r;
  r.command("PULSE 5 250");
  CHECK(r.core.active() && r.core.active_mask() == 5);
  CHECK(r.gpio.high[3] && !r.gpio.high[2] && r.gpio.high[1] && !r.gpio.high[0]);
  r.clock.advance(249);
  r.core.tick();
  CHECK(r.core.active());
  r.clock.advance(1);
  r.core.tick();
  CHECK(!r.core.active() && r.gpio.all_off());
}

void every_mask_and_minimum_duration() {
  for (unsigned mask = 1; mask <= 15; ++mask) {
    Rig r;
    r.command("PULSE " + std::to_string(mask) + " 1");
    CHECK(r.core.active_mask() == mask);
    for (unsigned slot = 0; slot < 4; ++slot) {
      CHECK(r.gpio.high[3 - slot] == ((mask & (1U << slot)) != 0));
    }
    r.clock.advance(1);
    r.core.tick();
    CHECK(r.gpio.all_off());
  }
}

void active_pulses_do_not_extend_or_add_channels() {
  Rig r;
  r.command("PULSE 1 100");
  r.clock.advance(50);
  const size_t event_count = r.gpio.events.size();
  r.command("PULSE 1 250");
  r.command("PULSE 8 250");
  CHECK(r.core.active_mask() == 1);
  CHECK(r.gpio.events.size() == event_count);
  r.clock.advance(50);
  r.core.tick();
  CHECK(!r.core.active() && r.gpio.all_off());
  CHECK(r.drain().find("ERR ACTIVE\n") != std::string::npos);
}

void off_pause_after_expiry_and_stop() {
  Rig r;
  r.command("PULSE 1 10");
  r.clock.advance(10);
  r.core.tick();
  r.command("PULSE 2 10");
  CHECK(!r.core.active());
  r.clock.advance(249);
  r.command("PULSE 2 10");
  CHECK(!r.core.active());
  r.clock.advance(1);
  r.command("PULSE 2 250");
  CHECK(r.core.active());
  r.command("STOP");
  CHECK(r.gpio.all_off());
  r.clock.advance(249);
  r.command("PULSE 2 10");
  CHECK(!r.core.active());
  r.clock.advance(1);
  r.command("PULSE 2 10");
  CHECK(r.core.active());
}

void late_loop_pause_uses_actual_off() {
  Rig r;
  r.command("PULSE 15 1");
  r.clock.advance(1000);
  r.core.tick();
  r.command("PULSE 15 1");
  CHECK(!r.core.active());
  r.clock.advance(250);
  r.command("PULSE 15 1");
  CHECK(r.core.active());
}

void millis_wrap_for_pulse_and_pause() {
  Rig r;
  r.clock.now = UINT32_MAX - 100;
  r.command("PULSE 15 250");
  r.clock.advance(249);
  r.core.tick();
  CHECK(r.core.active());
  r.clock.advance(1);
  r.core.tick();
  CHECK(!r.core.active());
  r.clock.advance(249);
  r.command("PULSE 1 1");
  CHECK(!r.core.active());
  r.clock.advance(1);
  r.command("PULSE 1 1");
  CHECK(r.core.active());
  r.command("STOP");
  r.clock.now = UINT32_MAX - 100;
  r.command("STOP");
  r.clock.advance(249);
  r.command("PULSE 1 1");
  CHECK(!r.core.active());
  r.clock.advance(1);
  r.command("PULSE 1 1");
  CHECK(r.core.active());
}

void malformed_commands_fail_closed() {
  const char* bad[] = {
      "", "pulse 1 10", "PULSE 0 10", "PULSE 16 10", "PULSE 1 0",
      "PULSE 1 251", "PULSE -1 10", "PULSE 1 -10", "PULSE +1 10",
      "PULSE 1 1.5", "PULSE 1", "PULSE 1 10 extra", "PULSE  1 10",
      " PULSE 1 10", "PULSE 1 10 ", "PULSE 999999999999999999999999 1",
      "STOP extra", "PING extra", "UNKNOWN", "PULSE 1 9999999999999999999999"};
  for (const char* line : bad) {
    Rig r;
    r.command("PULSE 15 250");
    r.command(line);
    CHECK(!r.core.active() && r.gpio.all_off());
    CHECK(r.drain().find("ERR INPUT\n") != std::string::npos);
  }
}

void overflow_stops_before_newline_and_resynchronizes() {
  Rig r;
  r.command("PULSE 15 250");
  r.bytes(std::string(hamda::Controller::kLineCapacity, 'X'));
  CHECK(!r.core.active() && r.gpio.all_off());
  r.bytes("PULSE 15 250\n");  // discarded suffix cannot become a command
  CHECK(!r.core.active());
  r.clock.advance(250);
  r.command("PULSE 1 1");
  CHECK(r.core.active());
}

void invalid_byte_and_crlf() {
  Rig r;
  r.bytes("PULSE 1 250\r\n");
  CHECK(r.core.active());
  r.core.receive(0);  // fail closed immediately, no newline needed
  CHECK(!r.core.active() && r.gpio.all_off());
  r.bytes("\n");
  r.clock.advance(250);
  r.bytes("PULSE 1 250\n");
  CHECK(r.core.active());
  r.bytes("PI\rNG");
  CHECK(!r.core.active() && r.gpio.all_off());
  r.bytes("\n");
  r.clock.advance(250);
  r.command("PULSE 1 1");
  CHECK(r.core.active());
}

void incomplete_line_does_not_block_expiry() {
  Rig r;
  r.command("PULSE 1 5");
  r.bytes("PULSE 2");
  r.clock.advance(5);
  r.core.tick();
  CHECK(!r.core.active() && r.gpio.all_off());
  r.bytes(" 250\n");
  CHECK(!r.core.active());
}

void stale_partial_frame_expires_and_cannot_actuate_later() {
  Rig r;
  r.clock.now = UINT32_MAX - 100;
  r.bytes("PULSE 15 250");
  r.clock.advance(249);
  r.core.tick();
  CHECK(!r.core.active());
  r.clock.advance(1);
  r.core.tick();
  CHECK(!r.core.active() && r.gpio.all_off());
  CHECK(r.drain() == "ERR INPUT\n");
  r.clock.advance(60000);
  r.bytes("\n");
  CHECK(!r.core.active());
  r.command("PULSE 1 1");
  CHECK(r.core.active());
}

void completed_frame_does_not_expire_during_gpio_write() {
  Rig r;
  r.gpio.high_cost_ms = 2;
  r.bytes("PULSE 1 250");
  r.clock.advance(249);
  r.bytes("\n");
  CHECK(r.core.active());
  CHECK(r.drain() == "OK PULSE 1 250\n");
  r.clock.advance(248);  // deadline starts BEFORE the 2 ms GPIO write
  r.core.tick();
  CHECK(!r.core.active() && r.gpio.all_off());
}

struct FakeRx {
  FakeClock& clock;
  std::string data;
  size_t offset = 0;
  uint32_t per_byte_ms = 1;
  explicit FakeRx(FakeClock& value) : clock(value) {}
  int available() const { return static_cast<int>(data.size() - offset); }
  int read() {
    if (offset == data.size()) return -1;
    clock.advance(per_byte_ms);
    return static_cast<unsigned char>(data[offset++]);
  }
};

void bounded_rx_flood_cannot_starve_deadline_or_stop() {
  Rig r;
  r.command("PULSE 1 10");
  FakeRx rx(r.clock);
  rx.data = std::string(1000, 'X');
  CHECK(hamda::pump_rx(r.core, rx, 64) == 64);
  CHECK(rx.offset == 64);
  CHECK(!r.core.active() && r.gpio.all_off());
  Rig s;
  s.command("PULSE 15 250");
  FakeRx stop_rx(s.clock);
  stop_rx.data = "PING\nSTOP\n" + std::string(1000, 'X');
  CHECK(hamda::pump_rx(s.core, stop_rx, 64) == 64);
  CHECK(!s.core.active() && s.gpio.all_off());
}

void gpio_failure_latches_fault_and_requests_off() {
  Rig r;
  r.gpio.fail_high_pin = 1;
  r.command("PULSE 15 10");
  CHECK(r.core.faulted());
  CHECK(!r.core.active() && r.gpio.all_off());
  r.gpio.fail_high_pin = -1;
  r.clock.advance(250);
  r.command("PULSE 1 10");
  CHECK(!r.core.active());
  r.command("STOP");
  CHECK(r.gpio.all_off());
  FakeClock clock;
  FakeGpio gpio;
  gpio.fail_prepare_pin = 2;
  hamda::Controller core(kA, clock, gpio);
  core.begin();
  CHECK(core.faulted() && gpio.all_off());
}

void identity_is_exact_and_no_autostart() {
  Rig r;
  r.command("ID");
  r.command("PING");
  CHECK(r.drain() ==
      "ID HAMDA_USB 1 A 10:00:3b:cc:97:d8\nOK PING\n");
  CHECK(!r.core.active() && r.gpio.all_off());
}

void full_or_partial_tx_never_blocks_control() {
  Rig r;
  for (unsigned i = 0; i < 100; ++i) r.command("PING");
  CHECK(r.core.dropped_replies() == 96);
  r.command("PULSE 15 250");
  CHECK(r.core.active());
  r.command("STOP");
  CHECK(!r.core.active() && r.gpio.all_off());
  CHECK(r.core.dropped_replies() == 98);
  CHECK(std::string(r.core.next_reply(), r.core.next_reply_size()) == "OK PING\n");
  r.core.consume_reply(3);
  CHECK(std::string(r.core.next_reply(), r.core.next_reply_size()) == "PING\n");
  r.core.consume_reply(999);
  CHECK(std::string(r.core.next_reply(), r.core.next_reply_size()) == "OK PING\n");
  r.drain();
  CHECK(r.core.next_reply() == nullptr && r.core.next_reply_size() == 0);
}

struct FakeTx {
  int capacity = 112;
  size_t accepted = 112;
  unsigned calls = 0;
  std::string sent;
  int availableForWrite() const { return capacity; }
  size_t write(const uint8_t* bytes, size_t size) {
    ++calls;
    CHECK(size <= static_cast<size_t>(capacity));
    if (size > accepted) size = accepted;
    sent.append(reinterpret_cast<const char*>(bytes), size);
    return size;
  }
};

void adapter_tx_is_off_only_capacity_bounded_and_handles_short_writes() {
  Rig r;
  FakeTx tx;
  r.command("PULSE 1 10");
  CHECK(hamda::pump_tx_when_off(r.core, tx) == 0);
  CHECK(tx.calls == 0);
  r.clock.advance(10);
  tx.capacity = 0;
  CHECK(hamda::pump_tx_when_off(r.core, tx) == 0);
  CHECK(!r.core.active() && tx.calls == 0);
  tx.capacity = 3;
  tx.accepted = 0;
  CHECK(hamda::pump_tx_when_off(r.core, tx) == 0);
  tx.accepted = 2;
  CHECK(hamda::pump_tx_when_off(r.core, tx) == 2);
  CHECK(tx.sent == "OK");
  tx.capacity = 112;
  tx.accepted = 112;
  hamda::pump_tx_when_off(r.core, tx);
  CHECK(tx.sent == "OK PULSE 1 10\n");
  CHECK(r.core.next_reply_size() == 0);
}

}  // namespace

int main() {
  struct Test { const char* name; void (*run)(); };
  const Test tests[] = {
      {"profiles_and_startup", profiles_and_startup},
      {"unknown_never_touches_gpio", unknown_never_touches_gpio},
      {"startup_pause", startup_pause},
      {"mask_and_autonomous_deadline", mask_and_autonomous_deadline},
      {"every_mask_and_minimum_duration", every_mask_and_minimum_duration},
      {"active_pulses_do_not_extend_or_add_channels", active_pulses_do_not_extend_or_add_channels},
      {"off_pause_after_expiry_and_stop", off_pause_after_expiry_and_stop},
      {"late_loop_pause_uses_actual_off", late_loop_pause_uses_actual_off},
      {"millis_wrap_for_pulse_and_pause", millis_wrap_for_pulse_and_pause},
      {"malformed_commands_fail_closed", malformed_commands_fail_closed},
      {"overflow_stops_before_newline_and_resynchronizes", overflow_stops_before_newline_and_resynchronizes},
      {"invalid_byte_and_crlf", invalid_byte_and_crlf},
      {"incomplete_line_does_not_block_expiry", incomplete_line_does_not_block_expiry},
      {"stale_partial_frame_expires_and_cannot_actuate_later", stale_partial_frame_expires_and_cannot_actuate_later},
      {"completed_frame_does_not_expire_during_gpio_write", completed_frame_does_not_expire_during_gpio_write},
      {"bounded_rx_flood_cannot_starve_deadline_or_stop", bounded_rx_flood_cannot_starve_deadline_or_stop},
      {"gpio_failure_latches_fault_and_requests_off", gpio_failure_latches_fault_and_requests_off},
      {"identity_is_exact_and_no_autostart", identity_is_exact_and_no_autostart},
      {"full_or_partial_tx_never_blocks_control", full_or_partial_tx_never_blocks_control},
      {"adapter_tx_is_off_only_capacity_bounded_and_handles_short_writes", adapter_tx_is_off_only_capacity_bounded_and_handles_short_writes},
  };
  for (const Test& test : tests) {
    test.run();
    std::cout << "PASS " << test.name << "\n";
  }
  std::cout << "20 native tests passed; no Arduino SDK or hardware validation.\n";
}

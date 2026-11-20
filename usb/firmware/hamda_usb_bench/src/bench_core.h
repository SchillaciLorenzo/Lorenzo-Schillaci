#ifndef HAMDA_USB_BENCH_CORE_H
#define HAMDA_USB_BENCH_CORE_H

#include <stddef.h>
#include <stdint.h>

namespace hamda {

// These are bench candidates, not electrically validated motor profiles.
struct Profile {
  const char* name;
  uint8_t mac[6];
  uint8_t pins[4];
};

const Profile* profile_for_mac(const uint8_t mac[6]);

class Clock {
 public:
  virtual ~Clock() {}
  virtual uint32_t now_ms() const = 0;
};

class Gpio {
 public:
  virtual ~Gpio() {}
  // Set the output latch LOW before enabling output direction.
  virtual bool prepare_low(uint8_t pin) = 0;
  virtual bool write(uint8_t pin, bool high) = 0;
};

class Controller {
 public:
  static const uint16_t kMaxPulseMs = 250;
  static const uint16_t kOffPauseMs = 250;
  static const uint16_t kFrameTimeoutMs = 250;
  static const size_t kLineCapacity = 32;
  static const size_t kReplyCapacity = 112;
  static const size_t kReplyCount = 4;

  Controller(const uint8_t mac[6], Clock& clock, Gpio& gpio);
  void begin();
  void tick();
  void receive(uint8_t byte);

  bool active() const { return active_; }
  bool faulted() const { return faulted_; }
  bool known_device() const { return profile_ != NULL; }
  uint8_t active_mask() const { return mask_; }
  const Profile* profile() const { return profile_; }

  // Fixed best-effort FIFO. Partial writes are consumed explicitly by caller.
  const char* next_reply() const;
  size_t next_reply_size() const;
  void consume_reply(size_t bytes);
  uint32_t dropped_replies() const { return dropped_replies_; }

 private:
  void execute_line();
  void invalid_input();
  void finish_episode();
  bool write_mask(uint8_t mask);
  void reply(const char* message);
  void identify();
  bool parse_pulse(uint8_t& mask, uint16_t& duration) const;

  uint8_t mac_[6];
  const Profile* profile_;
  Clock& clock_;
  Gpio& gpio_;
  bool begun_;
  bool active_;
  bool cooling_;
  bool faulted_;
  uint8_t mask_;
  uint16_t duration_ms_;
  uint32_t started_ms_;
  uint32_t off_since_ms_;
  char line_[kLineCapacity];
  size_t line_size_;
  uint32_t line_started_ms_;
  bool assembling_line_;
  bool discard_line_;
  bool saw_cr_;
  char replies_[kReplyCount][kReplyCapacity];
  size_t reply_sizes_[kReplyCount];
  size_t reply_head_;
  size_t reply_count_;
  size_t reply_offset_;
  uint32_t dropped_replies_;
};

// Serial.available/read must be nonblocking. The bound is bytes, not lines.
// Checking the clock around every byte prevents a flood starving the timer.
template <typename Transport>
size_t pump_rx(Controller& controller, Transport& serial, size_t byte_budget) {
  controller.tick();
  size_t processed = 0;
  while (processed < byte_budget && serial.available() > 0) {
    const int byte = serial.read();
    if (byte < 0) break;
    controller.receive(static_cast<uint8_t>(byte));
    ++processed;
    controller.tick();
  }
  controller.tick();
  return processed;
}

// Caller must configure a nonblocking write timeout on the real transport.
// No writes at all while ON, including when diagnostics are backlogged.
template <typename Transport>
size_t pump_tx_when_off(Controller& controller, Transport& serial) {
  controller.tick();
  if (controller.active()) return 0;
  const size_t remaining = controller.next_reply_size();
  if (remaining == 0) return 0;
  const int capacity = serial.availableForWrite();
  if (capacity <= 0) return 0;
  size_t amount = remaining;
  if (amount > static_cast<size_t>(capacity)) amount = capacity;
  const size_t written = serial.write(
      reinterpret_cast<const uint8_t*>(controller.next_reply()), amount);
  controller.consume_reply(written);
  controller.tick();
  return written;
}

}  // namespace hamda

#endif

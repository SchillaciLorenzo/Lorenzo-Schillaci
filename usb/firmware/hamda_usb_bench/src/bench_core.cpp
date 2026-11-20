#include "bench_core.h"

#include <stdio.h>
#include <string.h>

namespace hamda {
namespace {

// User-reported identical wiring: motor 1 orange, 2 dark green, 3 yellow,
// 4 blue. Numeric SuperMini correspondence is a bench candidate only.
const Profile kProfiles[] = {
    {"A", {0x10, 0x00, 0x3B, 0xCC, 0x97, 0xD8}, {3, 2, 1, 0}},
    {"B", {0x10, 0x00, 0x3B, 0xCC, 0x1C, 0x78}, {3, 2, 1, 0}},
};

bool unsigned_number(const char*& cursor, unsigned int limit,
                     unsigned int& value) {
  if (*cursor < '0' || *cursor > '9') return false;
  value = 0;
  while (*cursor >= '0' && *cursor <= '9') {
    const unsigned int digit = static_cast<unsigned int>(*cursor - '0');
    if (value > (limit - digit) / 10U) return false;
    value = value * 10U + digit;
    if (value > limit) return false;
    ++cursor;
  }
  return true;
}

}  // namespace

const Profile* profile_for_mac(const uint8_t mac[6]) {
  for (size_t i = 0; i < sizeof(kProfiles) / sizeof(kProfiles[0]); ++i) {
    if (memcmp(mac, kProfiles[i].mac, 6) == 0) return &kProfiles[i];
  }
  return NULL;
}

Controller::Controller(const uint8_t mac[6], Clock& clock, Gpio& gpio)
    : profile_(profile_for_mac(mac)), clock_(clock), gpio_(gpio),
      begun_(false), active_(false), cooling_(false), faulted_(false),
      mask_(0), duration_ms_(0), started_ms_(0), off_since_ms_(0),
      line_size_(0), line_started_ms_(0), assembling_line_(false),
      discard_line_(false), saw_cr_(false), reply_head_(0),
      reply_count_(0), reply_offset_(0), dropped_replies_(0) {
  memcpy(mac_, mac, sizeof(mac_));
  memset(line_, 0, sizeof(line_));
  memset(replies_, 0, sizeof(replies_));
  memset(reply_sizes_, 0, sizeof(reply_sizes_));
}

void Controller::begin() {
  if (begun_) return;
  begun_ = true;
  // Unknown MAC: do not configure, write or guess ANY motor GPIO.
  if (profile_ != NULL) {
    for (size_t i = 0; i < 4; ++i) {
      if (!gpio_.prepare_low(profile_->pins[i])) faulted_ = true;
    }
    if (faulted_) write_mask(0);
  }
  cooling_ = true;
  off_since_ms_ = clock_.now_ms();
}

bool Controller::write_mask(uint8_t mask) {
  if (profile_ == NULL) return false;
  bool okay = true;
  for (size_t i = 0; i < 4; ++i) {
    if (!gpio_.write(profile_->pins[i], (mask & (1U << i)) != 0)) okay = false;
  }
  if (!okay) faulted_ = true;
  return okay;
}

void Controller::finish_episode() {
  active_ = false;
  mask_ = 0;
  duration_ms_ = 0;
  if (profile_ != NULL) write_mask(0);
  // Anchor pause to actual software OFF request, even when a loop runs late.
  off_since_ms_ = clock_.now_ms();
  cooling_ = true;
}

void Controller::tick() {
  if (!begun_) return;
  const uint32_t now = clock_.now_ms();
  if (active_ && static_cast<uint32_t>(now - started_ms_) >= duration_ms_) {
    finish_episode();
  }
  if (assembling_line_ && !discard_line_ &&
      static_cast<uint32_t>(now - line_started_ms_) >= kFrameTimeoutMs) {
    invalid_input();
    discard_line_ = true;
  }
  if (cooling_ && static_cast<uint32_t>(clock_.now_ms() - off_since_ms_) >=
                      kOffPauseMs) {
    cooling_ = false;
  }
}

void Controller::invalid_input() {
  finish_episode();
  reply("ERR INPUT\n");
}

void Controller::receive(uint8_t byte) {
  tick();
  if (!begun_) return;
  if (byte == '\n') {
    // The frame is complete before executing code that may check the clock.
    assembling_line_ = false;
    if (!discard_line_) {
      line_[line_size_] = '\0';
      execute_line();
    }
    line_size_ = 0;
    discard_line_ = false;
    saw_cr_ = false;
    return;
  }
  if (discard_line_) return;
  if (!assembling_line_) {
    assembling_line_ = true;
    line_started_ms_ = clock_.now_ms();
  }
  // A CR is valid only as the final byte before LF (CRLF).
  if (saw_cr_) {
    invalid_input();
    discard_line_ = true;
    return;
  }
  if (byte == '\r') {
    saw_cr_ = true;
    return;
  }
  if (byte < 0x20 || byte > 0x7E || line_size_ >= kLineCapacity - 1) {
    invalid_input();  // Stop at the offending byte, not at a later newline.
    discard_line_ = true;
    return;
  }
  line_[line_size_++] = static_cast<char>(byte);
}

bool Controller::parse_pulse(uint8_t& mask, uint16_t& duration) const {
  if (strncmp(line_, "PULSE ", 6) != 0) return false;
  const char* cursor = line_ + 6;
  unsigned int parsed_mask = 0;
  unsigned int parsed_duration = 0;
  if (!unsigned_number(cursor, 15, parsed_mask) || parsed_mask == 0 ||
      *cursor++ != ' ') return false;
  if (!unsigned_number(cursor, kMaxPulseMs, parsed_duration) ||
      parsed_duration == 0 || *cursor != '\0') return false;
  mask = static_cast<uint8_t>(parsed_mask);
  duration = static_cast<uint16_t>(parsed_duration);
  return true;
}

void Controller::execute_line() {
  // STOP is never gated by active state, cooldown, identity or diagnostics.
  if (strcmp(line_, "STOP") == 0) {
    finish_episode();
    reply(faulted_ ? "ERR GPIO\n" : "OK STOP\n");
    return;
  }
  if (strcmp(line_, "ID") == 0) {
    identify();
    return;
  }
  if (strcmp(line_, "PING") == 0) {
    reply("OK PING\n");
    return;
  }
  uint8_t mask = 0;
  uint16_t duration = 0;
  if (!parse_pulse(mask, duration)) {
    invalid_input();
    return;
  }
  if (profile_ == NULL) {
    reply("ERR UNKNOWN_DEVICE\n");
  } else if (faulted_) {
    reply("ERR GPIO\n");
  } else if (active_) {
    // Reject ALL new pulses during an episode; never move its deadline.
    reply("ERR ACTIVE\n");
  } else if (cooling_) {
    reply("ERR COOLDOWN\n");
  } else {
    const uint32_t episode_start = clock_.now_ms();
    if (!write_mask(mask)) {
      finish_episode();
      reply("ERR GPIO\n");
      return;
    }
    mask_ = mask;
    duration_ms_ = duration;
    started_ms_ = episode_start;
    active_ = true;
    tick();
    char message[40];
    snprintf(message, sizeof(message), "OK PULSE %u %u\n",
             static_cast<unsigned>(mask), static_cast<unsigned>(duration));
    reply(message);
  }
}

void Controller::identify() {
  char message[kReplyCapacity];
  snprintf(message, sizeof(message),
           "ID HAMDA_USB 1 %s %02x:%02x:%02x:%02x:%02x:%02x\n",
           profile_ == NULL ? "UNKNOWN" : profile_->name,
           mac_[0], mac_[1], mac_[2], mac_[3], mac_[4], mac_[5]);
  reply(message);
}

void Controller::reply(const char* message) {
  if (reply_count_ >= kReplyCount) {
    if (dropped_replies_ != UINT32_MAX) ++dropped_replies_;
    return;
  }
  const size_t tail = (reply_head_ + reply_count_) % kReplyCount;
  const size_t length = strlen(message);
  if (length >= kReplyCapacity) return;
  memcpy(replies_[tail], message, length + 1);
  reply_sizes_[tail] = length;
  ++reply_count_;
}

const char* Controller::next_reply() const {
  return reply_count_ == 0 ? NULL : replies_[reply_head_] + reply_offset_;
}

size_t Controller::next_reply_size() const {
  return reply_count_ == 0 ? 0 : reply_sizes_[reply_head_] - reply_offset_;
}

void Controller::consume_reply(size_t bytes) {
  if (reply_count_ == 0) return;
  const size_t remaining = next_reply_size();
  if (bytes > remaining) bytes = remaining;
  reply_offset_ += bytes;
  if (reply_offset_ == reply_sizes_[reply_head_]) {
    reply_head_ = (reply_head_ + 1) % kReplyCount;
    --reply_count_;
    reply_offset_ = 0;
  }
}

}  // namespace hamda

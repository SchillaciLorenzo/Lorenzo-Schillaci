#!/usr/bin/env bash
set -euo pipefail
TACTUS_FIRMWARE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TACTUS_TEST_DIR="$(mktemp -d "${TMPDIR:-/tmp}/hamda-usb-native.XXXXXXXX")"
trap 'rm -rf -- "$TACTUS_TEST_DIR"' EXIT
"${CXX:-g++}" -std=c++11 -O2 -Wall -Wextra -Wpedantic -Werror \
  "$TACTUS_FIRMWARE_ROOT/hamda_usb_bench/src/bench_core.cpp" \
  "$TACTUS_FIRMWARE_ROOT/tests/test_bench_core.cpp" \
  -o "$TACTUS_TEST_DIR/test_bench_core"
"$TACTUS_TEST_DIR/test_bench_core"

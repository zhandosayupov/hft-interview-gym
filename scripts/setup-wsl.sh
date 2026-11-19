#!/usr/bin/env bash
# Installs the toolchain inside WSL2 Ubuntu 24.04 and the Python venv. Review before running.
set -euo pipefail
cd "$(dirname "$0")/.."
sudo apt-get update
sudo apt-get install -y build-essential g++ clang clangd lldb gdb cmake ninja-build git \
  python3-venv libgtest-dev libbenchmark-dev libclang-rt-dev sox libsox-fmt-pulse
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q
echo "Done. Next: scripts/print-desktop-config.sh"

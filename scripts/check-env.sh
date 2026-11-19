#!/usr/bin/env bash
# Read-only environment check for WSL2 Ubuntu. Installs nothing.
set -u
ok=0; bad=0
pass() { printf '  [ok]   %s\n' "$1"; ok=$((ok+1)); }
fail() { printf '  [MISS] %s\n' "$1"; bad=$((bad+1)); }
opt()  { printf '  [opt]  %s\n' "$1"; }  # optional: reported, never fails the check
have() { command -v "$1" >/dev/null 2>&1; }

echo "== Platform"
if grep -qi microsoft /proc/version 2>/dev/null; then pass "WSL kernel: $(uname -r)"; else fail "not running under WSL (fine for CI/Linux)"; fi
[ -n "${WSL_DISTRO_NAME:-}" ] && pass "distro: $WSL_DISTRO_NAME"
case "$PWD" in /mnt/*) fail "repo is on /mnt (Windows FS): move it to ~/projects for speed";; *) pass "repo on Linux FS: $PWD";; esac

echo "== Toolchain"
for t in git cmake ninja g++ clang++ clangd gdb lldb python3; do
  if have "$t"; then pass "$t: $($t --version 2>&1 | head -1)"; else fail "$t"; fi
done
if have cmake; then
  v=$(cmake --version | head -1 | awk '{print $3}')
  [ "$(printf '%s\n3.24\n' "$v" | sort -V | head -1)" = "3.24" ] && pass "cmake >= 3.24" || fail "cmake >= 3.24 required (have $v)"
fi

echo "== Libraries"
for p in GTest benchmark; do
  # Any one location is enough; `ls a b c` fails if *some* path is missing.
  found=""
  for d in /usr/lib/x86_64-linux-gnu/cmake/$p /usr/lib/cmake/$p /usr/local/lib/cmake/$p; do
    [ -d "$d" ] && { found="$d"; break; }
  done
  if [ -n "$found" ]; then pass "$p CMake package ($found)"; else fail "$p (apt install libgtest-dev libbenchmark-dev)"; fi
done

tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
cat > "$tmp/r.cpp" <<'CPP'
#include <thread>
int main() { int x = 0; std::thread t([&]{ x = 1; }); t.join(); return x - 1; }
CPP
echo "== Sanitizers (compile + run a tiny program)"
for cxx in g++ clang++; do
  have "$cxx" || continue
  for san in address,undefined thread; do
    if "$cxx" -std=c++20 -g -fsanitize=$san "$tmp/r.cpp" -o "$tmp/r" 2>"$tmp/err" && "$tmp/r" 2>"$tmp/run"; then
      pass "$cxx -fsanitize=$san"
    else
      fail "$cxx -fsanitize=$san: $(head -c 200 "$tmp/err" "$tmp/run" | tr '\n' ' ')"
      [ "$cxx" = clang++ ] && echo "         hint: sudo apt install libclang-rt-18-dev (or matching version)"
    fi
  done
done

echo "== Python"
if [ -x .venv/bin/python ]; then
  pass "venv: $(.venv/bin/python --version)"
  .venv/bin/python -c "import mcp" 2>/dev/null && pass "mcp package" || fail "mcp package (.venv/bin/pip install -e '.[dev]')"
else
  fail ".venv missing (python3 -m venv .venv && .venv/bin/pip install -e '.[dev]')"
fi

echo "== Audio for Claude Code /voice in WSL (only needed for the fallback workflow)"
[ -n "${WAYLAND_DISPLAY:-}${PULSE_SERVER:-}" ] && pass "WSLg audio env present" || opt "WSLg not detected (needed only for Claude Code voice dictation inside WSL)"
have sox && pass "sox" || opt "sox (sudo apt install sox libsox-fmt-pulse) — only for the fallback"

echo; echo "summary: $ok ok, $bad missing"
[ "$bad" -eq 0 ]

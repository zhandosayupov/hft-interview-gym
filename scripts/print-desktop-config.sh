#!/usr/bin/env bash
# Prints the mcpServers entry for %APPDATA%\Claude\claude_desktop_config.json (Windows side).
# Does not modify any file. Uses only `wsl.exe -d <distro> --exec`, which also exists in the
# old inbox (pre-Store) WSL. The server finds the repo from its own location, so no --cd.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
distro="${WSL_DISTRO_NAME:-Ubuntu}"
python3 - "$root" "$distro" <<'PY'
import json, sys
root, distro = sys.argv[1], sys.argv[2]
cfg = {"mcpServers": {"hft-gym": {
    "command": "wsl.exe",
    "args": ["-d", distro, "--exec", f"{root}/.venv/bin/python", "-m", "gym.server"],

}}}
print(json.dumps(cfg, indent=2))
PY

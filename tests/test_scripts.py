import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not shutil.which("bash"), reason="bash required")
def test_print_desktop_config_is_valid_json():
    out = subprocess.run(["bash", str(ROOT / "scripts/print-desktop-config.sh")],
                         capture_output=True, text=True, check=True).stdout
    srv = json.loads(out)["mcpServers"]["hft-gym"]
    assert srv["command"] == "wsl.exe"
    assert srv["args"][-2:] == ["-m", "gym.server"]
    assert "--cd" not in srv["args"]  # not supported by old inbox wsl.exe
    assert srv["args"][srv["args"].index("--exec") + 1] == f"{ROOT}/.venv/bin/python"


def test_claude_code_settings_deny_solution_edits():
    s = json.loads((ROOT / ".claude/settings.json").read_text())
    assert "Edit(/sessions/*/solution/**)" in s["permissions"]["deny"]
    assert any(r.startswith("Bash(git push") for r in s["permissions"]["deny"])


def test_template_presets_match_python():
    from gym.build import PRESETS
    p = json.loads((ROOT / "template/session/CMakePresets.json").read_text())
    for kind in ("configurePresets", "buildPresets", "testPresets"):
        names = {x["name"] for x in p[kind] if not x.get("hidden")}
        assert names == set(PRESETS), kind

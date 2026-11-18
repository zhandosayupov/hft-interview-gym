import shutil
from pathlib import Path

import pytest

from gym.workspace import Workspace

REPO = Path(__file__).resolve().parent.parent

PROBLEM = """# Sum
## Problem
Return a + b.
## Interface
`int add(int a, int b);`
"""


@pytest.fixture
def ws(tmp_path, monkeypatch) -> Workspace:
    """A throwaway workspace: copy of template/, cmake/, docs/; empty sessions/."""
    for d in ("template", "cmake", "docs"):
        shutil.copytree(REPO / d, tmp_path / d)
    (tmp_path / "sessions").mkdir()
    monkeypatch.setenv("GYM_ROOT", str(tmp_path))
    return Workspace(tmp_path)


@pytest.fixture
def session_id(ws):
    from gym.session import create_session
    return create_session(ws, "add", "Add two ints", "dsa", "easy", PROBLEM).id

import subprocess

import pytest

from gym import tools
from gym.workspace import PolicyError

from .conftest import PROBLEM


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_ping_and_guide(ws):
    p = tools.gym_ping()
    assert p["ok"] and p["root"] == str(ws.root)
    assert "Never write" in tools.get_interviewer_guide()


def test_start_session_and_scaffold(ws):
    r = tools.start_session("two-sum", "Two Sum", "dsa", "easy", PROBLEM)
    sid = r["session_id"]
    assert tools.list_sessions()[0]["id"] == sid
    tools.write_scaffold_file(sid, "tests/test_solution.cpp", "// tests", overwrite=True)
    with pytest.raises(PolicyError):
        tools.write_scaffold_file(sid, "solution/solution.hpp", "// cheat", overwrite=True)
    assert tools.read_file(f"sessions/{sid}/tests/test_solution.cpp") == "// tests"
    assert f"sessions/{sid}/problem.md" in tools.list_files()
    assert tools.set_session_status(sid, "coding") == {"status": "coding"}


def test_no_tool_can_write_solution_or_delete():
    names = {f.__name__ for f in tools.ALL_TOOLS}
    assert not any(w in n for n in names for w in ("delete", "remove", "commit", "push", "edit_solution"))


def test_git_views(ws):
    git(ws.root, "init", "-q")
    git(ws.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init")
    assert tools.git_diff() == "(no changes)"
    sid = tools.start_session("g", "G", "dsa", "easy", PROBLEM)["session_id"]
    git(ws.root, "add", "-A")
    git(ws.root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "s")
    (ws.session_dir(sid) / "solution" / "solution.hpp").write_text("#pragma once\nint f();\n")
    (ws.session_dir(sid) / "solution" / "new.cpp").write_text("int f(){return 1;}\n")
    d = tools.git_diff(f"sessions/{sid}")
    assert "+int f();" in d and "untracked" in d and "new.cpp" in d
    assert "##" in tools.git_status()
    with pytest.raises(PolicyError):
        tools.git_diff("../")


def test_gitview_refuses_mutating_subcommands(ws):
    from gym import gitview
    for sub in ("commit", "push", "reset", "checkout", "clean"):
        with pytest.raises(PermissionError):
            gitview._git(ws, sub)

from datetime import datetime, timezone

import pytest

from gym import session
from gym.workspace import PolicyError

from .conftest import PROBLEM

T = datetime(2026, 11, 18, 9, 30, tzinfo=timezone.utc)


def test_create_session_layout(ws):
    st = session.create_session(ws, "spsc-queue", "SPSC", "concurrency", "hard", PROBLEM, now=T)
    assert st.id == "20261118-0930-spsc-queue"
    d = ws.root / "sessions" / st.id
    for f in ("problem.md", "CMakeLists.txt", "CMakePresets.json", "solution/solution.hpp",
              "tests/test_solution.cpp", "session.json"):
        assert (d / f).is_file(), f
    assert (d / "problem.md").read_text().startswith("# Sum")
    assert session.load_state(ws, st.id).status == "setup"


def test_duplicate_session_rejected(ws):
    session.create_session(ws, "x", "X", "dsa", "easy", PROBLEM, now=T)
    with pytest.raises(FileExistsError):
        session.create_session(ws, "x", "X", "dsa", "easy", PROBLEM, now=T)


@pytest.mark.parametrize("slug", ["", "Bad", "a b", "../x", "-x", "a" * 49])
def test_bad_slug(ws, slug):
    with pytest.raises(PolicyError):
        session.create_session(ws, slug, "X", "dsa", "easy", PROBLEM)


def test_bad_track_difficulty_problem(ws):
    with pytest.raises(ValueError):
        session.create_session(ws, "x", "X", "web", "easy", PROBLEM)
    with pytest.raises(ValueError):
        session.create_session(ws, "x", "X", "dsa", "insane", PROBLEM)
    with pytest.raises(ValueError):
        session.create_session(ws, "x", "X", "dsa", "easy", "   ")


def test_status_and_listing(ws):
    a = session.create_session(ws, "a", "A", "dsa", "easy", PROBLEM, now=T)
    b = session.create_session(ws, "b", "B", "cpp", "medium", PROBLEM,
                               now=T.replace(hour=10))
    session.set_status(ws, a.id, "coding")
    assert [s.id for s in session.list_sessions(ws)] == [a.id, b.id]
    assert session.latest_session(ws).id == b.id
    assert session.load_state(ws, a.id).status == "coding"
    with pytest.raises(ValueError):
        session.set_status(ws, a.id, "bogus")


def test_no_sessions(ws):
    assert session.list_sessions(ws) == []
    assert session.latest_session(ws) is None

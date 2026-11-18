import os

import pytest

from gym.workspace import PolicyError


def test_resolve_inside(ws):
    assert ws.resolve("sessions") == ws.root / "sessions"


@pytest.mark.parametrize("bad", ["..", "../etc/passwd", "/etc/passwd", "sessions/../../x", "a\x00b"])
def test_resolve_rejects_escape(ws, bad):
    with pytest.raises(PolicyError):
        ws.resolve(bad)


def test_symlink_escape_rejected(ws, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    (outside / "secret.txt").write_text("x")
    os.symlink(outside, ws.root / "sessions" / "link")
    with pytest.raises(PolicyError):
        ws.read_text("sessions/link/secret.txt")


@pytest.mark.parametrize("bad_id", ["", ".", "..", "a/b", "a\\b"])
def test_invalid_session_ids(ws, bad_id):
    with pytest.raises(PolicyError):
        ws.session_dir(bad_id)


def test_missing_session(ws):
    with pytest.raises(FileNotFoundError):
        ws.session_dir("nope")


@pytest.mark.parametrize("path", ["solution/solution.hpp", "solution/new.cpp", "./solution/x.hpp",
                                  "tests/../solution/solution.hpp"])
def test_interviewer_cannot_write_solution(ws, session_id, path):
    with pytest.raises(PolicyError):
        ws.interviewer_write(session_id, path, "int add(int a,int b){return a+b;}", overwrite=True)


@pytest.mark.parametrize("path", ["CMakeLists.txt", "session.json", "report.json", "../x.md",
                                  "../../docs/interviewer.md", "tests"])
def test_interviewer_cannot_write_other_files(ws, session_id, path):
    with pytest.raises(PolicyError):
        ws.interviewer_write(session_id, path, "x", overwrite=True)


def test_interviewer_writes_allowed(ws, session_id):
    ws.interviewer_write(session_id, "tests/test_more.cpp", "// t")
    ws.interviewer_write(session_id, "bench/bench_solution.cpp", "// b")
    ws.interviewer_write(session_id, "notes.md", "hint 1")
    assert (ws.session_dir(session_id) / "tests/test_more.cpp").read_text() == "// t"


def test_no_silent_overwrite(ws, session_id):
    with pytest.raises(PolicyError, match="overwrite"):
        ws.interviewer_write(session_id, "problem.md", "changed")
    ws.interviewer_write(session_id, "problem.md", "changed", overwrite=True)
    assert (ws.session_dir(session_id) / "problem.md").read_text() == "changed"


def test_read_text_truncates_and_rejects_binary(ws, session_id):
    sdir = ws.session_dir(session_id)
    (sdir / "notes.md").write_text("a" * 50)
    assert "truncated" in ws.read_text(f"sessions/{session_id}/notes.md", max_bytes=10)
    (sdir / "blob.bin").write_bytes(b"\x00\x01")
    with pytest.raises(PolicyError):
        ws.read_text(f"sessions/{session_id}/blob.bin")


def test_list_files_skips_build(ws, session_id):
    b = ws.session_dir(session_id) / "build" / "asan"
    b.mkdir(parents=True)
    (b / "junk.o").write_text("")
    files = ws.list_files("sessions")
    assert any(f.endswith("problem.md") for f in files)
    assert not any("/build/" in f for f in files)

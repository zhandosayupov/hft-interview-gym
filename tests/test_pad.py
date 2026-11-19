"""Local pad (gym/pad.py): candidate-only writes, local-only access, build endpoint."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from gym.pad import PadServer
from gym.workspace import PolicyError

SOLUTION = "#pragma once\ninline int add(int a, int b) { return a + b; }\n"


@pytest.fixture
def pad(ws):
    srv = PadServer(ws, "127.0.0.1", 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def call(srv, path, body=None, headers=None, method=None):
    h = {}
    data = None
    if body is not None:
        h = {"Content-Type": "application/json", "X-Gym-Pad": "1"}
        data = json.dumps(body).encode()
    h.update(headers or {})
    req = urllib.request.Request(srv.url.rstrip("/") + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if r.headers.get_content_type() == "application/json"
                              else raw.decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


# ---- Workspace policy -------------------------------------------------------------
def test_candidate_write_only_solution(ws, session_id):
    p = ws.candidate_write(session_id, "solution/solution.hpp", SOLUTION)
    assert p.read_text() == SOLUTION
    ws.candidate_write(session_id, "solution/extra/helpers.cpp", "// ok")
    for bad in ("tests/test_solution.cpp", "problem.md", "notes.md", "session.json",
                "solution", "solution/../problem.md", "../other/solution/x.hpp",
                "solution/evil.sh", "CMakeLists.txt"):
        with pytest.raises(PolicyError):
            ws.candidate_write(session_id, bad, "x")


# ---- HTTP API -----------------------------------------------------------------------
def test_page_and_session_view(pad, session_id):
    status, html = call(pad, "/")
    assert status == 200 and "Build &amp; Test" in html
    status, d = call(pad, "/api/sessions")
    assert status == 200 and d["latest"] == session_id
    status, v = call(pad, f"/api/session?id={session_id}")
    assert status == 200
    assert v["problem_md"].startswith("# Sum")
    assert v["solution_files"] == ["solution/solution.hpp"]
    assert v["test_files"] == ["tests/test_solution.cpp"]
    status, f = call(pad, f"/api/file?session={session_id}&path=tests/test_solution.cpp")
    assert status == 200 and "solution.hpp" in f["content"]


def test_save_solution(pad, ws, session_id):
    status, d = call(pad, "/api/save", {"session": session_id, "path": "solution/solution.hpp",
                                        "content": SOLUTION})
    assert status == 200, d
    assert (ws.session_dir(session_id) / "solution/solution.hpp").read_text() == SOLUTION


@pytest.mark.parametrize("path", ["tests/test_solution.cpp", "problem.md",
                                  "solution/../../../escape.hpp", "session.json"])
def test_save_outside_solution_refused(pad, ws, session_id, path):
    before = (ws.session_dir(session_id) / "tests/test_solution.cpp").read_text()
    status, d = call(pad, "/api/save", {"session": session_id, "path": path, "content": "x"})
    assert status == 403, d
    assert (ws.session_dir(session_id) / "tests/test_solution.cpp").read_text() == before
    assert not (ws.root.parent / "escape.hpp").exists()


def test_bad_session_and_paths(pad, session_id):
    assert call(pad, "/api/session?id=..")[0] == 403
    assert call(pad, "/api/session?id=nope")[0] == 404
    assert call(pad, f"/api/file?session={session_id}&path=../../../etc/passwd")[0] == 403
    assert call(pad, "/api/nothing")[0] == 404


def test_cross_site_requests_refused(pad, ws, session_id):
    body = {"session": session_id, "path": "solution/solution.hpp", "content": "pwned"}
    target = ws.session_dir(session_id) / "solution/solution.hpp"
    before = target.read_text()
    # no custom header (what a plain cross-site form/fetch would send)
    req = urllib.request.Request(pad.url + "api/save", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "text/plain"}, method="POST")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=10)
    assert e.value.code == 403
    # foreign Origin
    assert call(pad, "/api/save", body, {"Origin": "http://evil.example"})[0] == 403
    # DNS rebinding: foreign Host header
    assert call(pad, "/api/sessions", headers={"Host": "evil.example:8765"})[0] == 403
    assert target.read_text() == before


def test_build_rejects_bad_preset(pad, session_id):
    status, d = call(pad, "/api/build", {"session": session_id, "preset": "msan"})
    assert status == 400 and "preset" in d["error"]


@pytest.mark.cpp
def test_build_and_test_records_run(pad, ws, session_id):
    from gym.session import load_state
    call(pad, "/api/save", {"session": session_id, "path": "solution/solution.hpp",
                            "content": SOLUTION})
    status, d = call(pad, "/api/build", {"session": session_id, "preset": "asan"})
    assert status == 200, d
    assert d["ok"] is True, d["steps"][-1]["output_tail"]
    assert d["tests_total"] and d["tests_passed"] == d["tests_total"]
    builds = load_state(ws, session_id).builds
    assert builds and builds[-1]["preset"] == "asan" and builds[-1]["ok"] is True
